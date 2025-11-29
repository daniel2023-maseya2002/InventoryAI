from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserCreateSerializer, SimpleUserSerializer

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    /api/users/           [GET (admin only): list users]
    /api/users/{pk}/      [GET/PUT/PATCH/DELETE (admin only)]
    /api/users/register/  [POST public] create account
    /api/users/me/        [GET authenticated] get profile
    """
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer

    def get_permissions(self):
        # public create (register), authenticated for "me", admin for list/detail
        if self.action in ("register",):
            return [AllowAny()]
        if self.action in ("me",):
            return [IsAuthenticated()]
        # list, retrieve, update, destroy require admin
        return [IsAdminUser()]

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(UserSerializer(request.user).data)
