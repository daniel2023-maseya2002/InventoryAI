# users/urls.py (example)
from django.urls import path, include
from rest_framework import routers
from .views import UserViewSet, RequestLoginCodeView, VerifyLoginCodeView, GoogleAuthView

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path("", include(router.urls)),
    path("auth/request_code/", RequestLoginCodeView.as_view(), name="request-code"),
    path("auth/verify_code/", VerifyLoginCodeView.as_view(), name="verify-code"),
    path("auth/google/", GoogleAuthView.as_view(), name="google-auth"),
]
