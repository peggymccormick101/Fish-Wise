import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# LocationIQ is a hosted, Nominatim-compatible geocoder (same OSM data, same
# response shape) with a real per-key rate limit instead of Nominatim's
# public demo endpoint, which throttles shared cloud-host IPs regardless of
# how little any one app sends. Free tier: 5,000 requests/day, no card.
LOCATIONIQ_URL = "https://us1.locationiq.com/v1/search"
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_VERNACULAR_URL = "https://api.gbif.org/v1/species/{key}/vernacularNames"

USER_AGENT = "FishWise/1.0 (hobby fishing-tips app)"

# GBIF backbone taxon key for the class Actinopterygii (ray-finned fishes,
# which covers virtually all freshwater and most inshore game species). Used
# only if the live species/match lookup below fails.
_FALLBACK_ACTINOPTERYGII_KEY = 204

_RADII_KM = [15, 40, 100, 250]
_MAX_SPECIES = 8
_OCCURRENCE_LIMIT = 300
_MAX_RETRIES = 2

_actinopterygii_key_cache: Optional[int] = None


class WaterBodyNotFoundError(Exception):
    """The water body name couldn't be geocoded to a real location."""


class NoSpeciesFoundError(Exception):
    """The location geocoded fine, but no fish occurrence records were
    found nearby, even at the widest search radius."""


class UpstreamServiceError(Exception):
    """A geocoding/GBIF request failed (network, timeout, bad response)."""


def _get(url: str, params: dict, timeout: int = 10) -> dict:
    """GET with retry-with-backoff on 429 — the free Nominatim/GBIF
    endpoints can rate-limit a cloud host's shared egress IP even for
    low-volume, legitimate use."""
    response = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout
            )
        except requests.RequestException as e:
            raise UpstreamServiceError(
                "Could not reach the location/species lookup service."
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
            "The location/species lookup service returned an unexpected "
            f"response (status {response.status_code})."
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


def _resolve_actinopterygii_key() -> int:
    global _actinopterygii_key_cache
    if _actinopterygii_key_cache is not None:
        return _actinopterygii_key_cache
    try:
        data = _get(GBIF_MATCH_URL, {"name": "Actinopterygii", "rank": "CLASS"})
        key = data.get("usageKey")
        if key:
            _actinopterygii_key_cache = int(key)
            return _actinopterygii_key_cache
    except UpstreamServiceError:
        pass
    logger.warning("GBIF species/match lookup failed; using fallback taxon key")
    _actinopterygii_key_cache = _FALLBACK_ACTINOPTERYGII_KEY
    return _actinopterygii_key_cache


def _fetch_species_counts(lat: float, lon: float, radius_km: int, taxon_key: int) -> dict:
    """Query GBIF occurrence records within radius_km of (lat, lon),
    filtered to ray-finned fish, and tally how often each species appears."""
    data = _get(
        GBIF_OCCURRENCE_URL,
        {
            # GBIF's format is "{distance}{unit},{lat},{lng}" — distance
            # first, e.g. "100km,40,90". Confirmed against the GEO_DISTANCE
            # javadoc in gbif/gbif-api's OccurrenceSearchParameter.java.
            "geoDistance": f"{radius_km}km,{lat},{lon}",
            "taxonKey": taxon_key,
            "hasCoordinate": "true",
            "limit": _OCCURRENCE_LIMIT,
        },
    )
    counts: dict[int, dict] = {}
    for record in data.get("results", []):
        species_key = record.get("speciesKey")
        name = record.get("species")
        if not species_key or not name:
            continue
        entry = counts.setdefault(species_key, {"key": species_key, "name": name, "count": 0})
        entry["count"] += 1
    return counts


def _common_name(species_key: int, scientific_name: str) -> str:
    """Look up an English common name for a species; fall back to its
    scientific name if none is recorded in GBIF."""
    try:
        data = _get(GBIF_VERNACULAR_URL.format(key=species_key), {"language": "eng"})
    except UpstreamServiceError:
        return scientific_name
    for entry in data.get("results", []):
        name = entry.get("vernacularName")
        if name:
            return name.title()
    return scientific_name


def find_species_near(lat: float, lon: float) -> list[str]:
    """Return fish species actually recorded near this location, per real
    GBIF occurrence data — not a language model's recall. Expands the
    search radius progressively until at least a few distinct species turn
    up, so sparser-data regions still get a useful result."""
    taxon_key = _resolve_actinopterygii_key()
    counts: dict[int, dict] = {}
    for radius_km in _RADII_KM:
        counts = _fetch_species_counts(lat, lon, radius_km, taxon_key)
        if len(counts) >= 3:
            break

    ranked = sorted(counts.values(), key=lambda v: v["count"], reverse=True)[:_MAX_SPECIES]
    return [_common_name(entry["key"], entry["name"]) for entry in ranked]


def lookup_water_body(water_body: str) -> dict:
    """Identify a water body and find fish species actually recorded near
    it, using real geocoding + biodiversity-occurrence data instead of
    asking a language model to recall species from memory."""
    location = geocode_water_body(water_body)
    species = find_species_near(location["lat"], location["lon"])
    if not species:
        raise NoSpeciesFoundError(
            f"Found '{location['display_name']}', but no fish records turned "
            "up nearby yet. Try a larger or better-known body of water."
        )
    return {"water_body_normalized": location["display_name"], "species": species}
