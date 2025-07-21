import json
import os
from typing import Any, Dict, List, Callable
from utils.metadata_manager import normalize_name
from constants import ASSETS_DIR, CONFIG_DIR, CACHE_FILE, CACHE_DROPDOWN_FILE, TXT_FILES, FORMAT_LIST, ADDITIONAL_LIST  # Importing constants

def _ensure_dirs() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)

def initialize_dropdown_cache() -> dict:
    """Initialize the dropdown cache from the JSON file under /config directory."""
    if os.path.exists(CACHE_DROPDOWN_FILE):
        try:
            with open(CACHE_DROPDOWN_FILE, "r") as f:
                data = json.load(f)
                return data  # Return the loaded data
        except Exception as e:
            print(f"Error loading dropdown cache: {e}")
    return {}  # Return an empty dict if the file doesn't exist

def load_cache(log_func: Callable[[str], None] = print) -> Dict[str, Any]:
    _ensure_dirs()
    if _txts_newer_than_cache():
        log_func("Cache missing/outdated – rebuilding …")
        data: Dict[str, Any] = {}
        for fname in TXT_FILES:
            raw = _load_txt(fname)
            data[fname] = raw
            data[f"normalized_{fname}"] = _norm_map(raw)
            log_func(f"  → {fname}: {len(raw)} lines")
        save_cache(data, log_func)
        return data

    try:
        with open(CACHE_FILE, encoding="utf-8") as fh:
            cache = json.load(fh)
        log_func(f"Loaded cache from {CACHE_FILE}")
        return cache
    except Exception as e:
        log_func(f"Cache read error ({e}) – rebuilding …")
        return load_cache(log_func)

def save_cache(data: Dict[str, Any], log_func: Callable[[str], None] = print) -> None:
    _ensure_dirs()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        log_func(f"Cache saved → {CACHE_FILE}")
    except Exception as exc:
        log_func(f"[cache_manager] Failed to write cache: {exc}")

def _load_txt(name: str) -> List[str]:
    path = os.path.join(ASSETS_DIR, name)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip()]
    return []

def _txts_newer_than_cache() -> bool:
    if not os.path.isfile(CACHE_FILE):
        return True
    cache_mtime = os.path.getmtime(CACHE_FILE)
    for fname in TXT_FILES:
        path = os.path.join(ASSETS_DIR, fname)
        if not os.path.isfile(path) or os.path.getmtime(path) > cache_mtime:
            return True
    return False

def _norm_map(raw: List[str]) -> Dict[str, str]:
    return {normalize_name(x): x for x in raw}

def cache_get_list(cache: Dict[str, Any], key: str) -> List[str]:
    return cache.get(key, [])

def cache_add_value(cache: Dict[str, Any], key: str, value: str, max_len: int = 50) -> None:
    value = value.strip()
    if not value:
        return
    lst = cache.get(key, [])
    if value in lst:
        lst.remove(value)
    lst.insert(0, value)
    cache[key] = lst[:max_len]
    save_cache(cache, log_func=lambda *_: None)  # silent write

def save_naming_scheme(scheme: Dict[str, str]) -> None:
    """Save the naming scheme dict to a file."""
    _ensure_dirs()
    try:
        with open(os.path.join(CONFIG_DIR, "naming_scheme.json"), 'w', encoding='utf-8') as f:
            json.dump(scheme, f, indent=2, ensure_ascii=False)
        print(f"[DEBUG] Naming scheme saved: {scheme}")
    except Exception as e:
        print(f"[ERROR] Failed to save naming scheme: {e}")

def load_naming_scheme() -> dict:
    """Load the naming scheme dict from file."""
    path = os.path.join(CONFIG_DIR, "naming_scheme.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load naming scheme: {e}")
        return {}

def load_dropdown_cache() -> dict:
    """Load dropdown history cache from file."""
    if not os.path.isfile(CACHE_DROPDOWN_FILE):
        return {}
    try:
        with open(CACHE_DROPDOWN_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_dropdown_cache(format_history: List[str], add_history: List[str]) -> None:
    """Save dropdown history cache to file."""
    data = {
        "format_history": format_history,
        "add_history": add_history,
    }
    try:
        with open(CACHE_DROPDOWN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[cache_manager] Failed to save dropdown cache: {e}")

# Cached dropdown helpers
cache                = load_cache()
DEFAULT_FORMATS      = FORMAT_LIST
DEFAULT_ADDITIONALS  = ADDITIONAL_LIST

def load_format_values() -> list[str]:
    cached = cache_get_list(cache, "Format")
    merged = list(DEFAULT_FORMATS)
    for fmt in cached:
        if fmt not in merged:
            merged.append(fmt)
    return merged

def load_additional_values() -> list[str]:
    vals = cache_get_list(cache, "Additional")
    return vals if vals else DEFAULT_ADDITIONALS

def _load_template_from_path(app, path):
    # Placeholder: implement loading logic here
    app._log(f"Loading template from: {path}")
    # TODO: implement actual loading of the PSD template

def save_selected_files(app):
    selected_ids = app.tree.selection()
    if not selected_ids:
        app._log("No files selected to add to the queue.")
        return

    for item_id in selected_ids:
        file_path = app.tree.set(item_id, "filepath")
        if not file_path:
            continue
        app.current_fp = file_path  # set current file context

        # Import save_current inside the function to avoid circular import
        from utils.queue_helpers import save_current
        save_current(app)  # call your existing queue_helpers save_current()
