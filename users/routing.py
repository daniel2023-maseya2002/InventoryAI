# users/routing.py
from django.urls import path
from .consumers import NotificationConsumer

# simple fixed route: ws://.../ws/notifications/
websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
