# backend/asgi.py
import os

# MUST set DJANGO_SETTINGS_MODULE before importing Django internals
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# import websocket routing AFTER settings are configured
import users.routing as users_routing

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            users_routing.websocket_urlpatterns
        )
    ),
})
