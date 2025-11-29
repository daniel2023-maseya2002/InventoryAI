from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from inventory.views import ProductViewSet, StockLogViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"stock-logs", StockLogViewSet, basename="stocklog")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    
    # include inventory app routes
    path('api/', include('inventory.urls')),

    # include users app routes
    path('api/', include('users.urls')),

    # JWT auth endpoints
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
