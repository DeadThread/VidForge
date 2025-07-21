"""
Centralized project constants and simple helpers.
All paths are *relative to the project root* (the folder containing this file),
so the app works no matter where the project is copied or which drive it’s on.
"""

from pathlib import Path
import re

# ── Project-root ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # Root of the project

# ── Config / Assets / Logs Paths ────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent  # This gets the folder where the current script is located

CONFIG_DIR  = BASE_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)                 # Ensure it exists

CONFIG_FILE         = CONFIG_DIR / "config.ini"

ASSETS_DIR = BASE_DIR / "assets"
TEMPL_DIR  = ASSETS_DIR / "Photoshop Templates"

GENERIC_DIR = TEMPL_DIR / "Generic"  # Path to the 'Generic' folder within Photoshop Templates

LOG_DIR    = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)                   # Ensure logs folder exists

ICON_PATH  = ASSETS_DIR / "TagForge.ico"

# ── Cache Files ─────────────────────────────────────────────────────
CACHE_FILE = CONFIG_DIR / 'cache.json'
CACHE_DROPDOWN_FILE = CONFIG_DIR / 'dropdown_cache.json'

DEFAULT_FOLDER_SCHEME = "%artist%/$year(date)/%filename%"
DEFAULT_FILENAME_SCHEME = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"


# ── Text Files ──────────────────────────────────────────────────────
TXT_FILES = ["Artists.txt", "Cities.txt", "Venues.txt"]

# ── Video Extensions, Regexes, etc. ─────────────────────────────────
VIDEO_EXT = (
    ".mp4", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".webm",
    ".ts", ".mpg", ".mpeg"
)

# ── State Abbreviations ─────────────────────────────────────────────
STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", 
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", 
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", 
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", 
    "VT", "VA", "WA", "WV", "WI", "WY"
}

# ── Resolution Regex ────────────────────────────────────────────────
RES_RE = re.compile(r"(2160|1440|1080|720|480|360|240)p?", re.I)

# ── Supported Formats ───────────────────────────────────────────────
FORMAT_LIST = [
    "2160p", "1080p", "720p", "480p", "LQ", "4k", "WEBRIP", "STREAMRIP", 
    "BLU-RAY", "DVD"
]

# ── Additional Formats ──────────────────────────────────────────────
ADDITIONAL_LIST = [
    "FLAC16", "FLAC24", "SBD", "AUD", "MTX", "DAT", "FM"
]

# ── Default Preview Data (used when the calling app has no live meta) ──
SAMPLE_META = {
    "artist":     "Phish",
    "date":       "1995-12-31",
    "venue":      "Madison Square Garden",
    "city":       "New York, NY",
    "format":     "2160p WEBRIP",
    "additional": "SBD",
    "year": "1995"
    # no output_folder here → we’ll fall back to the root_path argument
}

# ── Recognized Tokens (for the token list) ──────────────────────────
TOKENS = [
    "%artist%", "%date%", "%venue%", "%city%", "%format%", "%additional%",
    "%filename%", "%formatN%", "%formatN2%", "%additionalN%", "%additionalN2%",
    "$upper(text)", "$lower(text)", "$title(text)", "$substr(text,start[,end])",
    "$left(text,n)", "$right(text,n)", "$replace(text,search,replace)",
    "$len(text)", "$pad(text,n,ch)", "$add(x,y)", "$sub(x,y)", "$mul(x,y)",
    "$div(x,y)", "$eq(x,y)", "$lt(x,y)", "$gt(x,y)", "$and(x,y,…)",
    "$or(x,y,…)", "$not(x)", "$datetime()", "$year(date)", "$month(date)",
    "$day(date)", "$if(cond,T,F)", "$if2(v1,v2,…,fallback)",
]
