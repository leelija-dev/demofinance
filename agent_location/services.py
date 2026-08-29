from datetime import timedelta
from decimal import Decimal, InvalidOperation
from math import radians, cos, sin, asin, sqrt

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from agent.models import Agent
from .geocode import reverse_geocode
from .models import AgentCurrentLocation


def _stale_minutes():
    return int(getattr(settings, 'AGENT_LOCATION_STALE_MINUTES', 10))


def parse_coordinate(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return None


def is_valid_coordinate(lat, lng):
    if lat is None or lng is None:
        return False
    if lat == 0 and lng == 0:
        return False
    return Decimal('-90') <= lat <= Decimal('90') and Decimal('-180') <= lng <= Decimal('180')


def _haversine_m(lat1, lng1, lat2, lng2):
    """Approximate distance in meters between two WGS84 points."""
    try:
        r = 6371000.0
        p1, p2 = radians(float(lat1)), radians(float(lat2))
        dphi = radians(float(lat2) - float(lat1))
        dlmb = radians(float(lng2) - float(lng1))
        a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
        return 2 * r * asin(sqrt(a))
    except (TypeError, ValueError):
        return 999999.0


def _place_defaults_from_geocode(geo):
    if not geo:
        return {}
    return {
        'place_name': (geo.get('short_name') or '')[:255],
        'building': (geo.get('building') or '')[:255],
        'road': (geo.get('road') or '')[:255],
        'neighbourhood': (geo.get('neighbourhood') or '')[:255],
        'suburb': (geo.get('suburb') or '')[:255],
        'city': (geo.get('city') or geo.get('village') or '')[:128],
        'district': (geo.get('district') or '')[:128],
        'state': (geo.get('state') or '')[:128],
        'postcode': (geo.get('postcode') or '')[:32],
        'address_text': geo.get('display_name') or '',
        'geocode_provider': (geo.get('provider') or '')[:32],
    }


def upsert_agent_location(agent, latitude, longitude, accuracy_m=None, recorded_at=None):
    """Create or update the agent's latest location. Returns the model instance."""
    if recorded_at is None:
        recorded_at = timezone.now()
    elif isinstance(recorded_at, str):
        parsed = parse_datetime(recorded_at)
        recorded_at = parsed if parsed else timezone.now()
        if timezone.is_naive(recorded_at):
            recorded_at = timezone.make_aware(recorded_at, timezone.get_current_timezone())

    now = timezone.now()
    if recorded_at > now + timedelta(minutes=5):
        recorded_at = now

    accuracy = None
    if accuracy_m is not None and accuracy_m != '':
        try:
            accuracy = float(accuracy_m)
            if accuracy < 0:
                accuracy = None
        except (TypeError, ValueError):
            accuracy = None

    existing = AgentCurrentLocation.objects.filter(agent=agent).first()
    should_geocode = True
    if existing and existing.address_text and existing.geocode_provider in ('esri', 'esri+nominatim'):
        moved_m = _haversine_m(existing.latitude, existing.longitude, latitude, longitude)
        has_local_area = bool(
            existing.neighbourhood
            and existing.neighbourhood.lower() != (existing.city or '').lower()
        )
        # Skip re-geocode only for tiny moves when we already have a real local Area
        if moved_m < 40 and has_local_area:
            should_geocode = False

    place_fields = {}
    if should_geocode:
        geo = reverse_geocode(latitude, longitude)
        place_fields = _place_defaults_from_geocode(geo)
    elif existing:
        place_fields = {
            'place_name': existing.place_name,
            'building': existing.building,
            'road': existing.road,
            'neighbourhood': existing.neighbourhood,
            'suburb': existing.suburb,
            'city': existing.city,
            'district': existing.district,
            'state': existing.state,
            'postcode': existing.postcode,
            'address_text': existing.address_text,
            'geocode_provider': existing.geocode_provider,
        }

    defaults = {
        'latitude': latitude,
        'longitude': longitude,
        'accuracy_m': accuracy,
        'recorded_at': recorded_at,
        'session_active': True,
        **place_fields,
    }

    obj, _created = AgentCurrentLocation.objects.update_or_create(
        agent=agent,
        defaults=defaults,
    )
    return obj


def mark_agent_offline(agent_id):
    """Mark agent offline immediately (e.g. on logout). Keeps last known coordinates."""
    if not agent_id:
        return 0
    return AgentCurrentLocation.objects.filter(agent_id=agent_id).update(session_active=False)


def serialize_location_row(agent, loc, now=None):
    now = now or timezone.now()
    stale = timedelta(minutes=_stale_minutes())
    has_loc = loc is not None
    # Online only while logged-in session is active AND last ping is fresh
    is_online = bool(
        has_loc
        and getattr(loc, 'session_active', False)
        and (now - loc.recorded_at) <= stale
    )

    return {
        'agent_id': agent.agent_id,
        'full_name': agent.full_name,
        'phone': agent.phone,
        'area': agent.area or '',
        'status': agent.status,
        'branch_id': getattr(agent.branch, 'branch_id', None) or getattr(agent, 'branch_id', None),
        'branch_name': getattr(agent.branch, 'branch_name', '') if hasattr(agent, 'branch') else '',
        'latitude': float(loc.latitude) if has_loc else None,
        'longitude': float(loc.longitude) if has_loc else None,
        'accuracy_m': loc.accuracy_m if has_loc else None,
        'recorded_at': loc.recorded_at.isoformat() if has_loc else None,
        'is_online': is_online,
        'has_location': has_loc,
        'place_name': (loc.place_name if has_loc else '') or '',
        'building': (loc.building if has_loc else '') or '',
        'road': (loc.road if has_loc else '') or '',
        'neighbourhood': (loc.neighbourhood if has_loc else '') or '',
        'suburb': (loc.suburb if has_loc else '') or '',
        'city': (loc.city if has_loc else '') or '',
        'district': (loc.district if has_loc else '') or '',
        'state': (loc.state if has_loc else '') or '',
        'postcode': (loc.postcode if has_loc else '') or '',
        'address_text': (loc.address_text if has_loc else '') or '',
    }


def list_agent_locations(branch=None, status='active', search='', branch_id=None):
    """
    Return serialized location payloads for agents.
    - branch: Branch instance → restrict to that branch (branch portal)
    - branch_id: optional string filter (HQ portal)
    """
    qs = Agent.objects.select_related('branch', 'current_location')

    if branch is not None:
        qs = qs.filter(branch=branch)
    elif branch_id:
        qs = qs.filter(branch_id=branch_id)

    status = (status or 'active').strip().lower()
    if status in ('active', 'inactive'):
        qs = qs.filter(status=status)

    search = (search or '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(agent_id__icontains=search)
            | Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(current_location__place_name__icontains=search)
            | Q(current_location__address_text__icontains=search)
            | Q(current_location__road__icontains=search)
            | Q(current_location__building__icontains=search)
        )

    qs = qs.order_by('branch__branch_name', 'full_name')
    now = timezone.now()
    rows = []
    for agent in qs:
        try:
            loc = agent.current_location
        except AgentCurrentLocation.DoesNotExist:
            loc = None
        rows.append(serialize_location_row(agent, loc, now=now))

    # Backfill / upgrade place names (Esri preferred so Area matches map)
    fill_budget = int(getattr(settings, 'AGENT_LOCATION_GEOCODE_FILL_PER_REQUEST', 5))
    filled = 0
    for row in rows:
        if filled >= fill_budget:
            break
        if not row.get('has_location'):
            continue
        # Refresh if missing address OR still on old Nominatim/empty provider
        loc_obj = AgentCurrentLocation.objects.filter(agent_id=row['agent_id']).only(
            'geocode_provider', 'latitude', 'longitude'
        ).first()
        provider = (loc_obj.geocode_provider if loc_obj else '') or ''
        area = (row.get('neighbourhood') or '').strip()
        city = (row.get('city') or '').strip()
        has_local_area = bool(area and area.lower() != city.lower())
        needs_refresh = (
            (not row.get('address_text'))
            or (provider not in ('esri', 'esri+nominatim'))
            or (not has_local_area)
        )
        if not needs_refresh:
            continue
        geo = reverse_geocode(row['latitude'], row['longitude'])
        place_fields = _place_defaults_from_geocode(geo)
        if not place_fields.get('address_text') and not place_fields.get('neighbourhood'):
            continue
        AgentCurrentLocation.objects.filter(agent_id=row['agent_id']).update(**place_fields)
        row.update({
            'place_name': place_fields.get('place_name', ''),
            'building': place_fields.get('building', ''),
            'road': place_fields.get('road', ''),
            'neighbourhood': place_fields.get('neighbourhood', ''),
            'suburb': place_fields.get('suburb', ''),
            'city': place_fields.get('city', ''),
            'district': place_fields.get('district', ''),
            'state': place_fields.get('state', ''),
            'postcode': place_fields.get('postcode', ''),
            'address_text': place_fields.get('address_text', ''),
        })
        filled += 1

    return rows
