from django.db import models
from agent.models import Agent


class AgentCurrentLocation(models.Model):
    """Latest known GPS position for a field agent."""

    agent = models.OneToOneField(
        Agent,
        on_delete=models.CASCADE,
        related_name='current_location',
        primary_key=True,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_m = models.FloatField(null=True, blank=True)
    # Reverse-geocoded place details (Nominatim / OSM)
    place_name = models.CharField(max_length=255, blank=True, default='')
    building = models.CharField(max_length=255, blank=True, default='')
    road = models.CharField(max_length=255, blank=True, default='')
    neighbourhood = models.CharField(max_length=255, blank=True, default='')
    suburb = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=128, blank=True, default='')
    district = models.CharField(max_length=128, blank=True, default='')
    state = models.CharField(max_length=128, blank=True, default='')
    postcode = models.CharField(max_length=32, blank=True, default='')
    address_text = models.TextField(blank=True, default='')
    # esri | nominatim — Esri preferred so labels match street map
    geocode_provider = models.CharField(max_length=32, blank=True, default='')
    # True while agent session is sending pings; cleared on logout
    session_active = models.BooleanField(default=False, db_index=True)
    recorded_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agent current location'
        verbose_name_plural = 'Agent current locations'
        ordering = ['-recorded_at']

    def __str__(self):
        return f'{self.agent_id} @ {self.latitude}, {self.longitude}'
