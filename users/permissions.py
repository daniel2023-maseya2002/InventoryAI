# users/permissions.py
from rest_framework import permissions

class IsAdminOrSuperuser(permissions.BasePermission):
    """
    Allow access only to users with role == 'admin' or is_superuser.
    Use this for user-management endpoints.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", "") == "admin" or user.is_superuser
