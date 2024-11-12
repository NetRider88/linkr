from django.shortcuts import render, redirect, get_object_or_404
from .models import Link, Click
from django.utils.crypto import get_random_string
import requests
import plotly.express as px
from django.db.models import Count
from django.utils.dateparse import parse_datetime
import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm

def home(request):
    if request.user.is_authenticated:
        links = Link.objects.filter(user=request.user).order_by('-created_at')
        for link in links:
            link.total_clicks = link.clicks.count()
        return render(request, 'tracker/home.html', {'links': links})
    else:
        return render(request, 'tracker/home_public.html')

@login_required
def generate_link(request):
    if request.method == 'POST':
        original_url = request.POST['original_url']
        name = request.POST.get('name', '')
        short_id = get_random_string(6)
        link = Link.objects.create(
            user=request.user,  # Associate link with current user
            original_url=original_url, 
            short_id=short_id,
            name=name
        )
        return render(request, 'tracker/link_created.html', {
            'short_id': short_id,
            'full_url': f"{request.scheme}://{request.get_host()}/{short_id}/"
        })
    return render(request, 'tracker/generate.html')

def redirect_link(request, short_id):
    link = get_object_or_404(Link, short_id=short_id)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ip_address = request.META.get('REMOTE_ADDR')
    response = requests.get(f'https://freegeoip.app/json/{ip_address}')
    country = response.json().get('country_name', 'Unknown')
    Click.objects.create(
        link=link,
        user_agent=user_agent,
        ip_address=ip_address,
        country=country
    )
    return redirect(link.original_url)

@login_required
def analytics(request, short_id=None):
    links = Link.objects.filter(user=request.user).order_by('-created_at')
    selected_link = None
    clicks = []
    graph_json = None

    selected_short_id = request.GET.get('short_id', short_id)
    if selected_short_id:
        selected_link = get_object_or_404(Link, short_id=selected_short_id, user=request.user)
        clicks = selected_link.clicks.all()

        # Apply date filters if present
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = parse_datetime(start_date)
            clicks = clicks.filter(timestamp__gte=start_date)
        if end_date:
            end_date = parse_datetime(end_date)
            clicks = clicks.filter(timestamp__lte=end_date)

        # Create graph data
        country_data = clicks.values('country').annotate(count=Count('id')).order_by('-count')
        if country_data:
            df = pd.DataFrame(country_data)
            if not df.empty:
                fig = px.bar(
                    data_frame=df,
                    x='country',
                    y='count',
                    labels={'country': 'Country', 'count': 'Number of Clicks'},
                    title='Clicks by Country'
                )
                fig.update_layout(
                    xaxis_title='Country',
                    yaxis_title='Number of Clicks',
                    bargap=0.2
                )
                graph_json = fig.to_json()

    return render(request, 'tracker/analytics.html', {
        'links': links,
        'selected_link': selected_link,
        'clicks': clicks,
        'graph_json': graph_json
    })

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})
