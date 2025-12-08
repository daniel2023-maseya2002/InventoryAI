# users/views.py
import io
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .throttles import RequestCodeThrottle
from rest_framework.throttling import AnonRateThrottle

from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .serializers import UserSerializer, UserCreateSerializer, SimpleUserSerializer
from .permissions import IsAdminOrSuperuser
from .models import LoginCode
from .utils import send_login_code_email, user_tokens_for_user

# For Google token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# For bulk import
import pandas as pd
from rest_framework.parsers import MultiPartParser, FormParser

User = get_user_model()
logger = logging.getLogger(__name__)


# -------------------------
# Admin UserViewSet (no public register)
# -------------------------
class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for users. No public `register` action.
    Also exposes a bulk_import endpoint for admins to upload CSV/XLSX with columns:
    email, username(optional), first_name, last_name, role, password(optional)
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperuser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["role", "is_active", "is_staff", "is_superuser"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "date_joined"]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        return self.serializer_class

    @action(detail=False, methods=["get"], url_path="me", permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        Return the current authenticated user info.
        """
        return Response(UserSerializer(request.user).data)

    @action(detail=True, methods=["post"], url_path="set_password", permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperuser])
    def set_password(self, request, pk=None):
        """
        Admin endpoint to set a user's password.
        """
        user = self.get_object()
        password = request.data.get("password", "")
        if not password:
            return Response({"detail": "Password is required."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({"status": "password_set"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk_import", permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperuser])
    def bulk_import(self, request):
        """
        Admin-only: upload CSV/XLSX with file field 'file'.
        Expected columns (case-insensitive): email, username, first_name, last_name, role, password
        """
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "No file uploaded (field name 'file')"}, status=status.HTTP_400_BAD_REQUEST)

        filename = uploaded.name.lower()
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            logger.exception("Could not read bulk import file")
            return Response({"detail": f"Could not read file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        failed = []
        for idx, row in df.iterrows():
            try:
                email = str(row.get("email") or row.get("Email") or "").strip()
                if not email:
                    raise ValueError("Missing email")
                # skip existing
                existing = User.objects.filter(email__iexact=email).first()
                if existing:
                    failed.append({"row": int(idx) + 1, "email": email, "error": "User exists"})
                    continue

                username = row.get("username") or row.get("Username") or email.split("@")[0]
                first_name = row.get("first_name") or row.get("First_Name") or ""
                last_name = row.get("last_name") or row.get("Last_Name") or ""
                role = row.get("role") or "staff"
                password = row.get("password") or None

                user = User(username=username, email=email, first_name=first_name, last_name=last_name, role=role)
                if password:
                    user.set_password(str(password))
                else:
                    user.set_unusable_password()
                user.save()
                created.append({"email": user.email, "id": str(user.id)})
            except Exception as e:
                logger.exception("Bulk import row failed")
                failed.append({"row": int(idx) + 1, "error": str(e)})

        return Response({"created_count": len(created), "failed": failed, "created": created})


# -------------------------
# Public auth endpoints: Request code, Verify code, Google auth
# -------------------------
class RequestLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=32)


class RequestLoginCodeView(APIView):
    """
    POST { "email": "user@example.com" }
    Creates a LoginCode and emails it. Allowed to anyone.
    Throttled via RequestCodeThrottle + AnonRateThrottle.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RequestCodeThrottle, AnonRateThrottle]

    def post(self, request):
        serializer = RequestLoginCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()

        # Try to link to existing user (optional). We do not create user here.
        user = User.objects.filter(email__iexact=email).first()

        # create code
        minutes_valid = int(getattr(settings, "LOGIN_CODE_EXPIRE_MINUTES", 15))
        try:
            code_obj = LoginCode.create_code(email=email, user=user, minutes_valid=minutes_valid)
        except Exception as e:
            logger.exception("Failed to create LoginCode")
            return Response({"detail": "Failed to create code"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Send email; if it fails, delete code and return error.
        try:
            send_login_code_email(email, code_obj.code, minutes_valid=minutes_valid)
        except Exception as e:
            # safe failure: remove code to avoid accumulation
            try:
                code_obj.delete()
            except Exception:
                logger.exception("Failed to delete LoginCode after email send error")
            logger.exception("Failed to send login code email")
            # developer convenience: include error message only when DEBUG
            if getattr(settings, "DEBUG", False):
                return Response({"detail": "Failed to send email", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"detail": "Failed to send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # DEV convenience: return the code in response when DEBUG=True
        if getattr(settings, "DEBUG", False):
            return Response({"detail": "Code sent (DEV)", "code": code_obj.code})

        return Response({"detail": "Code sent (check your email)"})


class VerifyLoginCodeView(APIView):
    """
    POST { "email": "...", "code": "..." } -> returns JWT tokens
    Auto-provisions user if it does not exist.
    Includes attempt tracking / lockout behavior.
    """
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = VerifyLoginCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        code = serializer.validated_data["code"].strip()

        # Try to find exact matching valid code object
        code_obj = LoginCode.objects.filter(email__iexact=email, code=code).order_by("-created_at").first()

        if not code_obj:
            # increment attempt on latest code for this email to slow brute force
            latest = LoginCode.objects.filter(email__iexact=email).order_by("-created_at").first()
            if latest:
                try:
                    latest.register_attempt()
                except Exception:
                    logger.exception("Failed to register attempt on latest LoginCode")
            return Response({"detail": "Invalid or expired code"}, status=status.HTTP_400_BAD_REQUEST)

        # Check lockout
        if getattr(code_obj, "locked_until", None) and code_obj.locked_until > timezone.now():
            return Response({"detail": "Too many attempts. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Check validity
        if not code_obj.is_valid():
            return Response({"detail": "Invalid or expired code"}, status=status.HTTP_400_BAD_REQUEST)

        # Success: mark used
        code_obj.used = True
        code_obj.save(update_fields=["used"])

        # get or create user (safe get/create)
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            username = email.split("@")[0]
            user = User.objects.create(
                username=username,
                email=email,
                is_active=True,
                role=getattr(settings, "DEFAULT_NEW_USER_ROLE", "staff")
            )

        # attach user to code if not set
        if not code_obj.user:
            code_obj.user = user
            code_obj.save(update_fields=["user"])

        tokens = user_tokens_for_user(user)
        return Response({"user": {"id": str(user.id), "email": user.email, "role": user.role}, "tokens": tokens})


# GoogleAuthView (paste into the file)
class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("id_token")
        if not token:
            return Response({"detail": "id_token required"}, status=status.HTTP_400_BAD_REQUEST)

        audience = getattr(settings, "GOOGLE_CLIENT_ID", None)
        try:
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), audience)
            email = idinfo.get("email")
            email_verified = idinfo.get("email_verified", False)
            if not email or not email_verified:
                return Response({"detail": "Google account email not verified"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Invalid Google token")
            return Response({"detail": "Invalid Google token", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # ensure case-insensitive lookup and safe get/create
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            username = email.split("@")[0]
            user = User.objects.create(username=username, email=email, is_active=True,
                                       role=getattr(settings, "DEFAULT_NEW_USER_ROLE", "staff"))
        tokens = user_tokens_for_user(user)
        return Response({"user": {"id": str(user.id), "email": user.email, "role": user.role}, "tokens": tokens})
