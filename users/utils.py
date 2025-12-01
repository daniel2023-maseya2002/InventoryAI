# users/utils.py
from django.core.mail import EmailMessage
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

def send_login_code_email(email, code, minutes_valid=15):
    """
    Sends the numeric code to the user's email. Customize the template as needed.
    """
    subject = f"{getattr(settings, 'SHOP_NAME', 'Inventory')} — Your login code"
    body = (
        f"Your login code is: {code}\n\n"
        f"This code is valid for {minutes_valid} minutes.\n"
        "If you did not request this code, ignore this email.\n\n"
        "— The Team"
    )
    email_msg = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
    email_msg.send(fail_silently=False)

def user_tokens_for_user(user):
    """
    Return dict with refresh & access tokens for a user using SimpleJWT.
    """
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}
