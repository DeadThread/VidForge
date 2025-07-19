# utils/cache_manager.py
import json
import os
from typing import Any, Dict, List, Callable
from utils.metadata_manager import normalize_name

CONFIG_DIR = "config"
ASSETS_DIR = "assets"
CACHE_FILE = os.path.join(CONFIG_DIR, 'cache.json')
TXT_FILES = ["Artists.txt", "Cities.txt", "Venues.txt"]

def _ensure_dirs() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)

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

def save_naming_scheme(scheme: str):
    """Save the naming scheme to a file."""
    _ensure_dirs()
    try:
        with open(os.path.join(CONFIG_DIR, "naming_scheme.json"), 'w', encoding='utf-8') as f:
            json.dump({"naming_scheme": scheme}, f, indent=2, ensure_ascii=False)
        print(f"[DEBUG] Naming scheme saved: {scheme}")
    except Exception as e:
        print(f"[ERROR] Failed to save naming scheme: {e}")
