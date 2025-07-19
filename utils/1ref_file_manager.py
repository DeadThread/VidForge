import os
from utils.text_utils import normalize_name
from constants import ASSETS_DIR
from utils.logger_setup import logger

def load_reference_list(filename):
    d = {}
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    d[normalize_name(ln)] = ln
    logger.debug(f"Loaded {len(d)} entries from {filename}")
    return d

def add_to_reference(category, value, artist_dict, venue_dict, city_dict, hist_additional):
    if not value or not value.strip():
        logger.info(f"Skipped empty {category}")
        return

    value = value.strip()
    norm_val = normalize_name(value)

    logger.info(f"Checking {category}: '{value}' normalized to '{norm_val}'")

    if category == "artist":
        ref_dict = artist_dict
        path = os.path.join(ASSETS_DIR, "Artists.txt")
    elif category == "venue":
        ref_dict = venue_dict
        path = os.path.join(ASSETS_DIR, "Venues.txt")
    elif category == "city":
        ref_dict = city_dict
        path = os.path.join(ASSETS_DIR, "Cities.txt")
    elif category == "additional":
        if value in hist_additional:
            return
        hist_additional.add(value)
        # Optional: write to Additional.txt here if you want
        return
    else:
        return  # unknown category

    if norm_val in ref_dict:
        return

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(value + "\n")
        ref_dict[norm_val] = value
        logger.info(f"Added new {category}: {value} to {os.path.basename(path)}")
    except Exception as e:
        logger.error(f"Failed to add {category} '{value}': {e}")
