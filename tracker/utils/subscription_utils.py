# tracker/utils/subscription_utils.py

from django.utils import timezone
from ..models import SubscriptionTier, UserSubscription

def create_free_subscription(user):
    """Create a free subscription for new users"""
    free_tier = SubscriptionTier.objects.get(name='FREE')
    return UserSubscription.objects.create(
        user=user,
        tier=free_tier,
        active=True
    )

def get_subscription_limits(user):
    """Get current subscription limits for a user"""
    try:
        subscription = user.subscription
        if subscription.is_active():
            return {
                'max_links': subscription.tier.max_links,
                'max_clicks': subscription.tier.max_clicks,
                'max_variables': subscription.tier.max_variables,
                'allow_export': subscription.tier.allow_export,
                'api_access': subscription.tier.api_access,
                'custom_domain': subscription.tier.custom_domain,
            }
    except UserSubscription.DoesNotExist:
        pass
    
    # Return free tier limits if no subscription exists
    return {
        'max_links': 5,
        'max_clicks': 1000,
        'max_variables': 0,
        'allow_export': False,
        'api_access': False,
        'custom_domain': False,
    }