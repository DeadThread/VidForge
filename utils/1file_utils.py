import os
import time
from datetime import datetime

def touch(path, date_str=None):
    """
    Update file's modified and accessed time.
    date_str expected as 'YYYY-MM-DD' or None.
    """
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            mod_time = dt.timestamp()
        except Exception:
            mod_time = time.time()
    else:
        mod_time = time.time()

    os.utime(path, (mod_time, mod_time))  # Update the file timestamp
