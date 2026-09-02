import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

# LocationIQ is a hosted, Nominatim-compatible geocoder (same OSM data, same
# response shape) with a real per-key rate limit instead of Nominatim's
# public demo endpoint, which throttles shared cloud-host IPs regardless of
# how little any one app sends. Free tier: 5,000 requests/day, no card.
LOCATIONIQ_URL = "https://us1.locationiq.com/v1/search"
GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_SPECIES_URL = "https://api.gbif.org/v1/species/{key}"
GBIF_VERNACULAR_URL = "https://api.gbif.org/v1/species/{key}/vernacularNames"

USER_AGENT = "FishWise/1.0 (hobby fishing-tips app)"

# GBIF backbone key for phylum Chordata. There's no single "fish" taxon key
# to filter on: GBIF's current backbone split the old class Actinopterygii
# (its key, 204, was deleted from the backbone in 2022) into ~40+ separate
# orders attached directly to Chordata with no unifying class value at all.
# Rather than maintain a long, backbone-version-fragile list of fish order
# keys, query all of Chordata and exclude the small, stable set of non-fish
# classes below — anything left (including records with no class at all,
# which is how most bony-fish orders now appear) is fish.
_PHYLUM_CHORDATA_KEY = 44
_NON_FISH_CLASSES = {
    "Mammalia", "Aves", "Reptilia", "Amphibia",
    "Ascidiacea", "Thaliacea", "Appendicularia", "Leptocardii",
}
# Backup filter for records missing a "class" value (the same gap that lets
# classless fish orders through — Squamata water snakes and Testudines
# turtles have shown up in practice with no class tagged either). There are
# far fewer non-fish tetrapod orders than fish orders, so this stays small.
_NON_FISH_ORDERS = {
    "Squamata", "Testudines", "Crocodylia",  # reptiles
    "Anura", "Caudata", "Gymnophiona",  # amphibians
}

# A handful of common North American gamefish genera, used only to break
# ties toward what an angler actually cares about. GBIF's raw occurrence
# counts are dominated by natural-history/museum survey records of small,
# heavily-vouchered stream fish (darters, dace, shiners); popular sportfish
# like bass are comparatively under-collected by ichthyologists even where
# they're the most commonly caught species, so ranking by raw count alone
# can bury them. Any gamefish genus present is surfaced first; the rest are
# still ranked by how often they were actually recorded.
_GAMEFISH_GENERA = {
    "micropterus",  # largemouth/smallmouth/spotted bass
    "lepomis",  # bluegill, sunfish, redear
    "pomoxis",  # crappie
    "ictalurus", "ameiurus", "pylodictis",  # catfish, bullhead, flathead
    "sander", "perca",  # walleye, yellow perch
    "esox",  # pike, pickerel, muskellunge
    "cyprinus",  # common carp
    "salmo", "oncorhynchus", "salvelinus",  # trout, salmon, char
    "morone",  # striped/white bass
    "aplodinotus",  # freshwater drum
}


def _is_gamefish(scientific_name: str) -> bool:
    genus = scientific_name.split(" ", 1)[0].lower()
    return genus in _GAMEFISH_GENERA

_RADII_KM = [15, 40, 100, 250]
_MAX_SPECIES = 8
_MAX_CANDIDATES_TO_VERIFY = 25
_OCCURRENCE_LIMIT = 300
_PAGES_PER_RADIUS = 3
_MAX_RETRIES = 2


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


def _fetch_species_counts(lat: float, lon: float, radius_km: int) -> dict:
    """Query GBIF occurrence records within radius_km of (lat, lon) under
    phylum Chordata, filter out the known non-fish classes, and tally how
    often each remaining species appears. Pages through up to
    _PAGES_PER_RADIUS batches, since bird/mammal observations often
    dominate a raw Chordata sample and can crowd out fish in the first
    page alone."""
    counts: dict[int, dict] = {}
    for page in range(_PAGES_PER_RADIUS):
        data = _get(
            GBIF_OCCURRENCE_URL,
            {
                # GBIF's geoDistance format is "{lat},{lng},{distance}{unit}"
                # — confirmed by live-testing against the real API (a
                # documented javadoc example suggested distance-first, but
                # that order returns "Argument is not a valid number").
                "geoDistance": f"{lat},{lon},{radius_km}km",
                "phylumKey": _PHYLUM_CHORDATA_KEY,
                "hasCoordinate": "true",
                "limit": _OCCURRENCE_LIMIT,
                "offset": page * _OCCURRENCE_LIMIT,
            },
        )
        results = data.get("results", [])
        for record in results:
            if record.get("class") in _NON_FISH_CLASSES:
                continue
            if record.get("order") in _NON_FISH_ORDERS:
                continue
            species_key = record.get("speciesKey")
            name = record.get("species")
            if not species_key or not name:
                continue
            entry = counts.setdefault(species_key, {"key": species_key, "name": name, "count": 0})
            entry["count"] += 1
        if len(counts) >= 3 or len(results) < _OCCURRENCE_LIMIT:
            break
    return counts


def _verify_is_fish(species_key: int) -> bool:
    """Authoritatively confirm a species is a fish via its GBIF backbone
    record (/v1/species/{key}), which is always fully populated — unlike
    the class/order fields on individual occurrence records, which are
    frequently missing and let a water snake and a turtle through with
    the occurrence-record-only filtering above. On a lookup failure, don't
    penalize the candidate for a network hiccup — let it through."""
    try:
        data = _get(GBIF_SPECIES_URL.format(key=species_key), {})
    except UpstreamServiceError:
        return True
    if data.get("phylumKey") != _PHYLUM_CHORDATA_KEY:
        return False
    if data.get("class") in _NON_FISH_CLASSES:
        return False
    if data.get("order") in _NON_FISH_ORDERS:
        return False
    return True


def _common_name(species_key: int, scientific_name: str) -> str:
    """Look up an English common name for a species; fall back to its
    scientific name if none is recorded in GBIF."""
    try:
        data = _get(GBIF_VERNACULAR_URL.format(key=species_key), {"language": "eng"})
    except UpstreamServiceError:
        return scientific_name
    for entry in data.get("results", []):
        # The language query param above isn't reliably honored server-side
        # (German/Italian/Portuguese names have come back despite it), so
        # always re-check the language client-side before using a name.
        if entry.get("language") != "eng":
            continue
        name = entry.get("vernacularName")
        if name:
            return name.title()
    return scientific_name


def find_species_near(lat: float, lon: float) -> list[str]:
    """Return fish species actually recorded near this location, per real
    GBIF occurrence data — not a language model's recall. Expands the
    search radius progressively until at least a few distinct species turn
    up, so sparser-data regions still get a useful result."""
    counts: dict[int, dict] = {}
    for radius_km in _RADII_KM:
        counts = _fetch_species_counts(lat, lon, radius_km)
        if len(counts) >= 3:
            break

    by_count = sorted(counts.values(), key=lambda v: v["count"], reverse=True)
    gamefish = [e for e in by_count if _is_gamefish(e["name"])]
    others = [e for e in by_count if not _is_gamefish(e["name"])]
    candidates = (gamefish + others)[:_MAX_CANDIDATES_TO_VERIFY]

    verified = [e for e in candidates if _verify_is_fish(e["key"])]
    ranked = verified[:_MAX_SPECIES]
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
