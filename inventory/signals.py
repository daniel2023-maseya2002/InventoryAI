# inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
from .utils import create_notification

@receiver(post_save, sender=Product)
def product_post_save(sender, instance: Product, created, **kwargs):
    # If created, maybe no need to notify about low stock.
    if created:
        return

    # when updated, check if quantity is now at/below threshold
    try:
        qty = instance.quantity
        if qty <= instance.low_stock_threshold:
            # notify admins and broadcast
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(role="admin")
            for admin in admins:
                create_notification(
                    user=admin,
                    type="low_stock",
                    title=f"Low stock: {instance.name}",
                    message=f"Product '{instance.name}' quantity is {qty} (threshold {instance.low_stock_threshold}).",
                    payload={"product_id": str(instance.id), "quantity": qty, "threshold": instance.low_stock_threshold},
                    send_email=False
                )
            create_notification(
                user=None,
                type="low_stock",
                title=f"Low stock: {instance.name}",
                message=f"Product '{instance.name}' quantity is {qty} (threshold {instance.low_stock_threshold}).",
                payload={"product_id": str(instance.id), "quantity": qty, "threshold": instance.low_stock_threshold},
                send_email=False
            )
    except Exception:
        pass
