# tracker/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.urls import path
from django.db.models.functions import TruncDay
from django.utils import timezone
from django.contrib.admin import SimpleListFilter
from .models import (
    UserProfile, UserSubscription, Link, Click, 
    ClickVariable, SubscriptionTier
)

# Custom filters
class SubscriptionTypeFilter(SimpleListFilter):
    title = 'subscription type'
    parameter_name = 'sub_type'

    def lookups(self, request, model_admin):
        return [
            ('free', 'Free'),
            ('paid', 'Paid'),
            ('none', 'No Subscription')
        ]

    def queryset(self, request, queryset):
        if self.value() == 'free':
            return queryset.filter(subscription__tier__price=0)
        if self.value() == 'paid':
            return queryset.filter(subscription__tier__price__gt=0)
        if self.value() == 'none':
            return queryset.filter(subscription__isnull=True)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'get_full_name', 'get_email', 
        'get_subscription_tier', 'get_links_count', 
        'get_total_clicks', 'get_monthly_clicks'
    )
    search_fields = ('user__username', 'user__email', 'first_name', 'last_name')
    list_filter = ('user__subscription__tier', SubscriptionTypeFilter)

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

    def get_subscription_tier(self, obj):
        try:
            return obj.user.subscription.tier.name
        except:
            return 'No subscription'
    get_subscription_tier.short_description = 'Plan'

    def get_links_count(self, obj):
        return Link.objects.filter(user=obj.user).count()
    get_links_count.short_description = 'Links'

    def get_total_clicks(self, obj):
        return Click.objects.filter(link__user=obj.user).count()
    get_total_clicks.short_description = 'Total Clicks'

    def get_monthly_clicks(self, obj):
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        return Click.objects.filter(
            link__user=obj.user,
            timestamp__gte=month_start
        ).count()
    get_monthly_clicks.short_description = 'Monthly Clicks'

class ClickInline(admin.TabularInline):
    model = Click
    extra = 0
    readonly_fields = ('timestamp', 'ip_address', 'country', 'device_type')
    can_delete = False
    max_num = 0

@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = (
        'short_id', 'user', 'original_url', 
        'created_at', 'total_clicks', 'get_click_rate'
    )
    search_fields = ('short_id', 'original_url', 'user__username')
    list_filter = ('created_at', 'user__subscription__tier')
    readonly_fields = ('created_at', 'total_clicks', 'analytics_chart')
    inlines = [ClickInline]

    def get_variables(self, obj):
        variables = obj.variables.all()
        return ", ".join([f"{v.name}={v.placeholder}" for v in variables])
    get_variables.short_description = 'Variables'

    def analytics_chart(self, obj):
        clicks = Click.objects.filter(link=obj)\
            .annotate(day=TruncDay('timestamp'))\
            .values('day')\
            .annotate(count=Count('id'))\
            .order_by('day')
        
        # Generate simple ASCII chart
        if clicks:
            return format_html(
                '<pre style="font-size:12px">{}</pre>',
                '\n'.join([f"{c['day'].strftime('%Y-%m-%d')}: {'█' * (c['count']//5)}" for c in clicks])
            )
        return "No clicks yet"
    analytics_chart.short_description = 'Click Analytics'

    def get_click_rate(self, obj):
        """Calculate daily average click rate"""
        days_active = (timezone.now() - obj.created_at).days or 1
        daily_rate = obj.total_clicks / days_active
        # Use str.format() instead of f-string for SafeString
        return format_html(
            '<span title="Average clicks per day">{}/day</span>',
            '{:.1f}'.format(daily_rate)
        )
    get_click_rate.short_description = 'Click Rate'

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'tier', 'active', 'start_date', 
        'end_date', 'paypal_subscription_id',
        'get_usage_percentage'
    )
    list_filter = ('active', 'tier', 'start_date')
    search_fields = ('user__username', 'user__email')
    actions = ['cancel_subscription', 'activate_subscription']
    readonly_fields = ('start_date',)

    def get_usage_percentage(self, obj):
        monthly_clicks = Click.objects.filter(
            link__user=obj.user,
            timestamp__gte=timezone.now().replace(day=1)
        ).count()
        if obj.tier.max_clicks:
            percentage = (monthly_clicks / obj.tier.max_clicks) * 100
            return format_html(
                '<div style="width:100px;background:#eee;"><div style="width:{}%;background:{};height:10px;"></div></div>',
                min(100, percentage),
                '#28a745' if percentage < 80 else '#dc3545'
            )
        return 'N/A'
    get_usage_percentage.short_description = 'Usage'

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ('link', 'timestamp', 'country', 'device_type', 'ip_address')
    list_filter = ('timestamp', 'country', 'device_type')
    search_fields = ('link__short_id', 'link__user__username')
    date_hierarchy = 'timestamp'

@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'price', 'max_links', 'max_clicks',
        'get_active_users', 'get_total_revenue'
    )
    search_fields = ('name',)
    list_filter = ('allow_export', 'api_access', 'custom_domain')

    def get_active_users(self, obj):
        return UserSubscription.objects.filter(tier=obj, active=True).count()
    get_active_users.short_description = 'Active Users'

    def get_total_revenue(self, obj):
        active_subs = UserSubscription.objects.filter(tier=obj, active=True).count()
        return f"${active_subs * float(obj.price):.2f}/mo"
    get_total_revenue.short_description = 'Monthly Revenue'

# Customize admin site
admin.site.site_header = 'Link DNA Administration'
admin.site.site_title = 'Link DNA Admin Portal'
admin.site.index_title = 'Management Dashboard'
