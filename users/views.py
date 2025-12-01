# users/views.py
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .serializers import UserSerializer, UserCreateSerializer, SimpleUserSerializer

from .permissions import IsAdminOrSuperuser

from .models import LoginCode  # ensure this model exists in users.models
from .utils import send_login_code_email, user_tokens_for_user

# For Google token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

User = get_user_model()


# -------------------------
# Admin UserViewSet (no public register)
# -------------------------
class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for users. No public `register` action.
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperuser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["role", "is_active", "is_staff", "is_superuser"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "date_joined"]

    def get_serializer_class(self):
        # Admin uses full serializer; leave as default.
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


# -------------------------
# Public auth endpoints: Request code, Verify code, Google auth
# -------------------------
from rest_framework import serializers

class RequestLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyLoginCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=32)


class RequestLoginCodeView(APIView):
    """
    POST { "email": "user@example.com" }
    Creates a LoginCode and emails it. Allowed to anyone.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RequestLoginCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()

        # Try to link to existing user (optional). We do not create user here.
        user = User.objects.filter(email__iexact=email).first()

        # create code
        minutes_valid = int(getattr(settings, "LOGIN_CODE_EXPIRE_MINUTES", 15))
        code_obj = LoginCode.create_code(email=email, user=user, minutes_valid=minutes_valid)

        try:
            send_login_code_email(email, code_obj.code, minutes_valid=minutes_valid)
        except Exception as e:
            # safe failure
            code_obj.delete()
            return Response({"detail": "Failed to send email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "Code sent (check your email)"})


class VerifyLoginCodeView(APIView):
    """
    POST { "email": "...", "code": "..." } -> returns JWT tokens
    Auto-provisions user if it does not exist.
    """
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = VerifyLoginCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        code = serializer.validated_data["code"].strip()

        code_obj = LoginCode.objects.filter(email__iexact=email, code=code, used=False).order_by("-created_at").first()
        if not code_obj or not code_obj.is_valid():
            return Response({"detail": "Invalid or expired code"}, status=status.HTTP_400_BAD_REQUEST)

        # mark used
        code_obj.used = True
        code_obj.save(update_fields=["used"])

        # get or create user (safe get/create)
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            # auto-provision with default role 'staff'
            username = email.split("@")[0]
            user = User.objects.create(username=username, email=email, is_active=True, role=getattr(settings, "DEFAULT_NEW_USER_ROLE", "staff"))

        # attach user to code if not set
        if not code_obj.user:
            code_obj.user = user
            code_obj.save(update_fields=["user"])

        tokens = user_tokens_for_user(user)
        return Response({"user": {"id": str(user.id), "email": user.email, "role": user.role}, "tokens": tokens})


class GoogleAuthView(APIView):
    """
    POST { "id_token": "..." } — verify with Google and return JWT tokens.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("id_token")
        if not token:
            return Response({"detail": "id_token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # verify id_token; audience optional but recommended (set GOOGLE_CLIENT_ID in settings)
            audience = getattr(settings, "GOOGLE_CLIENT_ID", None) or None
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), audience)
            email = idinfo.get("email")
            email_verified = idinfo.get("email_verified", False)
            if not email or not email_verified:
                return Response({"detail": "Google account email not verified"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": "Invalid Google token", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # get or create user safely
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            username = email.split("@")[0]
            user = User.objects.create(username=username, email=email, is_active=True, role=getattr(settings, "DEFAULT_NEW_USER_ROLE", "staff"))

        tokens = user_tokens_for_user(user)
        return Response({"user": {"id": str(user.id), "email": user.email, "role": user.role}, "tokens": tokens})
