# tracker/utils/analytics/plotly_utils.py

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from django.db.models import Count

def create_analytics_dashboard(clicks, variables):
    """Create main analytics dashboard with multiple plots"""
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

    add_device_distribution(fig, clicks)
    add_time_distributions(fig, clicks)
    add_variable_distribution(fig, variables)
    
    return fig

def add_device_distribution(fig, clicks):
    """Add device type pie chart"""
    device_data = clicks.values('device_type').annotate(count=Count('id'))
    fig.add_trace(
        go.Pie(
            labels=[d['device_type'] for d in device_data],
            values=[d['count'] for d in device_data],
            name='Device Types'
        ), 
        row=1, col=2
    )

def add_time_distributions(fig, clicks):
    """Add time-based bar charts"""
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = clicks.values('weekday').annotate(count=Count('id')).order_by('weekday')
    
    fig.add_trace(
        go.Bar(
            x=[weekday_names[d['weekday']] for d in weekday_data],
            y=[d['count'] for d in weekday_data],
            name='Clicks by Day'
        ), 
        row=2, col=1
    )

    hour_data = clicks.values('hour').annotate(count=Count('id')).order_by('hour')
    fig.add_trace(
        go.Bar(
            x=[f"{d['hour']:02d}:00" for d in hour_data],
            y=[d['count'] for d in hour_data],
            name='Clicks by Hour'
        ), 
        row=2, col=2
    )

def add_variable_distribution(fig, variables):
    """Add variable values distribution"""
    if variables:
        variable_data = []
        for var in variables:
            variable_data.extend([{
                'Variable': var.name,
                'Value': value['value'],
                'Count': value['count']
            } for value in var.clickvariable_set.values('value')
                .annotate(count=Count('id'))
                .order_by('-count')])
        
        if variable_data:
            fig.add_trace(
                go.Bar(
                    x=[f"{d['Variable']}: {d['Value']}" for d in variable_data],
                    y=[d['Count'] for d in variable_data],
                    name='Variable Values'
                ),
                row=3, col=1
            )