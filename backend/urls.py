from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from inventory.views import ProductViewSet, StockLogViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny

schema_view = get_schema_view(
   openapi.Info(
      title="Inventory AI API",
      default_version='v1',
      description="Inventory AI System Backend",
   ),
   public=True,
   permission_classes=[AllowAny],
)


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

    # include ai app routes
    path("api/ai/", include("ai.urls")),

    # JWT auth endpoints
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
