# tracker/utils/analytics/stats.py
from django.db.models import Count
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def calculate_variable_stats(variable):
    """Calculate statistics for a link variable"""
    values = variable.clickvariable_set.all()
    total_values = values.count()
    unique_values = values.values('value').distinct().count()
    top_values = values.values('value').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    return {
        'name': variable.name,
        'total_values': total_values,
        'unique_values': unique_values,
        'top_values': top_values
    }

def create_analytics_plots(clicks):
    """Generate plotly visualizations for click analytics"""
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
    
    # Add device distribution
    device_data = clicks.values('device_type').annotate(count=Count('id'))
    fig.add_trace(go.Pie(
        labels=[d['device_type'] for d in device_data],
        values=[d['count'] for d in device_data],
        name='Device Types'
    ), row=1, col=2)
    
    # Add time-based distributions
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = clicks.values('weekday').annotate(count=Count('id')).order_by('weekday')
    
    fig.add_trace(go.Bar(
        x=[weekday_names[d['weekday']] for d in weekday_data],
        y=[d['count'] for d in weekday_data],
        name='Clicks by Day'
    ), row=2, col=1)
    
    return fig.to_json()