import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from astral import LocationInfo
from astral.sun import sun
from timezonefinder import TimezoneFinder

import requests
from PIL import Image
from io import BytesIO
from datetime import datetime

from tqdm import tqdm

CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_tz_finder = TimezoneFinder()

def extract_keys(data, INTERESTING_PROPERTIES):
    """Extract short keys for cameras and locations from the API response."""
    cams_keys = data.get("data", {}).get("cams", {}).get("key", {})
    locs_keys = data.get("data", {}).get("locs", {}).get("key", {})

    # Map properties to short keys for cams
    short_key_cams = {
        prop: short
        for prop in INTERESTING_PROPERTIES
        for short, longname in cams_keys.items()
        if isinstance(longname, str) and prop.lower() in longname.lower()
    }

    # Map properties to short keys for locs
    short_key_locs = {
        prop: short
        for prop in INTERESTING_PROPERTIES
        for short, longname in locs_keys.items()
        if isinstance(longname, str) and prop.lower() in longname.lower()
    }

    return short_key_cams, short_key_locs

def is_daytime_by_coords(latitude, longitude):
    """Determine if it's currently daytime at the given coordinates."""
    try:
        lat = float(latitude)
        lon = float(longitude)
        tz_name = _tz_finder.timezone_at(lat=lat, lng=lon)
        local_tz = ZoneInfo(tz_name)
        location = LocationInfo(latitude=lat, longitude=lon, timezone=tz_name)
        now_local = datetime.now(local_tz)
        s = sun(location.observer, date=now_local.date(), tzinfo=local_tz)
        return s["sunrise"] <= now_local <= s["sunset"]
    except Exception:
        return False
    
def clean_cameras_data(short_key_cams, data_cams):
    """Clean the JSON data by keeping only relevant items."""
    cleaned_file_json = CACHE_DIR / "alertwest_cleaned_json.json"
    cleaned_json = []
    stats = {"thermal":0, "dot":0, "offline":0, "missing":0, "low_res":0}

    date_path = datetime.now().strftime("%Y/%m/%d")

    for cam in tqdm(data_cams, desc="Cleaning cameras", unit="cam"):
        cam_id_cams = cam.get(short_key_cams.get("camId"))
        img_name = cam.get(short_key_cams.get("Screenshot"))
        cam_name = (cam.get(short_key_cams.get("camName")) or "").lower()
        provider = (cam.get(short_key_cams.get("providerName")) or "").lower()
        cam_offline = cam.get(short_key_cams.get("camOffline"))

        # Deletes thermal, DOT, offline cameras and those with missing parameters
        if "thermal" in cam_name:
            stats["thermal"] += 1
            continue
        if "dot" in provider:
            stats["dot"] += 1
            continue
        if cam_offline == 1:
            stats["offline"] += 1
            continue
        if not cam_id_cams or not img_name:
            stats["missing"] += 1
            continue

        img_url = (
            f"https://img.cdn.prod.alertwest.com/data/img/"
            f"{cam.get(short_key_cams['camId'])}/{date_path}/"
            f"{cam.get(short_key_cams['Screenshot'])}"
        )

        try:
            resp = requests.get(img_url, timeout=5)
            img = Image.open(BytesIO(resp.content))
            width, _ = img.size

            # Skip low-resolution images
            if width < 640:
                stats["low_res"] += 1
                continue

        except Exception:
            stats["missing"] += 1
            continue

        cleaned_json.append(cam)

    print(
        f"\nSkipped {stats['thermal']} thermal cameras, {stats['dot']} DOT cameras, {stats['offline']} offline cameras among {len(data_cams)} total cameras."
    )
    print(
        f"Skipped {stats['low_res']} low-resolution cameras (<640px width) among {len(data_cams)} total cameras."
    )
    print(
        f"Miss a parameter in the json to construct URL for {stats['missing']} cameras among {len(data_cams)} total cameras."
    )

    # Store cleaned JSON
    with open(cleaned_file_json, "w") as f:
        json.dump(cleaned_json, f)

    return cleaned_json

def filter_night_cameras(cleaned_json, data_locs, short_key_locs):
    """Filter out cameras that are currently in nighttime."""
    filtered_cams = []
    night_cams_ = 0

    locs_by_id = {loc.get("id"): loc for loc in data_locs if loc.get("id")}

    for cam in cleaned_json:
        loc_id = cam.get("lid")
        loc = locs_by_id.get(loc_id)

        if not loc:
            continue

        lat = loc.get(short_key_locs.get("locLat"))
        lon = loc.get(short_key_locs.get("locLon"))

        if lat is None or lon is None:
            continue

        if not is_daytime_by_coords(lat, lon):
            night_cams_ += 1
            continue

        filtered_cams.append(cam)

    print(
        f"Skipped {night_cams_} nighttime cameras "
        f"out of {len(cleaned_json)} cleaned cameras."
    )

    with open(CACHE_DIR / "alertwest_daytime_filtered_json.json", "w") as f:
        json.dump(filtered_cams, f)

    return filtered_cams

def split_json(data, n_raspberry, raspberry_id):
    """Split cameras across Raspberry Pi instances."""
    splitted_for_me = []

    for rid in range(n_raspberry):
        subset = [cam for idx, cam in enumerate(data) if idx % n_raspberry == rid]

        with open(CACHE_DIR / f"alertwest_split_raspberry_{rid}.json", "w") as f:
            json.dump(subset, f)

        if rid == raspberry_id:
            splitted_for_me = subset

    return splitted_for_me

def save_cache(short_key_cams, short_key_locs, locs):
    """Save keys and locations required for refresh cycles."""
    with open(CACHE_DIR / "alertwest_keys.json", "w") as f:
        json.dump(
            {
                "short_key_cams": short_key_cams,
                "short_key_locs": short_key_locs,
                "locs": locs,
            },
            f,
        )