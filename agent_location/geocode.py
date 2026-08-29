"""Reverse geocoding — Esri first (matches map tiles), Nominatim fallback.

Local area names (e.g. Bamanmura / Bamunmura) are often missing from the exact
GPS reverse result but appear on nearby road labels on the Esri street map.
We sample a small ring around the point to recover that locality.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings

logger = logging.getLogger(__name__)

ESRI_REVERSE_URL = (
    'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode'
)
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'

# ~150–250 m offsets — enough to catch nearby locality-named main roads
_RING_OFFSETS = (
    (0.0015, 0.0),
    (-0.0015, 0.0),
    (0.0, 0.0015),
    (0.0, -0.0015),
    (0.0015, -0.0015),
    (-0.0015, -0.0015),
    (0.0015, 0.0015),
    (-0.0015, 0.0015),
    (0.0025, -0.0025),
    (-0.0025, -0.0025),
)

_GENERIC_ROAD_TOKENS = {
    'main', 'road', 'rd', 'street', 'st', 'lane', 'ln', 'bye', 'byepass',
    'bypass', 'highway', 'nh', 'sh', 'mdr', 'taki', 'station', 'bus',
    'new', 'old', 'link', 'cross', 'crossing',
}


def _http_get_json(url, headers=None, timeout=4):
    req = urllib.request.Request(url, headers=headers or {}, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _empty_result():
    return {
        'display_name': '',
        'short_name': '',
        'building': '',
        'road': '',
        'neighbourhood': '',
        'suburb': '',
        'village': '',
        'city': '',
        'district': '',
        'state': '',
        'postcode': '',
        'country': '',
        'provider': '',
    }


def _area_from_road_name(road: str) -> str:
    """Extract locality from names like 'Bamanmura Main Road' / 'Bamun Mura Road'."""
    if not road:
        return ''
    road = road.strip()
    # Ignore highway refs
    if re.fullmatch(r'(NH|SH|MDR)?\s*\d+', road, re.I):
        return ''
    m = re.match(
        r'^(?P<area>.+?)\s+(?:Main\s+)?(?:Road|Rd|Street|St|Lane|Ln|Bypass|Highway)\.?$',
        road,
        re.I,
    )
    if not m:
        return ''
    area = m.group('area').strip(' ,.-')
    if re.fullmatch(r'(NH|SH|MDR)?\s*\d+', area, re.I):
        return ''
    tokens = [t for t in re.split(r'\s+', area) if t.lower() not in _GENERIC_ROAD_TOKENS]
    if not tokens:
        return ''
    return ' '.join(tokens)


def _esri_reverse_one(lat, lng, timeout):
    params = urllib.parse.urlencode({
        'f': 'json',
        'langCode': 'en',
        'location': f'{lng:.6f},{lat:.6f}',
        'featureTypes': '',
        'locationType': 'rooftop',
    })
    url = f'{ESRI_REVERSE_URL}?{params}'
    payload = _http_get_json(url, headers={'Accept': 'application/json'}, timeout=timeout)
    return payload.get('address') or {}


def _discover_local_area(lat, lng, center_address, timeout):
    """
    Find the most local area name:
    1) Esri Neighborhood at the pin
    2) Nearby Esri road labels that encode locality (e.g. Bamanmura Main Road)
    """
    direct = (center_address.get('Neighborhood') or '').strip()
    if direct:
        return direct

    candidates = []

    def _job(offset):
        dlat, dlng = offset
        try:
            addr = _esri_reverse_one(lat + dlat, lng + dlng, timeout)
        except Exception:
            return None
        neigh = (addr.get('Neighborhood') or '').strip()
        road = (addr.get('Address') or addr.get('ShortLabel') or '').strip()
        area = neigh or _area_from_road_name(road)
        if not area:
            return None
        # Prefer results that look like real localities, not city/district dumps
        city = (center_address.get('City') or center_address.get('District') or '').strip()
        if city and area.lower() == city.lower():
            return None
        # Distance proxy from offset magnitude
        dist_proxy = (dlat * dlat + dlng * dlng) ** 0.5
        return dist_proxy, area, road

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_job, off) for off in _RING_OFFSETS]
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                candidates.append(row)

    if not candidates:
        # Fallback: try extracting from center road itself
        center_road = (
            center_address.get('Address')
            or center_address.get('ShortLabel')
            or ''
        ).strip()
        return _area_from_road_name(center_road)

    candidates.sort(key=lambda r: r[0])
    return candidates[0][1]


def _from_esri(lat, lng, timeout):
    """
    Esri World Geocoder — same data family as Esri Street Map tiles.
    Enriches Area with nearby locality when Neighborhood is empty.
    """
    address = _esri_reverse_one(lat, lng, timeout)
    if not address:
        return {}

    building = (address.get('PlaceName') or address.get('Building') or '').strip()
    road = (
        address.get('StAddr')
        or address.get('Address')
        or address.get('ShortLabel')
        or ''
    ).strip()
    # Drop bogus "road" values that are just city / PIN
    if road and (
        road == (address.get('City') or '').strip()
        or road == (address.get('District') or '').strip()
        or re.fullmatch(r'\d{5,6}', road)
    ):
        road = (address.get('ShortLabel') or '').strip()
        if road == (address.get('City') or '').strip() or re.fullmatch(r'\d{5,6}', road or ''):
            road = ''

    neighbourhood = _discover_local_area(lat, lng, address, timeout)
    suburb = (address.get('Suburb') or address.get('Sector') or '').strip()
    village = (address.get('Village') or '').strip()
    city = (
        address.get('City')
        or address.get('MetroArea')
        or ''
    ).strip()
    district = (address.get('Subregion') or '').strip()
    state = (address.get('Region') or '').strip()
    postcode = (address.get('Postal') or address.get('PostalExt') or '').strip()
    country = (address.get('CntryName') or address.get('CountryCode') or '').strip()

    # Never let Area collapse to the city name (Barsat / Barasat)
    if neighbourhood and city and neighbourhood.lower() == city.lower():
        neighbourhood = ''

    display_name = (
        address.get('LongLabel')
        or address.get('Match_addr')
        or address.get('ShortLabel')
        or ''
    ).strip()
    # Prepend discovered local area when Esri long label skipped it
    if neighbourhood and neighbourhood.lower() not in display_name.lower():
        display_name = ', '.join(
            p for p in (road, neighbourhood, city, district, state, postcode) if p
        )

    if not display_name:
        parts = [
            p for p in (building, road, neighbourhood or suburb or village, city, district, state, postcode)
            if p
        ]
        display_name = ', '.join(parts)

    area = neighbourhood or suburb or village
    short_parts = [p for p in (building, road, area) if p]
    short_name = ', '.join(short_parts[:3]) if short_parts else display_name

    return {
        'display_name': display_name,
        'short_name': short_name,
        'building': building,
        'road': road,
        'neighbourhood': neighbourhood,
        'suburb': suburb,
        'village': village,
        'city': city,
        'district': district,
        'state': state,
        'postcode': postcode,
        'country': country,
        'provider': 'esri',
    }


def _from_nominatim(lat, lng, timeout):
    params = urllib.parse.urlencode({
        'lat': f'{lat:.6f}',
        'lon': f'{lng:.6f}',
        'format': 'jsonv2',
        'addressdetails': 1,
        'zoom': 18,
        'namedetails': 1,
    })
    url = f'{NOMINATIM_URL}?{params}'
    app_name = getattr(settings, 'AGENT_LOCATION_GEOCODER_UA', 'KsundaramAgentLocation/1.0')
    payload = _http_get_json(
        url,
        headers={'User-Agent': app_name, 'Accept': 'application/json'},
        timeout=timeout,
    )
    address = payload.get('address') or {}
    building = (
        address.get('building')
        or address.get('amenity')
        or address.get('shop')
        or address.get('office')
        or address.get('tourism')
        or address.get('leisure')
        or payload.get('name')
        or ''
    )
    road = address.get('road') or address.get('pedestrian') or address.get('path') or address.get('footway') or ''
    neighbourhood = (
        address.get('neighbourhood')
        or address.get('quarter')
        or address.get('residential')
        or address.get('locality')
        or address.get('hamlet')
        or ''
    )
    suburb = address.get('suburb') or address.get('city_district') or address.get('borough') or ''
    village = address.get('village') or address.get('town') or ''
    city = address.get('city') or address.get('municipality') or address.get('county') or ''
    district = address.get('state_district') or address.get('district') or ''
    state = address.get('state') or ''
    postcode = address.get('postcode') or ''
    country = address.get('country') or ''

    # Prefer suburb over city for Area when neighbourhood missing
    area = neighbourhood or suburb or village
    if area and city and area.lower() == city.lower():
        area = suburb if suburb.lower() != city.lower() else (village or '')

    short_parts = [p for p in (building, road, area) if p]
    short_name = ', '.join(short_parts[:3]) if short_parts else (payload.get('name') or '')
    display_name = payload.get('display_name') or ''
    if not display_name:
        full_parts = [p for p in (building, road, neighbourhood, suburb, village, city, district, state, postcode) if p]
        display_name = ', '.join(full_parts)

    return {
        'display_name': display_name,
        'short_name': short_name or display_name,
        'building': building or '',
        'road': road or '',
        'neighbourhood': neighbourhood or area or '',
        'suburb': suburb or '',
        'village': village or '',
        'city': city or '',
        'district': district or '',
        'state': state or '',
        'postcode': postcode or '',
        'country': country or '',
        'provider': 'nominatim',
    }


def reverse_geocode(latitude, longitude):
    """
    Return place details for a GPS point.
    Prefer Esri so Area name matches local map labels (e.g. Bamanmura).
    """
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return _empty_result()

    timeout = float(getattr(settings, 'AGENT_LOCATION_GEOCODE_TIMEOUT', 5))

    try:
        result = _from_esri(lat, lng, timeout)
        if result.get('display_name') or result.get('neighbourhood') or result.get('road'):
            # If Esri found road/city but no local Area, try Nominatim suburb as Area only
            if not result.get('neighbourhood'):
                try:
                    nom = _from_nominatim(lat, lng, timeout)
                    area = nom.get('neighbourhood') or nom.get('suburb') or nom.get('village') or ''
                    city = (result.get('city') or '').lower()
                    if area and area.lower() != city:
                        result['neighbourhood'] = area
                        if area.lower() not in (result.get('display_name') or '').lower():
                            result['display_name'] = ', '.join(
                                p for p in (
                                    result.get('road'),
                                    area,
                                    result.get('city'),
                                    result.get('district'),
                                    result.get('state'),
                                    result.get('postcode'),
                                ) if p
                            )
                        short_parts = [p for p in (result.get('building'), result.get('road'), area) if p]
                        result['short_name'] = ', '.join(short_parts[:3])
                        result['provider'] = 'esri+nominatim'
                except Exception as exc:
                    logger.debug('Nominatim area enrich failed: %s', exc)
            return result
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
        logger.debug('Esri reverse geocode failed: %s', exc)

    try:
        return _from_nominatim(lat, lng, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
        logger.debug('Nominatim reverse geocode failed: %s', exc)
        return _empty_result()
