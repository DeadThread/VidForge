import os
import logging
import configparser
from constants import CONFIG_FILE

log = logging.getLogger("vidforge")

def get_photoshop_path() -> str:
    """Return the Photoshop executable path from config.ini or ''."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    path = config.get("Settings", "photoshop_path", fallback="").strip()
    if path and os.path.isfile(path):
        log.info(f'Loaded Photoshop path: "{path}"')
        return path

    if path:
        log.warning(f'Photoshop path in config.ini is invalid: "{path}"')
    return ""

def save_photoshop_path(path: str) -> None:
    """Save the Photoshop path to config.ini under [Settings]."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    if "Settings" not in config:
        config["Settings"] = {}

    config.set("Settings", "photoshop_path", path)

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        config.write(fh)

    log.info(f'Saved Photoshop path to config.ini: "{path}"')
