from copy import copy

from django import template

register = template.Library()


@register.simple_tag
def render_field(bound_field, **attrs):
    widget = copy(bound_field.field.widget)
    widget.attrs = {**widget.attrs, **attrs}
    return bound_field.as_widget(widget=widget)
