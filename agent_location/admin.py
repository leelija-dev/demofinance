from django.contrib import admin
from .models import AgentCurrentLocation


@admin.register(AgentCurrentLocation)
class AgentCurrentLocationAdmin(admin.ModelAdmin):
    list_display = ('agent', 'place_name', 'latitude', 'longitude', 'accuracy_m', 'recorded_at', 'updated_at')
    search_fields = (
        'agent__agent_id',
        'agent__full_name',
        'agent__phone',
        'place_name',
        'address_text',
        'road',
        'building',
    )
    list_filter = ('recorded_at', 'city', 'state')
    readonly_fields = ('updated_at',)
