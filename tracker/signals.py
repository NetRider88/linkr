# tracker/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .utils.subscription_utils import create_free_subscription

@receiver(post_save, sender=User)
def create_user_subscription(sender, instance, created, **kwargs):
    """Create free subscription for new users"""
    if created:
        create_free_subscription(instance)