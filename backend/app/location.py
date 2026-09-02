import logging
import os
import time
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# LocationIQ is a hosted, Nominatim-compatible geocoder (same OSM data, same
# response shape) with a real per-key rate limit instead of Nominatim's
# public demo endpoint, which throttles shared cloud-host IPs regardless of
# how little any one app sends. Free tier: 5,000 requests/day, no card.
LOCATIONIQ_URL = "https://us1.locationiq.com/v1/search"
# Open-Meteo: free, no API key, no rate-limit signup required for this
# volume of use. One call gets both current conditions and today's
# sunrise/sunset for a location.
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

USER_AGENT = "FishWise/1.0 (hobby fishing-tips app)"

_MAX_RETRIES = 2


class WaterBodyNotFoundError(Exception):
    """The water body name couldn't be geocoded to a real location."""


class UpstreamServiceError(Exception):
    """A geocoding request failed (network, timeout, bad response)."""


def _get(url: str, params: dict, timeout: int = 10) -> dict:
    """GET with retry-with-backoff on 429 — free geocoding endpoints can
    rate-limit a cloud host's shared egress IP even for low-volume,
    legitimate use."""
    response = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
        except requests.RequestException as e:
            raise UpstreamServiceError(
                "Could not reach the location lookup service."
            ) from e

        if response.status_code != 429 or attempt == _MAX_RETRIES:
            break
        try:
            delay = float(response.headers.get("Retry-After", ""))
        except ValueError:
            delay = 1.5 * (attempt + 1)
        logger.warning("Rate-limited by %s, retrying in %.1fs", url, delay)
        time.sleep(delay)

    if response.status_code == 429:
        raise UpstreamServiceError(
            "The location lookup service is rate-limited right now. Please "
            "wait a moment and try again."
        )
    try:
        response.raise_for_status()
        return response.json()
    except (requests.HTTPError, ValueError) as e:
        raise UpstreamServiceError(
            "The location lookup service returned an unexpected response "
            f"(status {response.status_code})."
        ) from e


def _get_locationiq_key() -> str:
    api_key = os.environ.get("LOCATIONIQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LOCATIONIQ_API_KEY is not set. Sign up for a free key at "
            "https://locationiq.com (no card required) and add it to "
            "backend/.env or your deployment's environment variables."
        )
    return api_key


def geocode_water_body(query: str) -> dict:
    """Resolve free-text like 'Lake Travis, TX' to a normalized display name
    and coordinates, via LocationIQ's geocoder."""
    api_key = _get_locationiq_key()
    results = _get(LOCATIONIQ_URL, {"key": api_key, "q": query, "format": "json", "limit": 1})
    if not results:
        raise WaterBodyNotFoundError(
            f"Could not find a location matching '{query}'. Try including a "
            "city, state, or more specific name."
        )
    top = results[0]
    return {
        "display_name": top["display_name"],
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
    }


def _format_time(iso_str: str) -> Optional[str]:
    try:
        return datetime.fromisoformat(iso_str).strftime("%-I:%M %p")
    except ValueError:
        return None


def get_conditions(lat: float, lon: float) -> Optional[dict]:
    """Fetch current weather and today's sunrise/sunset for a location, via
    Open-Meteo. Returns None on any failure — conditions are a nice-to-have
    on top of the water body lookup, never something that should block it."""
    try:
        data = _get(
            OPEN_METEO_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m",
                "daily": "sunrise,sunset",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            },
        )
    except UpstreamServiceError as e:
        logger.warning("Open-Meteo lookup failed, omitting conditions: %s", e)
        return None

    current = data.get("current") or {}
    daily = data.get("daily") or {}
    sunrise_list = daily.get("sunrise") or []
    sunset_list = daily.get("sunset") or []

    result = {}
    if current.get("temperature_2m") is not None:
        result["temperature_f"] = current["temperature_2m"]
    if current.get("wind_speed_10m") is not None:
        result["wind_mph"] = current["wind_speed_10m"]
    if sunrise_list:
        sunrise = _format_time(sunrise_list[0])
        if sunrise:
            result["sunrise"] = sunrise
    if sunset_list:
        sunset = _format_time(sunset_list[0])
        if sunset:
            result["sunset"] = sunset

    return result or None
