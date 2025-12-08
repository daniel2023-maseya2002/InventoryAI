# users/utils.py
import threading
import traceback

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

# -----------------------
# Email sending helpers
# -----------------------
def _send_email_sync(subject, body, to_emails, html_body=None, from_email=None):
    """
    Synchronous email send. Return (True, None) on success, (False, error_str) on failure.
    """
    try:
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        if html_body:
            msg = EmailMultiAlternatives(subject, body, from_email, to_emails)
            msg.attach_alternative(html_body, "text/html")
        else:
            msg = EmailMessage(subject, body, from_email, to_emails)
        msg.send(fail_silently=False)
        return True, None
    except Exception as e:
        tb = traceback.format_exc()
        # In production replace prints with logger.error(...)
        print("Email send failed:", e)
        print(tb)
        return False, str(e)


def send_email_background(subject, body, to_emails, html_body=None, from_email=None):
    """
    Fire-and-forget email sender using a background thread.
    Suitable for local/dev and low-volume usage. For production use Celery.
    """
    thread = threading.Thread(
        target=_send_email_sync,
        args=(subject, body, to_emails, html_body, from_email),
        daemon=True,
    )
    thread.start()
    return True


def send_login_code_email(email, code, minutes_valid=15):
    """
    Non-blocking: generate and send a numeric login code to the user's email.
    Returns True when the send task was started (does not guarantee delivery).
    """
    subject = f"{getattr(settings, 'SHOP_NAME', 'Inventory')} — Your login code"
    body = (
        f"Your login code is: {code}\n\n"
        f"This code is valid for {minutes_valid} minutes.\n"
        "If you did not request this code, ignore this email.\n\n"
        "— The Team"
    )

    # Optional: generate HTML body via template rendering (uncomment if you have a template)
    # from django.template.loader import render_to_string
    # html_body = render_to_string("emails/login_code.html", {"code": code, "minutes_valid": minutes_valid})
    html_body = None

    try:
        # Fire-and-forget: start a background thread so the HTTP request is not blocked
        send_email_background(subject, body, [email], html_body=html_body, from_email=settings.DEFAULT_FROM_EMAIL)
        return True
    except Exception as e:
        print("send_login_code_email error:", e)
        print(traceback.format_exc())
        return False


# -----------------------
# JWT helper
# -----------------------
def user_tokens_for_user(user):
    """
    Return dict with refresh & access tokens for a user using SimpleJWT.
    """
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


# -----------------------
# Websocket notifications
# -----------------------
def emit_ws_notification(user=None, title="", message="", payload=None):
    """
    Send a websocket notification:
      - If `user` provided, send to group "user_<id>"
      - Otherwise broadcast to "broadcast" group
    Uses channel_layer.group_send with type 'notify' (the consumer should handle notify).
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            # no channel layer configured
            print("emit_ws_notification: channel_layer is None (not configured)")
            return False

        data = {
            "type": "notify",
            "title": title,
            "message": message,
            "payload": payload or {},
            "created_at": timezone.now().isoformat(),
        }
        if user:
            group = f"user_{user.id}"
            async_to_sync(channel_layer.group_send)(group, data)
        else:
            async_to_sync(channel_layer.group_send)("broadcast", data)
        return True
    except Exception as e:
        print("emit_ws_notification error:", e)
        print(traceback.format_exc())
        return False
