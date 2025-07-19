import os
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

def generate_poster(
    PS_EXE,
    artist,
    md,
    dest_dir,
    last_job,
    make_poster,
    template_sel,
    template_folder,
    tpl_map,
    templ_dir,
    close_photoshop_func,
    log_func=None
):
    # fallback to logger.info if no log_func provided
    log_func = log_func or logger.info

    # DEBUG log (only if logger is in debug mode)
    logger.debug(f"generate_poster dest_dir: {dest_dir}")

    # 1️⃣ respect per‑file “Make Poster”
    if make_poster != "Yes":
        log_func("Make Poster? No → skip")
        return

    # 1️⃣.a no Photoshop path? skip
    if not PS_EXE:
        log_func("Photoshop path not set → poster skipped")
        return

    poster_artist = md.get("artist") or artist

    # 2️⃣ resolve PSD template
    from utils.template_manager import choose_psd  # avoid circular imports

    template = choose_psd(
        poster_artist,
        template_sel,
        template_folder,
        tpl_map,
        templ_dir,
    )
    if not template:
        log_func("No template chosen → poster skipped")
        return

    # 3️⃣ run Photoshop
    template = template.replace("\\", "/")
    poster_png = os.path.join(dest_dir, "Poster.png").replace("\\", "/")
    poster_psd = os.path.join(dest_dir, "Poster.psd").replace("\\", "/")
    jsx_path = os.path.join(dest_dir, "poster_gen.jsx")

    def js_escape(s: str) -> str:
        return (
            s.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("'", "\\'")
             .replace("\n", "\\n")
             .replace("\r", "")
        )

    log_func(f"Generating poster: artist “{poster_artist}”, template {template}")

    jsx = f'''// VidForge JSX
var d = app.open(new File("{js_escape(template)}"));
var M = {{
"Artist": "{js_escape(poster_artist)}",
"Date"  : "{js_escape(md.get('date', ''))}",
"Venue" : "{js_escape(md.get('venue', ''))}",
"City"  : "{js_escape(md.get('city',  ''))}"
}};
for (var k in M) {{
try {{
    var l = d.artLayers.getByName(k);
    if (l.kind == LayerKind.TEXT) l.textItem.contents = M[k];
}} catch(e) {{}}
}}
d.saveAs(new File("{js_escape(poster_psd)}"));
d.saveAs(new File("{js_escape(poster_png)}"), new PNGSaveOptions(), true);
d.close(SaveOptions.DONOTSAVECHANGES);
'''

    try:
        with open(jsx_path, "w", encoding="utf-8") as fh:
            fh.write(jsx)
        log_func(f"JSX created: {jsx_path}")

        log_func(f"Launching Photoshop: {PS_EXE}")
        subprocess.Popen(
            [PS_EXE, "-r", jsx_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # wait max 3 minutes for poster to be generated
        start = time.time()
        while time.time() - start < 180 and not os.path.isfile(poster_png):
            time.sleep(2)

        if os.path.isfile(poster_png):
            log_func(f"Poster PNG created: {poster_png}")
        else:
            log_func("Poster generation timeout")

        try:
            os.remove(jsx_path)
        except Exception:
            pass

        if last_job:
            close_photoshop_func()

    except Exception as e:
        log_func(f"Photoshop error: {e}")
        logger.exception(e)

def close_photoshop():
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "Photoshop.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
