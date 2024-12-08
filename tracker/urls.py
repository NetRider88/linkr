from django.urls import path
from django.views.generic.base import RedirectView
from . import views

urlpatterns = [
    # Public URLs
    path('', views.home, name='index'),  # Direct to home view instead of redirect
    path('home/', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('subscription/plans/', views.subscription_plans, name='subscription_plans'),
    
    # Protected URLs (require login)
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('generate/', views.generate_link, name='generate_link'),
    path('delete/<str:short_id>/', views.delete_link, name='delete_link'),
    # Core URLs
    path('link/<str:short_id>/variables/', views.manage_variables, name='manage_variables'),
    path('link/<str:short_id>/variables/add/', views.add_variable, name='add_variable'),
    path('link/<str:short_id>/variables/<int:var_id>/delete/', views.delete_variable, name='delete_variable'),
    
    # Analytics
    path('analytics/<str:short_id>/', views.analytics, name='analytics'),
    path('analytics/<str:short_id>/export/', views.export_analytics, name='export_analytics'),
    
    # Subscription Management
    path('subscription/create/<int:tier_id>/', views.create_subscription, name='create_subscription'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('subscription/webhook/', views.paypal_webhook, name='paypal_webhook'),
    path('subscription/change/', views.change_subscription, name='change_subscription'),
    path('subscription/history/', views.subscription_history, name='subscription_history'),
    
    # Move track_click to bottom to avoid conflicting with other short_id patterns
    path('<str:short_id>/', views.track_click, name='track_click'),
]
