import json
import os
from utils.metadata_manager import normalize_name

CACHE_FILE = os.path.join('config', 'cache.json')

def load_cache() -> dict:
    """Load the cache from the cache file."""
    if not os.path.exists(CACHE_FILE):
        return {}  # Return empty dict if cache doesn't exist
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[cache_utils] Error loading cache: {e}")
        return {}

def is_cache_valid() -> bool:
    """Check if the cache file is valid based on modification times."""
    if not os.path.isfile(CACHE_FILE):
        return False  # Cache is invalid if it doesn't exist

    cache_mtime = os.path.getmtime(CACHE_FILE)
    TXT_FILES = ["Artists.txt", "Cities.txt", "Venues.txt"]
    for fname in TXT_FILES:
        path = os.path.join('assets', fname)
        if not os.path.isfile(path) or os.path.getmtime(path) > cache_mtime:
            return False  # Cache is outdated if any TXT file is newer or missing
    return True  # Cache is valid if no TXT file is newer

def build_normalized_map(raw: list) -> dict:
    """Return a dictionary mapping normalized names to original names."""
    return {normalize_name(x): x for x in raw}

def load_txt_file(filename: str) -> list:
    """Load and return the lines of a text file (non-empty)."""
    file_path = os.path.join('assets', filename)
    if os.path.isfile(file_path):
        with open(file_path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []  # Return an empty list if file doesn't exist or is empty

def get_txt_file_path(filename: str) -> str:
    """Return the full path for a given text file."""
    return os.path.join('assets', filename)

def cache_get_list(cache: dict, key: str) -> list:
    """Return the list stored under the given key in the cache (or an empty list if the key doesn't exist)."""
    val = cache.get(key)
    if isinstance(val, list):
        return val
    return []

def cache_add_value(cache: dict, key: str, value, max_len: int = 50) -> None:
    """
    Add *value* to the head of list *key*, drop duplicates, cap length, and persist the cache.
    Handles both string and list values.
    """
    if isinstance(value, list):
        # Clean each item in list
        cleaned = [str(v).strip() for v in value if str(v).strip()]
    else:
        # Single string value
        cleaned = [str(value).strip()]
    if not cleaned:
        return

    existing = cache_get_list(cache, key)
    # Remove any items from existing that are in cleaned (to avoid duplicates)
    existing = [v for v in existing if v not in cleaned]

    # Insert new cleaned values at front preserving order
    new_list = cleaned + existing
    cache[key] = new_list[:max_len]
    save_cache(cache)  # Save immediately

def save_cache(cache: dict) -> None:
    """Save the cache dictionary to the cache file (in JSON format)."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[cache_utils] Error saving cache: {e}")
