# inventory/permissions.py
from rest_framework import permissions

class IsAdminOrStaffWrite(permissions.BasePermission):
    """
    Permission rules:
      - SAFE_METHODS (GET, HEAD, OPTIONS) allowed for everyone.
      - POST/PUT/PATCH allowed for authenticated users with role 'staff' or 'admin'.
      - DELETE allowed only for authenticated users who are either:
          * role 'admin', OR
          * superuser.
    Assumes the user model has a `role` attribute with values 'admin' or 'staff'.
    """

    def has_permission(self, request, view):
        # Read-only access for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # DELETE only for admin or superuser
        if request.method == 'DELETE':
            return bool(
                request.user and
                request.user.is_authenticated and
                (getattr(request.user, "role", "") == "admin" or request.user.is_superuser)
            )

        # POST/PUT/PATCH allowed for staff & admin
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "role", "") in ("admin", "staff")
        )

    def has_object_permission(self, request, view, obj):
        """
        Object-level permissions: same rules as above.
        """
        return self.has_permission(request, view)
