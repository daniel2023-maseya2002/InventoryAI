from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # role: Admin / Staff
    ROLE_CHOICES = (("admin", "Admin"), ("staff", "Staff"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="staff")
    phone = models.CharField(max_length=32, blank=True, null=True)
    # settings JSON for notification preferences etc.
    settings = models.JSONField(default=dict, blank=True)

    # Make email required and unique, use it as the authentication field
    email = models.EmailField("email address", unique=True)

    # Make username optional (if you want to drop username entirely you could,
    # but keeping it avoids touching other code that expects username)
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # nothing else required on createsuperuser (email used as username field)

    def __str__(self):
        # show email as primary identifier
        return f"{self.email} ({self.role})"

class LoginCode(models.Model):
    """
    One-time login/verify code tied to an email (and optionally a user).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=8, help_text="Short numeric code or token")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["code"]),
        ]

    def is_valid(self):
        return (not self.used) and (self.expires_at >= timezone.now())

    @classmethod
    def create_code(cls, email, user=None, minutes_valid=15, code=None):
        from django.utils.crypto import get_random_string
        # 6-digit numeric code by default
        code = code or get_random_string(length=6, allowed_chars="0123456789")
        expires = timezone.now() + timedelta(minutes=minutes_valid)
        return cls.objects.create(email=email, user=user, code=code, expires_at=expires)