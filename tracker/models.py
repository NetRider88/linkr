from django.contrib.auth.models import User
from django.db import models

class Link(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='links')
    name = models.CharField(max_length=200, blank=True, null=True)
    original_url = models.URLField()
    short_id = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name or self.short_id} -> {self.original_url}"

class Click(models.Model):
    link = models.ForeignKey(Link, related_name='clicks', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.link.short_id} clicked at {self.timestamp}"
