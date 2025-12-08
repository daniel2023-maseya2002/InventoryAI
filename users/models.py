from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=12, help_text="Short numeric code or token")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    # security fields
    attempts = models.PositiveSmallIntegerField(default=0)   # attempts made to verify this code
    max_attempts = models.PositiveSmallIntegerField(default=5)  # per-code max attempts
    locked_until = models.DateTimeField(null=True, blank=True)  # optional lockout time

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["code"]),
        ]

    def is_valid(self):
        if self.used:
            return False
        if self.expires_at < timezone.now():
            return False
        if self.locked_until and self.locked_until > timezone.now():
            return False
        return True

    @classmethod
    def create_code(cls, email, user=None, minutes_valid=15, code=None, max_attempts=None):
        from django.utils.crypto import get_random_string
        code = code or get_random_string(length=6, allowed_chars="0123456789")
        expires = timezone.now() + timedelta(minutes=minutes_valid)
        mc = max_attempts or int(getattr(settings, "LOGIN_CODE_MAX_ATTEMPTS", 5))
        return cls.objects.create(email=email, user=user, code=code, expires_at=expires, max_attempts=mc)

    def register_attempt(self):
        """
        Called when a verification attempt is made for this specific code.
        If attempts exceed max_attempts, set locked_until for a short cooldown.
        """
        self.attempts += 1
        if self.attempts >= (self.max_attempts or int(getattr(settings, "LOGIN_CODE_MAX_ATTEMPTS", 5))):
            # lock next attempts for some minutes
            lock_minutes = int(getattr(settings, "LOGIN_CODE_LOCK_MINUTES", 15))
            self.locked_until = timezone.now() + timedelta(minutes=lock_minutes)
        self.save(update_fields=["attempts", "locked_until"])