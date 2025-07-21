# file_helpers.py
import os
import subprocess
import sys
from tkinter import filedialog, messagebox
import logging
from utils.tree_manager import fast_populate_tree as populate_tree  # Import populate_tree

# Set up logging
logger = logging.getLogger(__name__)

def create_missing_txt_files(directory, filenames):
    """Ensure that the specified text files exist in the given directory."""
    os.makedirs(directory, exist_ok=True)
    for fn in filenames:
        path = os.path.join(directory, fn)
        if not os.path.isfile(path):
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    pass  # Create an empty file
                logger.info(f"Created missing file: {path}")
            except Exception as e:
                logger.error(f"Failed to create {path}: {e}")

def _open_txt_file(assets_dir, filename: str):
    """Open a text file for editing in the default system editor."""
    file_path = os.path.join(assets_dir, filename)
    if os.path.exists(file_path):
        try:
            if sys.platform == 'win32':
                subprocess.Popen(['start', '', file_path], shell=True)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', file_path])
            else:
                subprocess.Popen(['xdg-open', file_path])
        except subprocess.CalledProcessError as e:
            logger.error(f"Error opening {filename} with system editor: {e}")
    else:
        messagebox.showerror("File Not Found", f"The file {filename} does not exist.")

def _maybe_sync_output_dir(output_dir, folder_template: str):
    """Sync output folder with an absolute folder template."""
    abs_check = evaluate_scheme(folder_template, {})
    if os.path.isabs(abs_check):
        root_prefix = os.path.splitdrive(abs_check)[0] or abs_check.split(os.sep)[0]
        if root_prefix and root_prefix != output_dir:
            output_dir = root_prefix
            logger.info(f"Output folder auto-synced to: {root_prefix}")

def _browse(app):
    """Browse for a folder and update root_dir and output_dir."""
    d = filedialog.askdirectory()
    if not d:
        return

    # Remember the new root directory
    app.root_dir.set(d)
    populate_tree(app, d)

    # If output folder isn't set yet, sync it to the root directory
    if not app.output_dir.get():
        app.output_dir.set(d)
        app._log(f"Output folder now follows root → {d}")

def _change_output_folder(config_parser, output_dir):
    """Change the output folder and save to config."""
    d = filedialog.askdirectory(title="Select Output Folder")
    if not d:
        return
    output_dir.set(d)
    config_parser.setdefault("Settings", {})
    config_parser.set("Settings", "output_folder", d)
    with open(CONFIG_FILE, "w") as f:
        config_parser.write(f)
    logger.info(f"Output folder changed to {d}")
