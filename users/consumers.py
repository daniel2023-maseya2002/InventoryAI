# users/consumers.py
import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

# Note: do NOT call get_user_model() at module import time or import
# rest_framework_simplejwt.tokens at top-level. We'll import them lazily
# inside connect() so Django apps are already loaded.

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # parse token from query string ?token=...
        qs = parse_qs(self.scope.get("query_string", b"").decode())
        token_list = qs.get("token") or qs.get("access") or []
        token = token_list[0] if token_list else None

        if not token:
            # no token provided — reject connection
            await self.close(code=4001)
            return

        # Lazy import: do token validation and get_user_model only here (runtime)
        try:
            from rest_framework_simplejwt.tokens import AccessToken  # lazy
            from django.contrib.auth import get_user_model  # lazy
        except Exception:
            # If these imports fail, reject the connection
            await self.close(code=4002)
            return

        # Validate token
        try:
            access = AccessToken(token)
            user_id = access.get("user_id")
            if not user_id:
                raise ValueError("no user_id in token")
        except Exception:
            await self.close(code=4003)
            return

        # Get User model and fetch the user (async DB call)
        User = get_user_model()
        try:
            # Use database_sync_to_async to avoid blocking the event loop
            self.user = await database_sync_to_async(User.objects.get)(id=user_id)
        except Exception:
            await self.close(code=4004)
            return

        # Join user-specific group + broadcast group
        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.channel_layer.group_add("broadcast", self.channel_name)

        await self.accept()

    async def disconnect(self, code):
        try:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
            await self.channel_layer.group_discard("broadcast", self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
        # optional: handle incoming messages (e.g., mark notification read)
        # simple echo for debug
        await self.send_json({"echo": content})

    # Handler name must match the 'type' used when group_send: 'notify'
    async def notify(self, event):
        # forward the event to the websocket client
        await self.send_json({
            "type": "notification",
            "title": event.get("title"),
            "message": event.get("message"),
            "payload": event.get("payload"),
            "created_at": event.get("created_at"),
        })
    