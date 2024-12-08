# tracker/templatetags/link_tags.py
from django import template

register = template.Library()

@register.simple_tag
def remaining_links(user):
    """Calculate remaining links for user's subscription"""
    try:
        max_links = user.subscription.tier.max_links
        used_links = user.link_set.count()
        return max_links - used_links
    except:
        return 0