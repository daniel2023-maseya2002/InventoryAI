# inventory/utils.py
from .models import Notification
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail

User = get_user_model()

def create_notification(user=None, type="info", title="", message="", payload=None, send_email=False):
    payload = payload or {}
    notif = Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message,
        payload=payload
    )

    # simple synchronous email (DEV only). In production move to Celery background job.
    if send_email and user and user.email:
        subject = title
        body = message + "\n\nDetails:\n" + str(payload)
        # fallback: use Django settings EMAIL_BACKEND configured
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        except Exception:
            # don't raise in production paths here; log if you want
            pass

    return notif
