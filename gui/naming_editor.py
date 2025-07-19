#!/usr/bin/env python3
"""
Naming‑scheme editor (token list • two editors • live preview)
"""

from __future__ import annotations
import os, sys, subprocess, re, datetime, tkinter as tk
from tkinter import ttk, font, messagebox
import json
from utils.logger_setup import logger

# ── default preview data (used when the calling app has no live meta) ──
SAMPLE_META = {
    "artist":     "Phish",
    "date":       "2025-06-20",
    "venue":      "SNHU Arena",
    "city":       "Manchester, NH",
    "format":     "2160p WEBRIP",
    "additional": "SBD",
    # no output_folder here → we’ll fall back to the root_path argument
}

# ── recognised tokens (just for the list on the left) ──
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

# ════════════════════════════════════════════════════════════════════════
#                               evaluator
# ════════════════════════════════════════════════════════════════════════
class _Evaluator:
    """Evaluator for live preview with token & function support."""

    FUNC_RE = re.compile(r"\$(\w+)\(([^)]*)\)")

    def __init__(self, meta: dict[str, str]):
        self.meta = meta

    def _list_token(self, base: str, all_: list[str], idx: int | None = None) -> str:
        if idx is None:
            return " ".join(all_)
        if 0 <= idx < len(all_):
            return all_[idx]
        return ""

    def _eval_func(self, match: re.Match) -> str:
        func = match.group(1).lower()
        args_raw = match.group(2)
        args = self._split_args(args_raw)

        def resolve(arg: str) -> str:
            arg = arg.strip()
            if arg.startswith("%") and arg.endswith("%"):
                return self.meta.get(arg[1:-1], "")
            if arg in self.meta:
                return self.meta.get(arg, "")
            return arg

        # ── string helpers ───────────────────────────────────────────
        if func == "upper"  and len(args) == 1: return resolve(args[0]).upper()
        if func == "lower"  and len(args) == 1: return resolve(args[0]).lower()
        if func == "title"  and len(args) == 1: return resolve(args[0]).title()
        if func == "len"    and len(args) == 1: return str(len(resolve(args[0])))

        if func == "substr" and 2 <= len(args) <= 3:
            txt = resolve(args[0]); start = int(args[1]); end = int(args[2]) if len(args)==3 else None
            return txt[start:end]

        if func == "left"   and len(args) == 2: return resolve(args[0])[:int(args[1])]
        if func == "right"  and len(args) == 2: return resolve(args[0])[-int(args[1]):]

        if func == "replace" and len(args) == 3:
            return resolve(args[0]).replace(args[1], args[2])

        if func == "pad" and len(args) >= 2:
            txt, n   = resolve(args[0]), int(args[1])
            ch       = args[2] if len(args) == 3 else " "
            return txt.ljust(n, ch)

        # ── date/time helpers ────────────────────────────────────────
        if func == "datetime" and len(args) == 0:
            return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if func in ("year", "month", "day") and len(args) == 1:
            val = resolve(args[0])
            try:
                dt = datetime.datetime.strptime(val, "%Y-%m-%d")
                return {
                    "year":  str(dt.year),
                    "month": f"{dt.month:02d}",
                    "day":   f"{dt.day:02d}"
                }[func]
            except Exception:
                return ""

        # ── math helpers (treat empty/non‑numeric as 0) ──────────────
        def num(a): 
            try:  return float(resolve(a))
            except ValueError: return 0.0

        if func == "add" and len(args)==2: return str(num(args[0]) + num(args[1]))
        if func == "sub" and len(args)==2: return str(num(args[0]) - num(args[1]))
        if func == "mul" and len(args)==2: return str(num(args[0]) * num(args[1]))
        if func == "div" and len(args)==2:
            denom = num(args[1])
            return "∞" if denom == 0 else str(num(args[0]) / denom)

        # ── comparisons / logic (truthy = non‑empty & not "0") ──────
        def truth(a): return bool(resolve(a)) and resolve(a) != "0"

        if func == "eq"  and len(args)==2: return str(resolve(args[0]) == resolve(args[1]))
        if func == "lt"  and len(args)==2: return str(num(args[0]) <  num(args[1]))
        if func == "gt"  and len(args)==2: return str(num(args[0]) >  num(args[1]))

        if func == "and": return str(all(truth(a) for a in args))
        if func == "or":  return str(any(truth(a) for a in args))
        if func == "not" and len(args)==1: return str(not truth(args[0]))

        # ── conditional helpers ─────────────────────────────────────
        if func == "if" and len(args)==3:
            return resolve(args[1]) if truth(args[0]) else resolve(args[2])

        if func == "if2" and len(args) >= 2:
            *candidates, fallback = args
            for cand in candidates:
                val = resolve(cand)
                if val: return val
            return resolve(fallback)

        # unknown function → leave as‑is
        return match.group(0)

    def _split_args(self, s: str) -> list[str]:
        parts = []
        current = []
        in_quotes = False
        quote_char = None
        for c in s:
            if c in ('"', "'"):
                if in_quotes:
                    if c == quote_char:
                        in_quotes = False
                        quote_char = None
                    else:
                        current.append(c)
                else:
                    in_quotes = True
                    quote_char = c
            elif c == ',' and not in_quotes:
                part = "".join(current).strip()
                if part.startswith(("'", '"')) and part.endswith(("'", '"')):
                    part = part[1:-1]
                parts.append(part)
                current = []
            else:
                current.append(c)
        if current:
            part = "".join(current).strip()
            if part.startswith(("'", '"')) and part.endswith(("'", '"')):
                part = part[1:-1]
            parts.append(part)
        return parts

    def eval(self, text: str) -> str:
        res = text

        # Handle %formatN#% tokens and %format%
        fmts = [f.strip() for f in self.meta.get("format", "").split(",") if f.strip()]
        adds = [a.strip() for a in self.meta.get("additional", "").split(",") if a.strip()]

        res = re.sub(
            r"%formatN(\d+)%",
            lambda m: self._list_token("formatN", fmts, int(m.group(1)) - 1),
            res,
        )
        res = res.replace("%formatN%", ", ".join(fmts))
        res = res.replace("%format%", fmts[0] if fmts else "")

        res = re.sub(
            r"%additionalN(\d+)%",
            lambda m: self._list_token("additionalN", adds, int(m.group(1)) - 1),
            res,
        )
        res = res.replace("%additionalN%", ", ".join(adds))
        res = res.replace("%additional%", adds[0] if adds else "")

        # Replace simple %token% except format/additional handled above
        for k, v in self.meta.items():
            if k in ("format", "additional"):
                continue
            res = res.replace(f"%{k}%", v)

        # Recursively evaluate $func(...) tokens until no changes
        prev = None
        while prev != res:
            prev = res
            res = self.FUNC_RE.sub(self._eval_func, res)

        return res

# ════════════════════════════════════════════════════════════════════════
#                             main widget
# ════════════════════════════════════════════════════════════════════════
class SchemeEditor(tk.Toplevel):
    """
    SchemeEditor(master,
                 root_path=app.output_dir.get(),
                 get_live_metadata=lambda: {...},
                 initial_scheme="...",
                 on_save=callable)
    """

    def __init__(self, master=None, *, root_path: str = "(Root)",
                 get_live_metadata=None, initial_scheme=None, on_save=None):
        super().__init__(master)
        self.title("Naming‑Scheme Editor")
        self.geometry("900x520")
        self.minsize(720, 420)

        self._root_path = root_path or "(Root)"
        self._get_meta = get_live_metadata or (lambda: SAMPLE_META)
        self._on_save = on_save

        self._build_gui()
        self._load_initial(initial_scheme)
        self._refresh_preview()  # first paint

    # ───────────────────────────────────────── UI
    def _build_gui(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        helpm = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Help", menu=helpm)
        helpm.add_command(label="Open README", command=self._open_readme)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=8)

        # token list
        left = ttk.Frame(main, padding=4)
        main.add(left, weight=1)
        ttk.Label(left, text="Tokens / Functions").pack(anchor="w")
        self.lb = tk.Listbox(left, activestyle="none", exportselection=False)
        self.lb.pack(side="left", fill="both", expand=True)
        for t in TOKENS:
            self.lb.insert("end", t)
        ttk.Scrollbar(left, command=self.lb.yview).pack(side="right", fill="y")
        self.lb.bind("<Double-Button-1>", self._insert_token)

        # editors & preview
        right = ttk.Frame(main, padding=4)
        main.add(right, weight=3)

        fixed = font.nametofont("TkFixedFont")

        # Create bold font variant for all text fields
        fixed_bold = fixed.copy()
        fixed_bold.configure(weight="bold")

        ttk.Label(right, text="Folder Scheme").pack(anchor="w")
        self.txt_folder = tk.Text(right, height=2, wrap="none", font=fixed_bold)
        self.txt_folder.pack(fill="x")
        self.txt_folder.bind("<<Modified>>", self._on_edit)

        ttk.Label(right, text="Filename Scheme").pack(anchor="w", pady=(6, 0))
        self.txt_file = tk.Text(right, height=2, wrap="none", font=fixed_bold)
        self.txt_file.pack(fill="x")
        self.txt_file.bind("<<Modified>>", self._on_edit)

        ttk.Label(right, text="Live Preview").pack(anchor="w", pady=(6, 0))

        # Get ttk theme's entry background for consistent background color
        style = ttk.Style(self)
        bg_col = style.lookup("TEntry", "fieldbackground") or "#eaeaea"

        # Helper to invert hex color
        def invert_color(color_str):
            if not color_str.startswith("#") or len(color_str) != 7:
                return color_str  # fallback
            r = 255 - int(color_str[1:3], 16)
            g = 255 - int(color_str[3:5], 16)
            b = 255 - int(color_str[5:7], 16)
            return f"#{r:02x}{g:02x}{b:02x}"

        # Get folder scheme selection colors
        folder_sel_bg = self.txt_folder.cget("selectbackground") or "#3399FF"
        folder_sel_fg = self.txt_folder.cget("selectforeground") or "#FFFFFF"

        # Invert for live preview selection colors
        live_sel_bg = invert_color(folder_sel_bg)
        live_sel_fg = invert_color(folder_sel_fg)

        self.txt_prev = tk.Text(
            right,
            height=5,
            wrap="word",
            background=bg_col,
            font=fixed_bold,
            selectbackground=live_sel_bg,
            selectforeground=live_sel_fg
        )
        self.txt_prev.pack(fill="both", expand=True)
        self._make_read_only(self.txt_prev)

        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Reset", command=self._reset).pack(side="right")

    def _make_read_only(self, w: tk.Text):
        # block key presses but allow selection and copy (Ctrl+C)
        def block(event):
            # Allow Ctrl+C to pass through
            if (event.state & 0x4) and event.keysym.lower() == 'c':  # Ctrl+C
                return None  # don't block
            return "break"

        for seq in ("<Key>", "<<Paste>>", "<Control-v>", "<Button-2>"):
            w.bind(seq, block)

        # context menu
        def ctx(e):
            m = tk.Menu(w, tearoff=0)
            m.add_command(label="Copy", command=lambda: w.event_generate("<<Copy>>"))
            m.tk_popup(e.x_root, e.y_root)
            m.grab_release()

        w.bind("<Button-3>", ctx)

    def _insert_token(self, *_):
        token = self.lb.get("active")
        focused_widget = self.focus_get()
        print(f"Focused widget: {focused_widget}")

        if focused_widget not in (self.txt_folder, self.txt_file):
            print("Focus is NOT on folder or file editor. Forcing focus to folder editor.")
            focused_widget = self.txt_folder
            focused_widget.focus_set()

        # Show insertion index for debugging
        insert_pos = focused_widget.index("insert")
        print(f"Inserting token at position: {insert_pos}")

        focused_widget.insert("insert", token)
        self._refresh_preview()

    # ───────────────────────────────────────── helpers
    def _load_initial(self, scheme):
        folder_default = "%artist%/$year(date)"
        filename_default = "%artist% - %date% - %venue% - %city% [%format%] [%additional%]"
        if isinstance(scheme, dict):
            folder_def = scheme.get("folder", folder_default)
            filename_def = scheme.get("filename", filename_default)
        elif isinstance(scheme, (list, tuple)) and len(scheme) == 2:
            folder_def, filename_def = scheme
        elif isinstance(scheme, str):
            folder_def = folder_default
            filename_def = scheme
        else:
            folder_def = folder_default
            filename_def = filename_default
        self.txt_folder.insert("1.0", folder_def)
        self.txt_file.insert("1.0", filename_def)

    def _on_edit(self, e):
        e.widget.edit_modified(False)
        self._refresh_preview()

    # ───────────────────────────────────────── preview
    def _refresh_preview(self):
        print("Refreshing preview...")
        meta = self._get_meta() or {}
        folder_scheme = self.txt_folder.get("1.0", "end-1c")
        file_scheme = self.txt_file.get("1.0", "end-1c")
        print(f"Folder scheme: {folder_scheme}")
        print(f"File scheme: {file_scheme}")
        
        ev = _Evaluator(meta)
        evaluated_file = ev.eval(file_scheme)
        
        meta_with_filename = meta.copy()
        meta_with_filename["filename"] = evaluated_file
        ev2 = _Evaluator(meta_with_filename)
        evaluated_folder = ev2.eval(folder_scheme)

        is_abs_path = os.path.isabs(evaluated_folder) or re.match(r"^[a-zA-Z]:[\\/]", evaluated_folder)
        if is_abs_path:
            preview_path = os.path.join(evaluated_folder, evaluated_file)
        else:
            root_folder = meta.get("output_folder") or self._root_path or "(Root)"
            preview_path = os.path.join(root_folder, evaluated_folder, evaluated_file)

        # Fix mixed slashes here:
        preview_path = os.path.normpath(preview_path)

        if len(preview_path) > 400:
            preview_path = preview_path[:397] + "…"

        self.txt_prev.config(state="normal")
        self.txt_prev.delete("1.0", "end")
        self.txt_prev.insert("1.0", preview_path)
        self.txt_prev.config(state="disabled")

    # ───────────────────────────────────────── buttons
    def _save(self):
        folder_scheme = self.txt_folder.get("1.0", "end-1c")
        filename_scheme = self.txt_file.get("1.0", "end-1c")
        new_scheme = {"folder": folder_scheme, "filename": filename_scheme}

        if callable(self._on_save):
            self._on_save(new_scheme)

        self.destroy()

    def _reset(self):
        self.txt_folder.delete("1.0", "end")
        self.txt_file.delete("1.0", "end")
        self._load_initial(None)
        self._refresh_preview()

    # ───────────────────────────────────────── README
    def _open_readme(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "read_me_scheme.md")
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open README: {e}")


# stand‑alone test
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    SchemeEditor(root, root_path=r"C:\Videos\Finished").wait_window()


# outside the class
NamingEditor = SchemeEditor
