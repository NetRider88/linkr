from django.contrib import admin
from django.urls import path, include
from tracker import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/', include('django.contrib.auth.urls')),  # Include auth URLs
    path('accounts/signup/', views.signup, name='signup'),
    path('generate/', views.generate_link, name='generate_link'),
    path('analytics/<str:short_id>/', views.analytics, name='analytics'),
    path('<str:short_id>/', views.redirect_link, name='redirect_link'),
]
