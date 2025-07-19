import os
import logging

logger = logging.getLogger(__name__)

def create_missing_txt_files(directory, filenames):
    os.makedirs(directory, exist_ok=True)
    for fn in filenames:
        path = os.path.join(directory, fn)
        if not os.path.isfile(path):
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    pass  # create empty file
                logger.info(f"Created missing file: {path}")
            except Exception as e:
                logger.error(f"Failed to create {path}: {e}")
