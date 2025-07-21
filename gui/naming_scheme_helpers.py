import json
import re
from datetime import datetime
from utils.evaluator import Evaluator
from constants import CONFIG_FILE, SAMPLE_META
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
#                        naming‑scheme helpers
# ═══════════════════════════════════════════════════════════════════════

def get_naming_scheme_from_config(app):
    """Read naming_scheme from config → return dict or raw string."""
    try:
        scheme_str = app.config_parser.get("Settings", "naming_scheme", fallback=None)
    except Exception:
        return None
    if scheme_str:
        try:
            return json.loads(scheme_str)
        except json.JSONDecodeError:
            return scheme_str
    return None

def _clean_root(path: str) -> str:
    if path in {"(Root)", ""}:
        return ""
    return path.removeprefix("(Root)/")

def _extract_root(pattern: str) -> str | None:
    if not pattern:
        return None
    norm = pattern.replace("\\", "/")
    cuts = [p for p in (norm.find("%"), norm.find("$")) if p >= 0]
    root = norm[:min(cuts)] if cuts else norm
    root = root.rstrip("/")
    return root or None

def handle_special_tokens(template: str, sample_meta: dict) -> str:
    """Handles special tokens in the template string."""
    def repl_year(match):
        date_key = match.group(1)
        date_str = sample_meta.get(date_key, "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return str(dt.year)
        except Exception:
            return ""
    
    template = re.sub(r"\$year\((\w+)\)", repl_year, template)
    for key, value in sample_meta.items():
        template = template.replace(f"%{key}%", str(value))
    
    return template

def get_live_metadata(app) -> dict:
    """Retrieve live metadata from the app."""
    return app._get_live_metadata()

def save_naming_scheme(new_scheme: dict, app):
    """Save the new naming scheme to config.ini and update the app."""
    # 1. Persist to config.ini
    scheme_str = json.dumps(new_scheme, ensure_ascii=False)
    app.naming_scheme = scheme_str
    app.config_parser.setdefault("Settings", {})
    app.config_parser.set("Settings", "naming_scheme", scheme_str)

    # 2. Handle root-folder
    root_folder = _extract_root(new_scheme.get("folder", "")) or "(Root)"
    if root_folder != "(Root)":
        app.config_parser.set("Settings", "output_folder", root_folder)
        app.output_dir.set(root_folder)
    else:
        if app.config_parser.has_option("Settings", "output_folder"):
            app.config_parser.remove_option("Settings", "output_folder")
        app.output_dir.set("")

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        app.config_parser.write(fh)

    # 3. Use the Evaluator class for evaluation
    sample_meta = SAMPLE_META.copy()  # Directly use SAMPLE_META from constants
    evaluator = Evaluator(sample_meta)  # Instantiate Evaluator

    # ── 3a: evaluate the filename
    filename_eval = evaluator.eval(new_scheme.get("filename", ""))

    # ── 3b: inject filename into meta for folder scheme
    sample_meta_with_fn = dict(sample_meta, filename=filename_eval)

    # ── 3c: evaluate the folder scheme
    folder_eval = evaluator.eval(new_scheme.get("folder", ""))

    # 4. Log everything
    app._log(f"Current Folder Scheme (evaluated): {folder_eval}")
    app._log(f"Current Filename Scheme (evaluated): {filename_eval}")
    app._log(f"Output Folder: {root_folder}")


def reset_naming_scheme_from_menu(app):
    """Restore the built‑in defaults for folder / filename scheme."""
    # ── canonical defaults ──────────────────────────────────────────
    default_folder   = "%artist%/$year(date)"
    default_filename = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"

    # ── update in‑memory settings ──────────────────────────────────
    app.naming_scheme = {
        "folder":   default_folder,
        "filename": default_filename,
    }
    app.folder_scheme   = default_folder
    app.filename_scheme = default_filename

    # reset output‑folder field
    app.output_dir.set("(Root)")
    if hasattr(app, "output_folder_var"):
        app.output_folder_var.set("(Root)")

    # ── persist to config.ini ───────────────────────────────────────
    cfg = app.config_parser
    if not cfg.has_section("Settings"):
        cfg.add_section("Settings")

    cfg.set("Settings", "naming_scheme", json.dumps(app.naming_scheme, ensure_ascii=False))
    cfg.set("Settings", "output_folder", "")

    config_path = Path(app.assets_dir, "config", "config.ini")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)

    # ── update open naming scheme editor (if any) ───────────────────
    if getattr(app, "scheme_editor", None) and hasattr(app.scheme_editor, "_reset"):
        app.scheme_editor._reset()

    # ── log what happened ───────────────────────────────────────────
    if hasattr(app, "_log"):
        app._log(
            "Naming scheme and output folder reset to default:\n"
            f"  Folder scheme : {default_folder}\n"
            f"  Filename scheme: {default_filename}\n"
            f"  Output folder  : (Root)"
        )
