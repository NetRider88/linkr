# tracker/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import Link, LinkVariable, UserProfile
from django.contrib.auth.forms import UserCreationForm

class LinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ['original_url', 'name']
        widgets = {
            'original_url': forms.URLInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

    def clean_original_url(self):
        url = self.cleaned_data['original_url']
        if not url:
            raise forms.ValidationError("Please enter a valid URL")
        return url

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class VariableForm(forms.ModelForm):
    class Meta:
        model = LinkVariable
        fields = ['name', 'placeholder']

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        # Remove username field as we'll use email
        if 'username' in self.fields:
            del self.fields['username']
            
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Use email as username
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class SignupForm(CustomUserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta(CustomUserCreationForm.Meta):
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')
