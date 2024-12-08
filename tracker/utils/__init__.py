# tracker/utils/subscription_utils.py

from django.core.cache import cache
from django.conf import settings

def get_subscription_limits(user):
    """Get current subscription limits for a user"""
    cache_key = f'subscription_limits_{user.id}'
    limits = cache.get(cache_key)
    
    if not limits:
        try:
            subscription = user.subscription
            limits = {
                'max_links': subscription.tier.max_links,
                'max_clicks': subscription.tier.max_clicks,
                'max_variables': subscription.tier.max_variables,
                'allow_export': subscription.tier.allow_export,
                'api_access': subscription.tier.api_access
            }
        except:
            # Default free tier limits from settings
            limits = {
                'max_links': settings.SUBSCRIPTION_SETTINGS['FREE_TIER_LINKS'],
                'max_clicks': settings.SUBSCRIPTION_SETTINGS['FREE_TIER_CLICKS'],
                'max_variables': 0,  
                'allow_export': False,
                'api_access': False
            }
        cache.set(cache_key, limits, 300)  # Cache for 5 minutes
        
    return limits