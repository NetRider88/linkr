from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
import geoip2.database
from geoip2.errors import GeoIP2Error
import user_agents
from .models import Link, Click, LinkVariable, ClickVariable
from .forms import LinkForm, UserProfileForm
from django.contrib import messages
from django.utils import timezone
from django.http import Http404, HttpResponse
from django.utils.crypto import get_random_string
import plotly.express as px
from django.db.models import Count, Sum
from django.utils.dateparse import parse_datetime
import pandas as pd
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.db.models.functions import ExtractHour, ExtractWeekDay
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import string
import random
import hashlib
from urllib.parse import quote_plus, unquote_plus, urlparse, parse_qs, urlencode
import csv
import pandas as pd
from django.http import HttpResponse
from datetime import datetime

def home(request):
    if request.user.is_authenticated:
        links = Link.objects.filter(user=request.user).order_by('-created_at')
        for link in links:
            link.total_clicks = link.clicks.count()
            link.save()
        links = Link.objects.filter(user=request.user)
        total_clicks = links.aggregate(Sum('total_clicks'))['total_clicks__sum'] or 0
        
        return render(request, 'tracker/home.html', {
            'links': links,
            'total_clicks': total_clicks
        })
    else:
        return render(request, 'tracker/home_public.html')

@login_required
def generate_link(request):
    if request.method == 'POST':
        form = LinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.user = request.user
            
            # Parse the original URL
            parsed_url = urlparse(link.original_url)
            
            # Get variables from form
            variables = request.POST.getlist('variable_names[]')
            placeholders = request.POST.getlist('variable_placeholders[]')
            
            # Save the original URL without modifications
            link.original_url = link.original_url
            
            # Generate unique short_id
            characters = string.ascii_letters + string.digits
            while True:
                short_id = ''.join(random.choice(characters) for _ in range(6))
                if not Link.objects.filter(short_id=short_id).exists():
                    break
            link.short_id = short_id
            link.save()

            # Create LinkVariable objects
            for name, placeholder in zip(variables, placeholders):
                if name and placeholder:  # Only create if both fields are filled
                    # Validate Braze variable format
                    if (placeholder.startswith('{{custom_attribute.${') and 
                        placeholder.endswith('}}')):
                        LinkVariable.objects.create(
                            link=link,
                            name=name,
                            placeholder=placeholder
                        )

            # Refresh the link object to ensure we have the latest data including variables
            link.refresh_from_db()
            messages.success(request, f'Link created: {link.get_short_url()}')
            return redirect('home')
    else:
        form = LinkForm()
    return render(request, 'tracker/generate_link.html', {'form': form})

def create_click_record(request, link):
    # Get IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '').strip()

    # Handle localhost IPs for testing
    if ip_address in ('127.0.0.1', '::1', ''):
        ip_address = '8.8.8.8'  # Public IP for testing

    # Get country from IP using geoip2
    try:
        with geoip2.database.Reader(settings.GEOIP_PATH / 'GeoLite2-City.mmdb') as reader:
            response = reader.city(ip_address)
            country = response.country.name or 'Unknown'
    except (GeoIP2Error, Exception) as e:
        print(f"Geolocation error: {e}")
        country = 'Unknown'

    # Get device type from user agent
    user_agent_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = user_agents.parse(user_agent_string)

    if user_agent.is_mobile:
        device_type = 'Mobile'
    elif user_agent.is_tablet:
        device_type = 'Tablet'
    elif user_agent.is_pc:
        device_type = 'Desktop'
    else:
        device_type = 'Other'

    # Generate visitor ID from IP and user agent
    visitor_id = hashlib.md5(f"{ip_address}{user_agent_string}".encode()).hexdigest()

    # Create click record
    click = Click.objects.create(
        link=link,
        ip_address=ip_address,
        country=country,
        user_agent=user_agent_string,
        device_type=device_type,
        timestamp=timezone.now(),
        weekday=timezone.now().weekday(),
        hour=timezone.now().hour,
        visitor_id=visitor_id
    )

    return click

def track_click(request, short_id):
    link = get_object_or_404(Link, short_id=short_id)
    click = create_click_record(request, link)

    # Track variables
    for variable in link.variables.all():
        value = request.GET.get(variable.name, '')
        if value:
            # URL decode the value if needed
            try:
                decoded_value = unquote_plus(value)
            except Exception:
                decoded_value = value

            ClickVariable.objects.create(
                click=click,
                variable=variable,
                value=decoded_value
            )

    # Update total clicks
    link.total_clicks += 1
    link.save()

    return redirect(link.original_url)

def redirect_link(request, short_id):
    link = get_object_or_404(Link, short_id=short_id)
    
    # Create click record and track variables
    click = create_click_record(request, link)
    
    # Parse the original URL
    parsed_url = urlparse(link.original_url)
    
    # Get the first variable if it exists
    if link.variables.exists():
        variable = link.variables.first()
        # Use the variable name and its Braze placeholder
        query_params = {variable.name: variable.placeholder}
    else:
        query_params = {}
    
    # Track variables
    for variable in link.variables.all():
        value = request.GET.get(variable.name, '')
        if value:
            # Store the variable value (URL decoded)
            try:
                decoded_value = unquote_plus(value)
            except Exception:
                decoded_value = value

            ClickVariable.objects.create(
                click=click,
                variable=variable,
                value=decoded_value
            )
    
    # Reconstruct the URL with the Braze placeholder
    query_string = urlencode(query_params)
    final_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    if query_string:
        final_url += f"?{query_string}"
    
    # Update total clicks
    link.total_clicks += 1
    link.save()
            
    return redirect(final_url)

@login_required
def analytics(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    clicks = link.clicks.all().order_by('-timestamp')
    total_clicks = clicks.count()
    unique_clicks = clicks.values('visitor_id').distinct().count()

    # Create subplot figure
    fig = make_subplots(
        rows=3, cols=2,
        specs=[
            [{"type": "xy"}, {"type": "domain"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"colspan": 2, "type": "xy"}, None],
        ],
        subplot_titles=(
            'Clicks by Country', 'Device Types',
            'Clicks by Day of Week', 'Clicks by Hour',
            'Variable Values Distribution'
        )
    )

    # Add country distribution
    country_data = clicks.values('country').annotate(count=Count('id')).order_by('-count')
    fig.add_trace(go.Bar(x=[d['country'] for d in country_data],
                        y=[d['count'] for d in country_data],
                        name='Clicks by Country'), row=1, col=1)

    # Add device type distribution
    device_data = clicks.values('device_type').annotate(count=Count('id'))
    fig.add_trace(go.Pie(labels=[d['device_type'] for d in device_data],
                        values=[d['count'] for d in device_data],
                        name='Device Types'), row=1, col=2)

    # Add weekday distribution
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = clicks.values('weekday').annotate(count=Count('id')).order_by('weekday')
    fig.add_trace(go.Bar(x=[weekday_names[d['weekday']] for d in weekday_data],
                        y=[d['count'] for d in weekday_data],
                        name='Clicks by Day'), row=2, col=1)

    # Add hourly distribution
    hour_data = clicks.values('hour').annotate(count=Count('id')).order_by('hour')
    fig.add_trace(go.Bar(x=[f"{d['hour']:02d}:00" for d in hour_data],
                        y=[d['count'] for d in hour_data],
                        name='Clicks by Hour'), row=2, col=2)

    # Add variable values distribution
    variable_data = []
    for variable in link.variables.all():
        values = ClickVariable.objects.filter(
            variable=variable
        ).values('value').annotate(count=Count('id')).order_by('-count')
        for value in values:
            variable_data.append({
                'Variable': variable.name,
                'Value': value['value'],
                'Count': value['count']
            })

    if variable_data:
        df = pd.DataFrame(variable_data)
        fig.add_trace(go.Bar(x=[f"{row['Variable']}: {row['Value']}" for _, row in df.iterrows()],
                            y=df['Count'],
                            name='Variable Values'), row=3, col=1)

    # Update layout
    fig.update_layout(height=1200, showlegend=True, title_text="Link Analytics")

    # Get variable statistics
    variable_stats = []
    for variable in link.variables.all():
        values = ClickVariable.objects.filter(variable=variable)
        total_values = values.count()
        unique_values = values.values('value').distinct().count()
        top_values = values.values('value').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        variable_stats.append({
            'name': variable.name,
            'total_values': total_values,
            'unique_values': unique_values,
            'top_values': top_values
        })

    return render(request, 'tracker/analytics.html', {
        'link': link,
        'total_clicks': total_clicks,
        'unique_clicks': unique_clicks,
        'variable_stats': variable_stats,
        'graph_json': fig.to_json(),
        'clicks': clicks  # Added clicks to context for the detailed table
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

@login_required
def delete_link(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    link.delete()
    messages.success(request, 'Link deleted successfully.')
    return redirect('home')

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'tracker/profile.html', {'form': form})

def export_analytics(request, short_id):
    link = get_object_or_404(Link, short_id=short_id, user=request.user)
    clicks = Click.objects.filter(link=link).select_related('ip_info')

    # Prepare data
    data = []
    for click in clicks:
        row = {
            'Timestamp': click.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Country': click.ip_info.country if click.ip_info else 'Unknown',
            'City': click.ip_info.city if click.ip_info else 'Unknown',
            'IP': click.ip_address,
        }
        
        # Add variables if any
        click_vars = ClickVariable.objects.filter(click=click)
        for var in click_vars:
            row[f'Variable_{var.variable.name}'] = var.value
            
        data.append(row)

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="link_analytics_{short_id}_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.DictWriter(response, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        
        return response
    
    else:  # Excel format
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="link_analytics_{short_id}_{datetime.now().strftime("%Y%m%d")}.xlsx"'
        
        df.to_excel(response, index=False, engine='openpyxl')
        return response
