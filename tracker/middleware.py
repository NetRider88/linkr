# tracker/middleware.py
from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.contrib import messages
from django.conf import settings
from .models import UserSubscription, SubscriptionTier
import logging

logger = logging.getLogger(__name__)

class SubscriptionLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Define paths that are always accessible
        PUBLIC_PATHS = [
            '/tracker/login/',
            '/tracker/signup/',
            '/tracker/logout/',
            '/static/',
            '/media/',
            '/admin/',
            '/tracker/subscription/plans/',  # Allow public access to plans
            '/tracker/home/',  # Allow public access to home
        ]

        # Define paths that require authentication but not subscription
        AUTH_ONLY_PATHS = [
            '/tracker/profile/',
            '/tracker/profile/update/',
            '/tracker/profile/change-password/',
            '/tracker/subscription/create/',
            '/tracker/subscription/success/',
            '/tracker/subscription/cancel/',
            '/tracker/subscription/webhook/',
            '/tracker/subscription/history/',
        ]

        current_path = request.path
        resolved_url = resolve(request.path_info)

        # Allow public access to short links (track_click view)
        if resolved_url.url_name == 'track_click':
            return self.get_response(request)

        # Allow public paths
        if any(current_path.startswith(path) for path in PUBLIC_PATHS):
            return self.get_response(request)

        # Check authentication
        if not request.user.is_authenticated:
            return redirect('login')

        # Allow subscription management without checks
        if any(current_path.startswith(path) for path in AUTH_ONLY_PATHS):
            return self.get_response(request)

        # Check subscription for authenticated users
        try:
            subscription = request.user.subscription
            # Automatically activate subscription
            if not subscription.active:
                subscription.active = True
                subscription.payment_status = 'completed'
                subscription.save()
                logger.info(f"Activated subscription for user {request.user.id}")
                
        except UserSubscription.DoesNotExist:
            # Create a free subscription if none exists
            free_tier = SubscriptionTier.objects.get_or_create(
                name='FREE',
                defaults={
                    'price': 0,
                    'yearly_price': 0,
                    'max_links': 5,
                    'max_clicks': 1000,
                    'retention_days': 30,
                    'max_variables': 0,
                    'allow_export': False,
                    'api_access': False,
                    'custom_domain': False,
                    'team_members': 1,
                    'description': 'Basic link tracking'
                }
            )[0]
            subscription = UserSubscription.objects.create(
                user=request.user,
                tier=free_tier,
                active=True,
                payment_status='completed'
            )
            logger.info(f"Created free subscription for user {request.user.id}")
            messages.info(request, 'You have been assigned a free subscription plan.')

        return self.get_response(request)

class SubscriptionVerificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                subscription = request.user.subscription
                # Automatically activate subscription
                if not subscription.active:
                    subscription.active = True
                    subscription.payment_status = 'completed'
                    subscription.save()
                    logger.info(f"Activated subscription for user {request.user.id}")
            except UserSubscription.DoesNotExist:
                pass
        return self.get_response(request)

class PaymentVerificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip payment verification for track_click view
        try:
            resolved_url = resolve(request.path_info)
            if resolved_url.url_name == 'track_click':
                return self.get_response(request)
        except:
            pass

        if request.user.is_authenticated and not request.user.is_staff:
            current_url = resolve(request.path_info).url_name
            
            # URLs that don't require payment verification
            exempt_urls = [
                'subscription_plans',
                'subscription_success',
                'subscription_cancel',
                'logout',
                'profile',
                'update_profile',
                'change_password',
                'home',
                'track_click',
                'generate_link'  # Add generate_link to exempt URLs
            ]

            if current_url not in exempt_urls:
                try:
                    subscription = request.user.subscription
                    # Automatically activate subscription
                    if not subscription.active:
                        subscription.active = True
                        subscription.payment_status = 'completed'
                        subscription.save()
                        logger.info(f"Activated subscription for user {request.user.id}")
                except UserSubscription.DoesNotExist:
                    return redirect('subscription_plans')

        return self.get_response(request)

# tracker/utils/subscription_utils.py
from django.core.cache import cache
from django.db.models import Count
from datetime import datetime, timedelta

def get_subscription_limits(user):
    cache_key = f'subscription_limits_{user.id}'
    limits = cache.get(cache_key)
    
    if not limits:
        subscription = user.subscription
        limits = {
            'max_links': subscription.tier.max_links,
            'max_clicks': subscription.tier.max_clicks,
            'max_variables': subscription.tier.max_variables,
            'allow_export': subscription.tier.allow_export,
            'api_access': subscription.tier.api_access
        }
        cache.set(cache_key, limits, 300)  # Cache for 5 minutes
        
    return limits

def check_feature_access(feature_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            limits = get_subscription_limits(request.user)
            
            if not limits.get(f'allow_{feature_name}', False):
                messages.warning(request, f'Please upgrade your plan to use {feature_name}.')
                return redirect('subscription_plans')
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
