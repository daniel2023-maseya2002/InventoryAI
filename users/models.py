from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # role: Admin / Staff
    ROLE_CHOICES = (("admin", "Admin"), ("staff", "Staff"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="staff")
    phone = models.CharField(max_length=32, blank=True, null=True)
    # settings JSON for notification preferences etc.
    settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"
