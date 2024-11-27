from django.contrib.auth.models import User
from django.db import models
from urllib.parse import urlencode

class Link(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
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
