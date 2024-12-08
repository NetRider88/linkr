from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    """
    Add a CSS class to a form field
    """
    return field.as_widget(attrs={"class": css_class})

@register.filter(name='field_type')
def field_type(field):
    """
    Return the name of the field class
    """
    return field.field.widget.__class__.__name__

@register.filter(name='input_class')
def input_class(field):
    """
    Return appropriate Bootstrap class based on field type and validation state
    """
    css_class = 'form-control'
    if field.errors:
        css_class += ' is-invalid'
    elif field.form.is_bound and field.name in field.form.cleaned_data:
        css_class += ' is-valid'
    return css_class
