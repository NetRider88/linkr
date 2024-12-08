# tracker/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def payment_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
            
        try:
            subscription = request.user.subscription
            # Only check payment status for paid tiers
            if subscription.tier.price > 0 and (
                not subscription.active or 
                subscription.payment_status != 'completed'
            ):
                messages.warning(
                    request, 
                    'Please complete your payment to access this feature.'
                )
                return redirect('subscription_plans')
            
            # Check if user has reached their link limit
            from .models import Link
            current_links = Link.objects.filter(user=request.user).count()
            if current_links >= subscription.tier.max_links:
                messages.warning(
                    request,
                    f'You have reached your limit of {subscription.tier.max_links} links. Please upgrade your plan to create more links.'
                )
                return redirect('subscription_plans')
                
        except Exception as e:
            messages.error(request, 'Subscription error. Please contact support.')
            return redirect('subscription_plans')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view