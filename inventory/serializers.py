from rest_framework import serializers
from .models import Product, StockLog, Notification
from django.contrib.auth import get_user_model


User = get_user_model()

class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


class ProductSerializer(serializers.ModelSerializer):
    total_value = serializers.SerializerMethodField()
    last_price_updated_by = SimpleUserSerializer(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            "id","sku","name","category","description","purchase_price","selling_price",
            "quantity","supplier","barcode","low_stock_threshold","reorder_qty",
            "image","last_price_updated_by","created_at","updated_at","total_value"
        ]
        read_only_fields = ["id","created_at","updated_at","total_value","last_price_updated_by"]

    def get_total_value(self, obj):
        # return numeric value (float) for convenience to frontend
        try:
            return float(obj.quantity) * float(obj.purchase_price)
        except Exception:
            return None

    def validate_image(self, image):
        if image is None:
            return image
        # max size 3MB (change if you want)
        max_size = 3 * 1024 * 1024
        if image.size > max_size:
            raise serializers.ValidationError("Image file too large (max 3 MB).")
        # allowed content types
        valid_types = ["image/jpeg", "image/png"]
        if hasattr(image, "content_type") and image.content_type not in valid_types:
            raise serializers.ValidationError("Unsupported image type. Use JPEG or PNG.")
        return image

class StockLogSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    user = SimpleUserSerializer(read_only=True)

    class Meta:
        model = StockLog
        fields = ["id","product","user","change_amount","reason","resulting_quantity","reference","created_at"]
        read_only_fields = ["id","created_at","resulting_quantity","user"]

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id","user","type","title","message","payload","is_read","created_at"]
        read_only_fields = ["id","created_at"]
