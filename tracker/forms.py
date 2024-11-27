# tracker/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import Link

class LinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ['original_url', 'name']
        widgets = {
            'original_url': forms.URLInput(attrs={'placeholder': 'https://example.com?var={variable_name}'}),
            'name': forms.TextInput(attrs={'placeholder': 'My Link'})
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
