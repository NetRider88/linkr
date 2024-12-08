from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
import json
from .models import (
    SubscriptionTier, 
    UserSubscription, 
    Link, 
    LinkVariable,
    Click,  # Add this import
    ClickVariable,  # Add this if you need it for variable tracking
    UserProfile  # Add this import
)
from .utils.paypal import PayPalClient
from .forms import LinkForm
import random
import string
from django.db import IntegrityError
from django.http import HttpResponse
import csv
import pandas as pd
from datetime import datetime
from django.db.models import Count  # Add this import
from django.db.models import DateField
from django.db.models.functions import TruncDay
from django.db import models  # Add this import
from django.http import Http404
from user_agents import parse
import uuid
import geoip2.database  # Add this import
from django.contrib.gis.geoip2 import GeoIP2  # Add this import
from ip2geotools.databases.noncommercial import DbIpCity
from .forms import UserProfileForm  # Add this import
from .forms import SignupForm  # Import SignupForm from forms.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import transaction  # Add this import
from django.http import JsonResponse  # Add this import
import logging
from django.contrib.auth import update_session_auth_hash
from decimal import Decimal

logger = logging.getLogger(__name__)

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('home')  # Always redirect to home after login
        
    def form_invalid(self, form):
        messages.error(self.request, 'Invalid email or password. Please try again.')
        return super().form_invalid(form)

def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('home')
    return redirect('home')

def home(request):
    if request.user.is_authenticated:
        links = Link.objects.filter(user=request.user).order_by('-created_at')
        name = request.user.userprofile.get_full_name()
        context = {
            'links': links,
            'name': name,
            'total_clicks': Click.objects.filter(link__user=request.user).count(),
            'total_links': links.count()
        }
        return render(request, 'tracker/home.html', context)
    return render(request, 'tracker/home_public.html')

def signup(request):
    tiers = SubscriptionTier.objects.all().order_by('price')
    selected_tier = request.GET.get('tier')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = form.save(commit=False)
                    user.first_name = form.cleaned_data['first_name']
                    user.last_name = form.cleaned_data['last_name']
                    user.save()
                    
                    # Get or create subscription
                    tier = SubscriptionTier.objects.get(id=request.POST.get('tier'))
                    subscription, created = UserSubscription.objects.get_or_create(
                        user=user,
                        defaults={
                            'tier': tier,
                            'active': False,
                            'payment_status': 'pending'
                        }
                    )
                    
                    # Always login the user after creation
                    login(request, user)
                    
                    if tier.price == 0:
                        # Activate free tier immediately
                        subscription.active = True
                        subscription.payment_status = 'completed'
                        subscription.tier = tier
                        subscription.save()
                        return redirect('home')
                    else:
                        # Initialize PayPal client
                        paypal_client = PayPalClient()
                        approval_url = paypal_client.create_subscription(
                            user=user,
                            tier=tier,
                            request=request
                        )
                        
                        if approval_url:
                            return redirect(approval_url)
                        else:
                            messages.error(request, "Could not initialize payment. Please try again.")
                            return redirect('subscription_plans')
                    
            except Exception as e:
                messages.error(request, f"Error during signup: {str(e)}")
                return redirect('signup')
    else:
        form = SignupForm()
    
    return render(request, 'registration/signup.html', {
        'form': form,
        'tiers': tiers,
        'selected_tier': selected_tier,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID
    })

@login_required
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get accurate stats
    active_links_count = Link.objects.filter(user=request.user).count()
    total_clicks = Click.objects.filter(link__user=request.user).count()
    monthly_clicks = Click.objects.filter(
        link__user=request.user,
        timestamp__gte=timezone.now().replace(day=1, hour=0, minute=0, second=0)
    ).count()
    
    context = {
        'form': UserProfileForm(instance=user_profile),
        'active_links_count': active_links_count,
        'total_clicks': total_clicks,
        'monthly_clicks': monthly_clicks,
    }
    
    return render(request, 'tracker/profile.html', context)

def generate_short_id(length=6):
    """Generate a random short ID"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

from .decorators import payment_required

@login_required
@payment_required
def generate_link(request):
    # Check if user has an active subscription
    try:
        subscription = request.user.subscription
        if not subscription.active:
            subscription.active = True
            subscription.payment_status = 'completed'
            subscription.save()
            logger.info(f"Activated subscription for user {request.user.id}")
    except UserSubscription.DoesNotExist:
        # Create free subscription if none exists
        free_tier = SubscriptionTier.objects.get_or_create(
            name='FREE',
            defaults={
                'price': 0,
                'max_links': 5,
                'max_clicks': 1000,
                'is_default': True
            }
        )[0]
        subscription = UserSubscription.objects.create(
            user=request.user,
            tier=free_tier,
            active=True,
            payment_status='completed'
        )
        logger.info(f"Created new free subscription for user {request.user.id}")

    if request.method == 'POST':
        form = LinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.user = request.user
            
            # Try to generate a unique short_id
            max_attempts = 10
            for attempt in range(max_attempts):
                try:
                    link.short_id = generate_short_id()
                    link.save()
                    break
                except IntegrityError:
                    if attempt == max_attempts - 1:
                        messages.error(request, 'Unable to generate unique link ID. Please try again.')
                        return redirect('generate_link')
                    continue
            
            # Handle variables
            variable_names = request.POST.getlist('variable_names[]')
            variable_placeholders = request.POST.getlist('variable_placeholders[]')
            
            for name, placeholder in zip(variable_names, variable_placeholders):
                if name.strip() and placeholder.strip():
                    LinkVariable.objects.create(
                        link=link,
                        name=name.strip(),
                        placeholder=placeholder.strip()
                    )
            
            messages.success(request, 'Link created successfully!')
            return redirect('home')
    else:
        form = LinkForm()
    
    return render(request, 'tracker/generate_link.html', {'form': form})

@login_required
def delete_link(request, short_id):
    Link.objects.filter(short_id=short_id, user=request.user).delete()
    return redirect('home')

def track_click(request, short_id):
    try:
        link = Link.objects.get(short_id=short_id)
        
        # Get real IP even in development
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        # Get user agent with better parsing
        user_agent_string = request.META.get('HTTP_USER_AGENT', '')
        try:
            user_agent = parse(user_agent_string)
            if user_agent.is_mobile:
                device_type = 'Mobile'
            elif user_agent.is_tablet:
                device_type = 'Tablet'
            elif user_agent.is_pc:
                device_type = 'Desktop'
            else:
                device_type = 'Other'
        except:
            device_type = 'Unknown'

        # Get country from IP
        country = 'Unknown'
        try:
            # Try using Django's GeoIP2 first
            geo = GeoIP2()
            geo_data = geo.city(ip_address)
            if geo_data and geo_data.get('country_name'):
                country = geo_data['country_name']
            else:
                # Fallback to ip2geotools
                response = DbIpCity.get(ip_address, api_key='free')
                country = response.country
        except:
            # If in development or IP is local
            if ip_address in ['127.0.0.1', 'localhost', '::1']:
                country = 'Local'
            else:
                logger.warning(f"Could not determine country for IP: {ip_address}")

        # Create click record
        click = Click.objects.create(
            link=link,
            ip_address=ip_address,
            user_agent=user_agent_string,
            device_type=device_type,
            country=country,
            weekday=timezone.now().weekday(),
            hour=timezone.now().hour,
            visitor_id=request.COOKIES.get('visitor_id', str(uuid.uuid4()))
        )

        # Process any URL parameters
        for var in link.variables.all():
            value = request.GET.get(var.name, '')
            if value:
                ClickVariable.objects.create(
                    click=click,
                    variable=var,
                    value=value
                )

        # Update click count
        link.total_clicks = models.F('total_clicks') + 1
        link.save()

        # Build response
        response = redirect(link.original_url)
        if 'visitor_id' not in request.COOKIES:
            response.set_cookie('visitor_id', click.visitor_id, max_age=365*24*60*60)
        
        return response

    except Link.DoesNotExist:
        raise Http404("Link not found")

@login_required
def analytics(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    
    # Limit to last 30 days by default
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=30)
    
    clicks = Click.objects.filter(
        link=link,
        timestamp__range=(start_date, end_date)
    ).order_by('-timestamp')
    
    # Calculate basic stats
    total_clicks = clicks.count()
    unique_visitors = clicks.values('visitor_id').distinct().count()
    monthly_clicks = clicks.count()  # Since we're already filtering for last 30 days
    avg_daily_clicks = round(total_clicks / max(1, (timezone.now() - link.created_at).days), 1)
    
    # Prepare time series data
    daily_clicks = (clicks
                   .annotate(day=TruncDay('timestamp'))
                   .values('day')
                   .annotate(count=Count('id'))
                   .order_by('day'))
    
    dates_labels = [entry['day'].strftime('%Y-%m-%d') for entry in daily_clicks]
    clicks_data = [entry['count'] for entry in daily_clicks]
    
    # Device distribution
    device_data = list(clicks.values('device_type')
                      .annotate(count=Count('id'))
                      .values_list('count', flat=True))
    device_labels = ['Desktop', 'Mobile', 'Tablet']
    
    # Weekday distribution (0 = Monday, 6 = Sunday)
    weekday_data = [clicks.filter(weekday=i).count() for i in range(7)]
    
    # Hourly distribution
    hourly_data = [clicks.filter(hour=i).count() for i in range(24)]
    
    # Get click details with variables
    click_details = []
    for click in clicks.select_related('link').prefetch_related('variables__variable')[:100]:
        variables = {cv.variable.name: cv.value for cv in click.variables.all()}
        click_details.append({
            'timestamp': click.timestamp,
            'country': click.country,
            'device_type': click.device_type,
            'referrer': click.referrer if hasattr(click, 'referrer') else None,
            'browser': click.browser if hasattr(click, 'browser') else None,
            'variables': variables
        })
    
    # Get link variables
    link_variables = link.variables.all()
    
    # Variable usage statistics
    variable_stats = {}
    if link_variables.exists():
        for var in link_variables:
            values = ClickVariable.objects.filter(
                click__in=clicks,
                variable=var
            ).values('value').annotate(
                count=Count('id')
            ).order_by('-count')[:5]  # Top 5 values
            
            variable_stats[var.name] = {
                'total_usage': sum(v['count'] for v in values),
                'top_values': [{'value': v['value'], 'count': v['count']} for v in values]
            }
    
    context = {
        'link': link,
        'total_clicks': total_clicks,
        'unique_visitors': unique_visitors,
        'monthly_clicks': monthly_clicks,
        'avg_daily_clicks': avg_daily_clicks,
        'clicks': click_details,
        'link_variables': link_variables,
        'variable_stats': variable_stats,
        
        # Chart data
        'dates_labels': json.dumps(dates_labels),
        'clicks_data': json.dumps(clicks_data),
        'device_labels': json.dumps(device_labels),
        'device_data': json.dumps(device_data),
        'weekday_data': json.dumps(weekday_data),
        'hourly_data': json.dumps(hourly_data),
    }
    
    return render(request, 'tracker/analytics.html', context)

@login_required
def export_analytics(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    
    # Get all clicks with their variables in a single query
    clicks = Click.objects.filter(link=link).prefetch_related(
        'variables__variable'
    ).order_by('-timestamp')
    
    # Get link variables for column headers
    link_variables = link.variables.all()
    
    # Prepare data
    data = []
    for click in clicks:
        # Base click data
        row = {
            'Time': click.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Location': click.country,
            'Device': click.device_type,
            'Referrer': 'Direct',  # Default value
            'Browser': 'Unknown',  # Default value
        }
        
        # Parse user agent for browser info if available
        if click.user_agent:
            try:
                # Simple browser detection
                user_agent = click.user_agent.lower()
                if 'firefox' in user_agent:
                    row['Browser'] = 'Firefox'
                elif 'chrome' in user_agent:
                    row['Browser'] = 'Chrome'
                elif 'safari' in user_agent:
                    row['Browser'] = 'Safari'
                elif 'edge' in user_agent:
                    row['Browser'] = 'Edge'
                elif 'opera' in user_agent:
                    row['Browser'] = 'Opera'
            except:
                pass
        
        # Add variables
        click_variables = {cv.variable.name: cv.value for cv in click.variables.all()}
        for var in link_variables:
            row[var.name] = click_variables.get(var.name, '')
            
        data.append(row)

    # Generate CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{link.name or link.short_id}_analytics_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    if data:
        writer = csv.DictWriter(response, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    return response

def subscription_plans(request):
    """Display subscription plans"""
    # Get all tiers ordered by price
    tiers = SubscriptionTier.objects.all().order_by('price')
    
    # Log the number of tiers found
    logger.info(f"Found {tiers.count()} subscription tiers")
    for tier in tiers:
        logger.info(f"Tier: {tier.name}, Price: ${tier.price}")
    
    current_subscription = None
    if request.user.is_authenticated:
        try:
            current_subscription = request.user.subscription
            # Ensure admin-created subscriptions are active
            if not current_subscription.active and not getattr(current_subscription, '_from_payment', False):
                current_subscription.active = True
                current_subscription.payment_status = 'completed'
                current_subscription.save()
        except UserSubscription.DoesNotExist:
            pass

    # Calculate savings for each tier
    for tier in tiers:
        if tier.price > 0:
            # Convert to Decimal for accurate calculations
            monthly_price = Decimal(str(tier.price))
            
            # Calculate yearly price (20% discount)
            if not tier.yearly_price:
                tier.yearly_price = monthly_price * 12 * Decimal('0.8')
            else:
                tier.yearly_price = Decimal(str(tier.yearly_price))
            
            # Calculate monthly equivalent of yearly price
            tier.monthly_equivalent = tier.yearly_price / 12
            
            # Calculate yearly savings
            tier.yearly_savings = (monthly_price * 12) - tier.yearly_price
        else:
            tier.yearly_price = Decimal('0')
            tier.monthly_equivalent = Decimal('0')
            tier.yearly_savings = Decimal('0')

    # Check if PayPal is properly configured
    paypal_configured = bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)
    if not paypal_configured:
        logger.error("PayPal credentials not configured")
        messages.warning(request, "Payment system is temporarily unavailable. Only free tier is available at the moment.")

    context = {
        'tiers': tiers,
        'current_subscription': current_subscription,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID if paypal_configured else None,
        'paypal_configured': paypal_configured,
    }
    
    return render(request, 'tracker/subscription/plans.html', context)

@login_required
def create_subscription(request, tier_id):
    try:
        logger.info(f"Creating subscription for user {request.user.id} with tier {tier_id}")
        
        # Validate PayPal configuration
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            logger.error("PayPal credentials not configured")
            return JsonResponse({
                'error': 'Payment system not configured'
            }, status=400)
            
        tier = SubscriptionTier.objects.get(id=tier_id)
        billing = request.GET.get('billing', 'monthly')
        
        logger.info(f"Found tier: {tier.name}, billing: {billing}")
        
        # Calculate amount based on billing period
        amount = str(tier.yearly_price if billing == 'yearly' else tier.price)
        logger.info(f"Calculated amount: {amount}")

        # Store subscription details in session
        request.session['pending_subscription'] = {
            'tier_id': tier_id,
            'billing': billing,
            'amount': amount
        }
        
        response_data = {
            'client_id': settings.PAYPAL_CLIENT_ID,
            'tier_name': tier.name,
            'amount': amount,
            'currency': 'USD',
            'billing': billing,
            'description': f"{tier.name} Plan - {billing.capitalize()} Billing"
        }
        logger.info(f"Sending response: {response_data}")
        
        return JsonResponse(response_data)
        
    except SubscriptionTier.DoesNotExist:
        logger.error(f"Tier {tier_id} not found")
        return JsonResponse({
            'error': 'Invalid subscription tier'
        }, status=404)
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e)
        }, status=400)

@login_required
def subscription_success(request):
    try:
        tier_id = request.session.get('pending_tier_id')
        billing_period = request.session.get('billing_period', 'monthly')
        
        logger.info(f"Processing successful subscription for user {request.user.id}, tier {tier_id}, billing {billing_period}")
        
        if not tier_id:
            logger.error("No pending tier ID found in session")
            messages.error(request, 'No pending subscription found.')
            return redirect('subscription_plans')
            
        tier = SubscriptionTier.objects.get(id=tier_id)
        logger.info(f"Found tier: {tier.name}")
        
        # Update subscription
        subscription, created = UserSubscription.objects.get_or_create(
            user=request.user,
            defaults={'tier': tier}
        )
        
        if not created:
            subscription.tier = tier
        
        subscription.active = True
        subscription.payment_status = 'completed'
        subscription.save()
        
        logger.info(f"Subscription {'created' if created else 'updated'} successfully")
        
        # Clear session data
        request.session.pop('pending_tier_id', None)
        request.session.pop('billing_period', None)
        
        messages.success(request, f'Successfully subscribed to {tier.name} plan!')
        return redirect('home')
        
    except Exception as e:
        logger.error(f"Subscription success error: {str(e)}", exc_info=True)
        messages.error(request, 'Error processing subscription.')
        return redirect('subscription_plans')

@login_required
def subscription_cancel(request):
    messages.info(request, 'Subscription process cancelled.')
    return redirect('subscription_plans')

def paypal_webhook(request):
    # This would contain PayPal webhook handling logic
    pass

@login_required
def change_subscription(request):
    return redirect('subscription_plans')

@login_required
def subscription_history(request):
    return render(request, 'tracker/subscription/history.html')

@login_required
def manage_variables(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    return render(request, 'tracker/manage_variables.html', {'link': link})

@login_required
def add_variable(request, short_id):
    if request.method == 'POST':
        link = get_object_or_404(Link, short_id=short_id, user=request.user)
        name = request.POST.get('name')
        placeholder = request.POST.get('placeholder')
        
        if name and placeholder:
            LinkVariable.objects.create(
                link=link,
                name=name,
                placeholder=placeholder
            )
            messages.success(request, 'Variable added successfully!')
        
    return redirect('manage_variables', short_id=short_id)

@login_required
def delete_variable(request, short_id, var_id):
    variable = get_object_or_404(LinkVariable, id=var_id, link__short_id=short_id, link__user=request.user)
    variable.delete()
    messages.success(request, 'Variable deleted successfully!')
    return redirect('manage_variables', short_id=short_id)

# Add signal to create default subscription for new users
# tracker/models.py
@receiver(post_save, sender=User)
def create_default_subscription(sender, instance, created, **kwargs):
    """Create free subscription for new users"""
    if created:
        try:
            free_tier = SubscriptionTier.objects.get_or_create(
                name='FREE',
                defaults={
                    'price': 0,
                    'max_links': 5,
                    'max_clicks': 1000,
                    'is_default': True
                }
            )[0]
            subscription = UserSubscription.objects.create(
                user=instance,
                tier=free_tier,
                active=True,
                payment_status='completed'
            )
            logger.info(f"Created free subscription for user {instance.id}")
        except Exception as e:
            logger.error(f"Error creating free subscription: {str(e)}")

@login_required
def dashboard(request):
    """Dashboard view showing user's links and basic analytics"""
    user_links = Link.objects.filter(user=request.user).order_by('-created_at')
    total_clicks = Click.objects.filter(link__user=request.user).count()
    recent_clicks = Click.objects.filter(
        link__user=request.user
    ).order_by('-timestamp')[:10]

    context = {
        'links': user_links,
        'total_clicks': total_clicks,
        'recent_clicks': recent_clicks,
        'subscription': request.user.subscription,
    }
    return render(request, 'tracker/dashboard.html', context)

@login_required
def update_profile(request):
    """Update user profile information"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return redirect('profile')

@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        user = request.user
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        # Verify current password
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('profile')

        # Verify new passwords match
        if new_password1 != new_password2:
            messages.error(request, 'New passwords do not match.')
            return redirect('profile')

        # Validate password strength
        if len(new_password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('profile')

        # Change password
        user.set_password(new_password1)
        user.save()

        # Update session to prevent logout
        update_session_auth_hash(request, user)

        messages.success(request, 'Password changed successfully!')
        return redirect('profile')

    return redirect('profile')

@receiver(post_save, sender=UserSubscription)
def activate_admin_subscription(sender, instance, created, **kwargs):
    """Automatically activate subscriptions created from admin panel"""
    if created and instance.tier:
        # If it's a free tier or created from admin panel, activate it
        if instance.tier.price == 0 or not getattr(instance, '_from_payment', False):
            instance.active = True
            instance.payment_status = 'completed'
            instance.save()