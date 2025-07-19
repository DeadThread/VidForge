VidForge

VidForge is a powerful desktop application to organize, tag, and rename video files and video folders. It features dynamic, artist-aware Photoshop template selection, customizable naming schemes, and batch processing with a user-friendly Tkinter GUI.
Features

- Flexible tagging and renaming of video files/folders with customizable naming schemes

- Dynamic dropdown menus for selecting artists and Photoshop poster templates

- Supports per-artist and generic Photoshop template folders

- Real-time log panel and queue processing system

- Integrated naming scheme editor popup

- Persistent UI states and theme support

- Easy re-scan of template folders and live metadata refresh

Installation

- Clone the repository:
```
    git clone https://github.com/yourusername/vidforge.git
    cd vidforge
```
(Optional) Create and activate a Python virtual environment:
```
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```
Install required dependencies:
```
    pip install -r requirements.txt
```
Configure your environment and assets:

- Place Photoshop templates under assets/Photoshop Templates/
  
- Customize your Artists.txt, Venues.txt, and Cities.txt files as needed
  
- Configure your output and root folders within the app or config files

Usage

Run the app with:
```
python VidForge.py
```
- Use the File > Open Root Folder menu to select your media folder

- Use the Edit menu to modify artists, venues, cities, or naming schemes

- Select artist and templates from the dropdowns; template selection supports random or specific PSDs per artist

- Use the queue to save, process, or remove selected folders

-  View live logs in the right panel for process feedback

- Use the Tools menu to select Photoshop location and re-scan templates as needed

- Toggle "Make Poster?" to enable or disable template selection

Folder Structure

vidforge/
├── assets/
│   └── Photoshop Templates/
│       ├── Generic/
│       │   └── Generic.psd
│       ├── Artist1/
│       │   └── Artist1.psd
│       └── ...
├── gui/
├── utils/
├── VidForge.py
├── requirements.txt
├── README.md
└── ...

Configuration

- Artists.txt, Venues.txt, Cities.txt are simple text files for dropdown auto-complete

- Photoshop templates are organized by artist folder inside assets/Photoshop Templates/

- Naming schemes are editable via the Change Naming Scheme dialog

Dependencies

- Python 3.10+

- Tkinter (usually bundled with Python)

- Mutagen (for audio tagging)

- Pillow (if used for image handling)

- Other dependencies as listed in requirements.txt

Contributing

Contributions are welcome! Feel free to:

- Open issues for bugs or feature requests

- Fork the repo and submit pull requests

- Improve documentation or test cases

License

- This project is licensed under the MIT License. See the LICENSE file for details.
Contact

Created and maintained by DeadThread
