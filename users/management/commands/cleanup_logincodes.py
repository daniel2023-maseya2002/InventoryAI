# users/management/commands/cleanup_logincodes.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
import logging

from users.models import LoginCode

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Delete login codes older than X days and used codes."

    def handle(self, *args, **options):
        try:
            cleanup_days = int(getattr(settings, "LOGIN_CODE_CLEANUP_DAYS", 30))
        except Exception:
            cleanup_days = 30

        older_than = timezone.now() - timedelta(days=cleanup_days)

        qs = LoginCode.objects.filter(Q(used=True) | Q(created_at__lt=older_than))
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {count} old/used LoginCode records"))
        logger.info("cleanup_logincodes removed %d records", count)
