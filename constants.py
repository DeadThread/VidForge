"""
Centralised project constants and simple helpers.
All paths are *relative to the project root* (the folder containing this file),
so the app works no matter where the project is copied or which drive it’s on.
"""

from pathlib import Path
import re

# ── Project‑root ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent      # …/VidForge/   (or whatever)

# ── Config / assets / logs paths ────────────────────────────────────
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)                 # ensure it exists

CONFIG_FILE         = CONFIG_DIR / "config.ini"

ASSETS_DIR = BASE_DIR / "assets"
TEMPL_DIR  = ASSETS_DIR / "Photoshop Templates"

LOG_DIR    = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)                   # ensure logs folder exists

ICON_PATH  = ASSETS_DIR / "TagForge.ico"

# ── Video extensions, regexes, etc. ─────────────────────────────────
VIDEO_EXT = (
    ".mp4", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".webm",
    ".ts", ".mpg", ".mpeg"
)

STATE_ABBR = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY"
}

RES_RE      = re.compile(r"(2160|1440|1080|720|480|360|240)p?", re.I)

FORMAT_LIST = [
    "2160p", "1080p", "720p", "480p", "LQ", "4k", "WEBRIP", "STREAMRIP", "BLU-RAY", "DVD", 
]

ADDITIONAL_LIST = [
    "FLAC16", "FLAC24", "SBD", "AUD", "MTX", "DAT", "FM"
]