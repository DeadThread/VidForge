"""
utils.queue_manager
-------------------
Move/rename files in the queue, optionally generate posters,
and — per file — override the filesystem modified-date.
"""
from __future__ import annotations

import os
import re
import shutil
import datetime
from typing import Dict, Sequence, List, Any

from utils.logger_setup import logger
from utils.helpers import touch
from utils.text_utils import extract_date  # helper → pulls YYYY-MM-DD from meta/filename
from utils.metadata_manager import reload_metadata
from utils.cache_manager import load_dropdown_cache, save_dropdown_cache
from utils.file_helpers import populate_tree
from tkinter import messagebox

# ────────────────────────────────────────────────────────────────────────
FUNC_RE = re.compile(r"\$(\w+)\(([^)]*)\)")

def _split_args(raw: str) -> list[str]:
    """Simple CSV splitter that respects single/double quotes."""
    parts, cur, quoted, qch = [], [], False, ""
    for ch in raw:
        if ch in {"'", '"'}:
            if quoted and ch == qch:
                quoted = False
            else:
                quoted, qch = True, ch
        elif ch == "," and not quoted:
            parts.append("".join(cur).strip().strip("'\""))
            cur = []
            continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur).strip().strip("'\""))
    return parts


def _truthy(s: str) -> bool:
    return bool(s) and s.lower() not in {"0", "false", "off", "no", "null"}


def resolve_output_base(output_dir: str | None, fallback_root: str) -> str:
    """
    Translate the sentinel '(Root)' (or blank) to the actual root directory
    chosen in the GUI; otherwise return the path given by *output_dir*.
    """
    if not output_dir or output_dir.strip() == "(Root)":
        return fallback_root
    return output_dir


def _apply_scheme(
    pattern: str,
    md: Dict[str, str],
    *,
    artist: str,
    date: str,
    filename: str = ""
) -> str:
    """Replace %tokens% and $func(…) inside *pattern*."""

    year, month, day = md.get("year", ""), md.get("month", ""), md.get("day", "")
    date_tok = (
        f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year and month and day else
        f"{year}-{month.zfill(2)}" if year and month else
        year
    )

    repl: Dict[str, str] = {
        "%artist%": artist,
        "%year%": year or (date[:4] if date else ""),
        "%date%": date_tok or date,
        "%venue%": md.get("venue", ""),
        "%city%": md.get("city", ""),
        "%format%": md.get("format", ""),
        "%additional%": md.get("additional", ""),
        "%filename%": filename,
    }

    fmt_parts = repl["%format%"].split()
    # Split additional on commas, trim spaces and trailing commas
    add_parts = [x.strip().rstrip(",") for x in repl["%additional%"].split(",") if x.strip()]

    def _list_token(prefix: str, parts: list[str], idx: int | None):
        return " ".join(parts) if idx is None else (parts[idx] if 0 <= idx < len(parts) else "")

    def _num_token_sub(m: re.Match):
        base, num = m.group(1), m.group(2)
        idx = int(num) - 1 if num else None
        src = fmt_parts if base.lower().startswith("format") else add_parts
        return _list_token(base, src, idx)

    # Handle numbered tokens with brackets first: e.g. [%additionalN1%]
    pattern = re.sub(r"\[%(formatN|additionalN)(\d*)%]", _num_token_sub, pattern, flags=re.I)
    # Handle unbracketed numbered tokens: %additionalN2%
    pattern = re.sub(r"%(formatN|additionalN)(\d*)%", _num_token_sub, pattern, flags=re.I)

    # Replace regular tokens %artist%, %date%, etc.
    for tok, val in repl.items():
        pattern = pattern.replace(tok, val)

    # Evaluate $func(args) repeatedly until stable
    def _func_sub(m: re.Match) -> str:
        fn = m.group(1).lower()
        args = _split_args(m.group(2))

        def _val(arg: str) -> str:
            if arg.startswith("%") and arg.endswith("%"):
                return repl.get(arg, "")
            if arg in {"artist", "filename"}:
                return {"artist": artist, "filename": filename}[arg]
            if arg == "date":
                return date_tok or date
            return md.get(arg, arg)

        if fn in {"upper", "lower", "title"} and len(args) == 1:
            txt = _val(args[0])
            return getattr(txt, fn)()

        if fn in {"year", "month", "day"} and len(args) == 1:
            d = _val(args[0]) or date
            try:
                dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                return f"{dt.year}" if fn == "year" else f"{getattr(dt, fn):02d}"
            except Exception:
                return ""

        if fn == "len" and len(args) == 1:
            return str(len(_val(args[0])))

        if fn == "substr" and 2 <= len(args) <= 3:
            txt, start = _val(args[0]), int(args[1])
            end = int(args[2]) if len(args) == 3 else None
            return txt[start:end]

        if fn == "left" and len(args) == 2:
            return _val(args[0])[:int(args[1])]

        if fn == "right" and len(args) == 2:
            return _val(args[0])[-int(args[1]):]

        if fn == "replace" and len(args) == 3:
            return _val(args[0]).replace(args[1], args[2])

        if fn == "pad" and len(args) >= 2:
            txt, n = _val(args[0]), int(args[1])
            ch = args[2] if len(args) == 3 and args[2] else " "
            return txt.ljust(n, ch)

        if fn in {"add", "sub", "mul", "div"} and len(args) == 2:
            a, b = float(_val(args[0]) or 0), float(_val(args[1]) or 0)
            try:
                res = {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b}[fn]
                res_s = f"{res}".rstrip("0").rstrip(".") if "." in f"{res}" else f"{res}"
                return res_s
            except ZeroDivisionError:
                return ""

        if fn in {"eq", "lt", "gt"} and len(args) == 2:
            a, b = _val(args[0]), _val(args[1])
            try:
                a_f, b_f = float(a), float(b)
                cmp = (a_f, b_f)
            except ValueError:
                cmp = (a, b)
            ok = {"eq": cmp[0] == cmp[1], "lt": cmp[0] < cmp[1], "gt": cmp[0] > cmp[1]}[fn]
            return "1" if ok else "0"

        if fn == "and":
            return "1" if all(_truthy(_val(x)) for x in args) else "0"
        if fn == "or":
            return "1" if any(_truthy(_val(x)) for x in args) else "0"
        if fn == "not" and len(args) == 1:
            return "0" if _truthy(_val(args[0])) else "1"

        if fn == "if" and len(args) == 3:
            return _val(args[1]) if _truthy(_val(args[0])) else _val(args[2])

        if fn == "if2" and len(args) >= 2:
            *alts, fb = args
            for a in alts:
                v = _val(a)
                if _truthy(v):
                    return v
            return _val(fb)

        if fn == "datetime" and not args:
            return datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

        return m.group(0)  # unknown function → leave untouched

    prev = None
    out = pattern
    while prev != out:
        prev = out
        out = FUNC_RE.sub(_func_sub, out)

    # Cleanup final string
    out = re.sub(r"(?:\s*-\s*){2,}", " - ", out)  # repeated dashes
    out = re.sub(r"\s{2,}", " ", out).strip()

    for sep in (" - ", "--", "- -"):
        while out.startswith(sep):
            out = out[len(sep):].lstrip()
        while out.endswith(sep):
            out = out[:-len(sep)].rstrip()

    return out


def process_queue(
    *,
    queue: Sequence[str],
    meta: Dict[str, Dict[str, Any]],
    root_dir: str,
    log_func,
    generate_poster_func,
    close_photoshop_func,
    tpl_map,
    templ_dir,
    output_dir: str | None = None,
    folder_scheme: str = "",
    filename_scheme: str = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]",
    override_date_flags: List[bool] | None = None,
    current_template_folder: str | None = None,
) -> None:
    if override_date_flags and len(override_date_flags) != len(queue):
        logger.warning("override_date_flags length mismatch → ignoring list")
        override_date_flags = None

    for idx, src in enumerate(queue):
        md = meta.get(src, {})
        date = md.get("date") or extract_date(os.path.basename(src))
        if not date:
            log_func(f"Skip {src}: no date found")
            continue

        artist = md.get("artist", "Unknown")
        base_in = os.path.splitext(os.path.basename(src))[0]

        # Build filename (without extension)
        dest_base = _apply_scheme(
            filename_scheme, md, artist=artist, date=date, filename=base_in
        ) or artist

        # Build folder path (using dest_base)
        folder_sub = _apply_scheme(
            folder_scheme, md, artist=artist, date=date, filename=dest_base
        ) if folder_scheme else ""

        # Determine root directory (handle "(Root)" sentinel)
        raw_output = _apply_scheme(
            output_dir or "(Root)", md, artist=artist, date=date, filename=dest_base
        )
        dest_root = resolve_output_base(raw_output, root_dir)

        # Normalize dest_dir carefully to avoid Windows UNC issues
        dest_dir_raw = os.path.join(dest_root, folder_sub)
        dest_dir = os.path.normpath(dest_dir_raw)

        # Create folder
        os.makedirs(dest_dir, exist_ok=True)

        ext = os.path.splitext(src)[1]
        dest_fp = os.path.join(dest_dir, dest_base + ext)

        try:
            # Move/rename if different path
            if os.path.abspath(src) != os.path.abspath(dest_fp):
                shutil.move(src, dest_fp)
                log_func(f"Moved: {src} → {dest_fp}")

                # Override timestamp if flagged
                flag = (
                    override_date_flags[idx]
                    if override_date_flags is not None
                    else md.get("override_date", False)
                )
                if _truthy(str(flag)):
                    touch(dest_fp, date)

            # IMPORTANT: Make sure dest_dir is absolute, no UNC prefix
            # If path has UNC prefix (\\?\), remove it for Photoshop JSX path usage
            poster_dest_dir = dest_dir[4:] if dest_dir.startswith(r"\\?\\") else dest_dir

            # Generate poster if flagged
            if _truthy(md.get("make_poster", "0")):
                generate_poster_func(
                    artist=artist,
                    md=md,
                    dest_dir=poster_dest_dir,
                    last_job=(idx == len(queue) - 1),
                    make_poster="Yes",
                    template_sel=md.get("template", "Default"),
                    template_folder=current_template_folder,
                )
            else:
                log_func(f"Make Poster? No → skip for {dest_fp}")

        except Exception as e:
            log_func(f"Error processing {src}: {e}")
            logger.exception(e)

    # Cleanup Photoshop session if requested
    if close_photoshop_func:
        try:
            close_photoshop_func()
            log_func("Closed Photoshop.")
        except Exception as exc:
            logger.exception(exc)
            log_func(f"Error closing Photoshop: {exc}")

    log_func("Processing finished.")


def process_queue_with_ui(app) -> None:
    """
    Wrapper to process queue with VideoTagger app UI integration.
    """
    if not app.queue:
        messagebox.showinfo("Queue empty", "Add files first.")
        return
    if not app.root_dir.get():
        messagebox.showerror("No root", "Pick root folder.")
        return

    app._log("Starting queue processing …")

    # Extract folder & filename patterns
    folder_pattern = ""
    filename_pattern = ""
    ns = app.naming_scheme

    if isinstance(ns, dict):
        folder_pattern = ns.get("folder", "")
        filename_pattern = ns.get("filename", "")
    elif isinstance(ns, str):
        stripped = ns.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                import json
                ns_dict = json.loads(stripped)
                if isinstance(ns_dict, dict):
                    folder_pattern = ns_dict.get("folder", "")
                    filename_pattern = ns_dict.get("filename", "")
                else:
                    filename_pattern = stripped
            except json.JSONDecodeError:
                filename_pattern = stripped
        else:
            filename_pattern = stripped

    # Call core processing
    process_queue(
        queue=app.queue,
        meta=app.meta,
        root_dir=app.root_dir.get(),
        log_func=app._log,
        generate_poster_func=app._generate_poster,
        close_photoshop_func=app._close_photoshop if hasattr(app, "_close_photoshop") else None,
        tpl_map=app.tpl_map,
        templ_dir=app.TEMPL_DIR if hasattr(app, "TEMPL_DIR") else "",
        output_dir=app.output_dir.get() or None,
        folder_scheme=folder_pattern,
        filename_scheme=filename_pattern,
        current_template_folder=getattr(app, "_current_artist", None),
    )

    # Clear UI queue
    from utils.queue_helpers import clear_queue
    clear_queue(app)
    app._log("Queue processed and cleared.")

    # Reload metadata
    reload_metadata(app)
    app._log("Metadata reloaded after queue processing.")

    # Save dropdown cache - assuming your app.hist has keys 'format_history', 'add_history'
    save_dropdown_cache(app.hist, app.queue)
    app._log("Dropdown cache saved.")

    # Update combobox history from cache
    cache = load_dropdown_cache()
    format_hist = cache.get("format_history", [])
    add_hist = cache.get("add_history", [])

    current_format = app.v_format.get().strip()
    current_add = app.v_add.get().strip()

    if current_format:
        format_hist = [current_format] + [f for f in format_hist if f != current_format]
    if current_add:
        add_hist = [current_add] + [a for a in add_hist if a != current_add]

    save_dropdown_cache(format_hist, add_hist)

    app.ent_format['values'] = format_hist
    app.ent_add['values'] = add_hist

    app.v_format.set(current_format)
    app.v_add.set(current_add)

    # Reload metadata again if needed
    reload_metadata(app)

    # Refresh directory tree if root directory exists
    if app.root_dir.get():
        populate_tree(app, app.root_dir.get())
