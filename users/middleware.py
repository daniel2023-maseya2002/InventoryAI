# users/middleware.py
from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import close_old_connections
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

User = get_user_model()

class TokenAuthMiddleware(BaseMiddleware):
    """
    Custom Channels middleware that authenticates user from query string token or Authorization header.
    Usage: ws://.../ws/notifications/?token=<access_token>
    """
    async def __call__(self, scope, receive, send):
        # close old DB connections to avoid usage problems
        close_old_connections()
        query_string = scope.get("query_string", b"").decode()
        qs = parse_qs(query_string)
        token = None
        if "token" in qs:
            token = qs.get("token")[0]
        else:
            # optionally support Authorization header passed in subprotocols or header
            headers = dict((k.decode(), v.decode()) for k, v in scope.get("headers", []))
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1]

        if token:
            try:
                # Validate token with SimpleJWT
                untyped = UntypedToken(token)
                # If valid, find user (we get user id from token payload)
                jwt_obj = JWTAuthentication()
                validated = jwt_obj.get_validated_token(token)
                user = jwt_obj.get_user(validated)
                scope["user"] = user
            except Exception:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
