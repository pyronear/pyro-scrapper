"""Utility functions for the AlertWest spiders."""

from .config import (
    INTERESTING_PROPERTIES,
)


def extract_keys(data):
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
