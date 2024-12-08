from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from urllib.parse import urlencode
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    class Meta:
        swappable = 'AUTH_USER_MODEL'

class Link(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    original_url = models.URLField()
    short_id = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_clicks = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.short_id} -> {self.original_url}"

    def get_short_url(self):
        base_url = f"http://localhost:8000/tracker/{self.short_id}"
        # If there are any variables, use the Braze placeholder
        if self.variables.exists():
            variable = self.variables.first()
            return f"{base_url}?{variable.name}={variable.placeholder}"
        return base_url

class LinkVariable(models.Model):
    link = models.ForeignKey(Link, related_name='variables', on_delete=models.CASCADE)
    name = models.CharField(max_length=50)  # e.g., "vendor_id", "campaign_id"
    placeholder = models.CharField(max_length=100)  # e.g., "{{custom_attribute.${vendor_name}}}"

    def __str__(self):
        return f"{self.name} ({self.placeholder})"

class Click(models.Model):
    link = models.ForeignKey(Link, related_name='clicks', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    country = models.CharField(max_length=100, default='Unknown')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=50, default='Unknown')
    weekday = models.IntegerField(default=0)  # 0-6 for Monday-Sunday
    hour = models.IntegerField(default=0)     # 0-23
    visitor_id = models.CharField(max_length=100)  # For tracking unique clicks

    class Meta:
        indexes = [
            models.Index(fields=['link', 'visitor_id']),  # For efficient unique click counting
        ]

    def __str__(self):
        return f"Click on {self.link.short_id} at {self.timestamp}"

    @property
    def created_at(self):
        return self.timestamp

class ClickVariable(models.Model):
    click = models.ForeignKey(Click, related_name='variables', on_delete=models.CASCADE)
    variable = models.ForeignKey(LinkVariable, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)  # The actual value received

    def __str__(self):
        return f"{self.variable.name}: {self.value}"

    class Meta:
        indexes = [
            models.Index(fields=['variable', 'value']),  # For efficient analytics queries
        ]

class SubscriptionTier(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_links = models.IntegerField(default=5)
    max_clicks = models.IntegerField(default=1000)
    retention_days = models.IntegerField(default=30)
    max_variables = models.IntegerField(default=0)
    allow_export = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    custom_domain = models.BooleanField(default=False)
    team_members = models.IntegerField(default=1)
    is_default = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} (${self.price}/month)"

    def get_yearly_savings(self):
        if not self.yearly_price:
            return 0
        return (self.price * 12) - self.yearly_price

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.user.email}'s profile"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

class UserSubscription(models.Model):
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    )
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    tier = models.ForeignKey(SubscriptionTier, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)  # Changed default to False
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    paypal_subscription_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.email}'s {self.tier.name} subscription"

    def has_reached_link_limit(self):
        return self.user.link_set.count() >= self.tier.max_links

    def has_reached_click_limit(self):
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        monthly_clicks = Click.objects.filter(
            link__user=self.user,
            timestamp__gte=month_start
        ).count()
        return monthly_clicks >= self.tier.max_clicks

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile for new users"""
    if created:
        UserProfile.objects.create(
            user=instance,
            first_name=instance.first_name,
            last_name=instance.last_name
        )

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """Update UserProfile when User is saved"""
    try:
        instance.userprofile.first_name = instance.first_name
        instance.userprofile.last_name = instance.last_name
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(
            user=instance,
            first_name=instance.first_name,
            last_name=instance.last_name
        )

# Create management command to create subscriptions for existing users
# tracker/management/commands/create_missing_subscriptions.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create subscriptions for users without one'

    def handle(self, *args, **kwargs):
        users_without_subscription = CustomUser.objects.filter(subscription__isnull=True)
        default_tier = SubscriptionTier.objects.get_or_create(
            name='FREE',
            defaults={
                'price': 0,
                'max_links': 5,
                'max_clicks': 1000,
                'is_default': True
            }
        )[0]
        
        for user in users_without_subscription:
            UserSubscription.objects.create(user=user, tier=default_tier)
            self.stdout.write(f'Created subscription for {user.email}')
