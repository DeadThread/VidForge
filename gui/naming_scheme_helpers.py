import json
import re
from datetime import datetime
from utils.evaluator import Evaluator
from constants import CONFIG_FILE, SAMPLE_META
from pathlib import Path
from gui.gui_helpers import _row

# ═══════════════════════════════════════════════════════════════════════
#                        naming‑scheme helpers
# ═══════════════════════════════════════════════════════════════════════

def get_naming_scheme_from_config(app):
    print("[DEBUG] Attempting to read naming_scheme from config.ini")
    try:
        scheme_str = app.config_parser.get("Settings", "naming_scheme", fallback=None)
        print(f"[DEBUG] Raw naming_scheme string from config: {scheme_str}")
        
        if scheme_str:
            try:
                loaded = json.loads(scheme_str)
                print(f"[DEBUG] Parsed naming_scheme JSON: {loaded}")
                print(f"[DEBUG] Successfully returning loaded scheme: {loaded}")
                return loaded
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON decode error: {e}, returning raw string")
                return scheme_str
        else:
            print("[DEBUG] No naming_scheme found in config")
            return None
            
    except Exception as e:
        print(f"[ERROR] Unexpected exception in get_naming_scheme_from_config: {e}")
        import traceback
        traceback.print_exc()
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
    print(f"[DEBUG] Saving naming scheme to config.ini: {new_scheme}")
    # 1. Persist to config.ini
    scheme_str = json.dumps(new_scheme, ensure_ascii=False)
    app.naming_scheme = new_scheme
    if not app.config_parser.has_section("Settings"):
        app.config_parser.add_section("Settings")
    app.config_parser.set("Settings", "naming_scheme", scheme_str)

    # 2. Handle root-folder
    root_folder = _extract_root(new_scheme.get("folder", "")) or "(Root)"
    print(f"[DEBUG] Extracted root folder from naming scheme: {root_folder}")
    if root_folder != "(Root)":
        app.config_parser.set("Settings", "output_folder", root_folder)
        app.output_dir.set(root_folder)
    else:
        if app.config_parser.has_option("Settings", "output_folder"):
            app.config_parser.remove_option("Settings", "output_folder")
        app.output_dir.set("")

    # Make sure config directory exists
    Path(CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        app.config_parser.write(fh)
    print("[DEBUG] Naming scheme saved successfully to config.ini")

def reset_naming_scheme_from_menu(app):
    """Restore the built‑in defaults for folder / filename scheme."""
    print("[DEBUG] Resetting naming scheme to defaults")
    
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

    # Use correct config file path, ensure directory exists
    Path(CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
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

def load_naming_scheme_on_startup(app):
    print("[DEBUG] === load_naming_scheme_on_startup CALLED ===")
    
    try:
        scheme = get_naming_scheme_from_config(app)
        print(f"[DEBUG] Scheme after get_naming_scheme_from_config: {scheme}")
        print(f"[DEBUG] Scheme type: {type(scheme)}, bool value: {bool(scheme)}")
        
        if scheme and isinstance(scheme, dict):
            print("[DEBUG] Valid scheme found, applying to app...")
            
            # Update internal state
            app.naming_scheme = scheme
            app.folder_scheme = scheme.get("folder", "%artist%/$year(date)")
            app.filename_scheme = scheme.get("filename", "%artist% - %date% - %venue% - %city% [%format%] [%additional%]")

            # Handle output folder from the scheme's folder pattern
            folder_pattern = scheme.get("folder", "")
            extracted_root = _extract_root(folder_pattern)
            
            if extracted_root:
                print(f"[DEBUG] Extracted root folder from scheme: {extracted_root}")
                app.output_dir.set(extracted_root)
                if hasattr(app, "output_folder_var"):
                    app.output_folder_var.set(extracted_root)
            else:
                # Check if there's a separate output_folder setting in config
                output_folder = app.config_parser.get("Settings", "output_folder", fallback="(Root)")
                print(f"[DEBUG] Using output folder from config: {output_folder}")
                app.output_dir.set(output_folder if output_folder else "(Root)")
                if hasattr(app, "output_folder_var"):
                    app.output_folder_var.set(output_folder if output_folder else "(Root)")
            
            print(f"[DEBUG] Successfully applied naming scheme - folder: {app.folder_scheme}, filename: {app.filename_scheme}")
            print("[DEBUG] === load_naming_scheme_on_startup COMPLETED SUCCESSFULLY ===")
            
        else:
            print("[DEBUG] No valid scheme found or scheme is not a dict, using defaults")
            reset_naming_scheme_from_menu(app)
            
    except Exception as e:
        print(f"[ERROR] Exception in load_naming_scheme_on_startup: {e}")
        import traceback
        traceback.print_exc()
        print("[DEBUG] Falling back to default naming scheme due to error")
        reset_naming_scheme_from_menu(app)