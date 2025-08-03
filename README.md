[![VidForge Screenshots](https://i.imgur.com/Szo3tsc.png)](https://imgur.com/a/XOPU0n3)

## Overview

**VidForge** is a powerful desktop application to organize, tag, and rename video files and folders using flexible naming schemes and artist-aware poster templates. It features a user-friendly Tkinter GUI, live logging, Photoshop integration, and dynamic queue processing.

**SchemeEditor**, integrated into VidForge or usable standalone, enables users to define **custom folder and filename naming schemes** using a combination of **metadata tokens** and **formatting functions**. This allows total control over how your files and directories are named.

---

## Features

* Flexible tagging and renaming of media using custom naming schemes
* Integrated naming scheme editor with live preview and function/tokens list
* Dynamic dropdowns for selecting artists and Photoshop templates
* Batch processing and queue system
* Real-time log output panel
* Persistent theme and UI settings
* Supports both per-artist and generic PSD templates
* Quick access to edit lists: Artists, Venues, Cities
* Right-click to copy preview

---

## Installation

```bash
git clone https://github.com/yourusername/vidforge.git
cd vidforge
```

(Optional) Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

* Place Photoshop templates under:

  ```
  assets/Photoshop Templates/
  ```
* Use subfolders for artist-specific templates (e.g., `assets/Photoshop Templates/Phish/`)
* Edit `Artists.txt`, `Venues.txt`, and `Cities.txt` for dropdown options
* Configure output paths and other settings via the GUI or config file
* Use Generic.psd as a starting point to create your own templates. Modify the background, reposition text layers as needed, and ensure the layers for Artist, Venue, and City remain intact so they can be read correctly by the application.

---

## Usage

```bash
python VidForge.py
```

* Use **File > Open Root Folder** to select your media directory
* Choose an artist and template using the dropdown menus
* Enable or disable "Make Poster?" to control PSD selection
* Use the **Edit** menu to modify metadata lists and naming schemes
* View real-time logs in the side panel
* Use **Tools > Set Photoshop Location** and **Rescan Templates** as needed
* Process folders via the queue with Save/Process/Remove actions

---

## Folder Structure

```
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
```

---

## SchemeEditor - Custom Naming Schemes

### Overview

`SchemeEditor` is a Python script built with `Tkinter` that allows users to create and test customizable naming schemes for their media files. It provides a user-friendly interface for inserting tokens (placeholders for metadata), functions (for data manipulation), and conditional logic to format filenames based on various metadata fields.

### Main Features

* **Tokens**: Insert placeholders for artist, date, venue, city, format, and additional metadata
* **Functions**: Perform text, math, date, and logical operations
* **Preview**: Live preview of evaluated filename/folder
* **Save Scheme**: Store schemes for reuse
* **Reset Default**: Revert to default layout
* **Right-click**: Copy evaluated preview to clipboard

---

### Tokens

Tokens represent pieces of metadata that will be dynamically replaced when evaluated. They are enclosed in `%` symbols.

| Token            | Description                         | Example          |
| ---------------- | ----------------------------------- | ---------------- |
| `%artist%`       | Artist name                         | `Phish`          |
| `%date%`         | Full date (YYYY-MM-DD)              | `2025-06-20`     |
| `%venue%`        | Venue of the event                  | `SNHU Arena`     |
| `%city%`         | City + state                        | `Manchester, NH` |
| `%format%`       | First format tag                    | `2160p`          |
| `%formatN%`      | All format tags space-separated     | `2160p WEBRIP`   |
| `%formatN#%`     | Nth format tag (e.g., `%formatN2%`) | `WEBRIP`         |
| `%additional%`   | First additional tag                | `SBD`            |
| `%additionalN%`  | All additional tags space-separated | `SBD AUD DAT`    |
| `%additionalN#%` | Nth additional tag                  | `AUD`            |
| `%year%`         | Year from date                      | `2025`           |
| `%month%`        | Month from date                     | `06`             |
| `%day%`          | Day from date                       | `20`             |

---

### Functions

Functions begin with `$` and use parentheses for arguments. They support nesting.

#### Text

| Function                        | Description         | Example                      | Output       |
| ------------------------------- | ------------------- | ---------------------------- | ------------ |
| `$upper(text)`                  | Uppercase text      | `$upper(%artist%)`           | `PHISH`      |
| `$lower(text)`                  | Lowercase text      | `$lower(%artist%)`           | `phish`      |
| `$title(text)`                  | Title case          | `$title("live show")`        | `Live Show`  |
| `$substr(text,start,end)`       | Substring           | `$substr(%artist%,0,3)`      | `Phi`        |
| `$left(text,n)`                 | Leftmost `n` chars  | `$left(%artist%,3)`          | `Phi`        |
| `$right(text,n)`                | Rightmost `n` chars | `$right(%artist%,3)`         | `ish`        |
| `$replace(text,search,replace)` | Replace text        | `$replace(%city%,", NH","")` | `Manchester` |
| `$len(text)`                    | Text length         | `$len(%artist%)`             | `5`          |
| `$pad(text,n,ch)`               | Pad to length       | `$pad(%artist%,7,"_")`       | `Phish__`    |

#### Math

| Function    | Description | Example      | Output |
| ----------- | ----------- | ------------ | ------ |
| `$add(x,y)` | Addition    | `$add(10,5)` | `15`   |
| `$sub(x,y)` | Subtraction | `$sub(10,2)` | `8`    |
| `$mul(x,y)` | Multiply    | `$mul(4,5)`  | `20`   |
| `$div(x,y)` | Divide      | `$div(10,2)` | `5`    |

#### Logical

| Function    | Description | Example               | Output |
| ----------- | ----------- | --------------------- | ------ |
| `$eq(x,y)`  | Equal       | `$eq(%artist%,Phish)` | `1`    |
| `$gt(x,y)`  | Greater     | `$gt(5,2)`            | `1`    |
| `$lt(x,y)`  | Less than   | `$lt(1,2)`            | `1`    |
| `$and(x,y)` | All true    | `$and(1,1)`           | `1`    |
| `$or(x,y)`  | Any true    | `$or(0,1)`            | `1`    |
| `$not(x)`   | Negate      | `$not(0)`             | `1`    |

#### Date

| Function       | Description | Example          | Output                |
| -------------- | ----------- | ---------------- | --------------------- |
| `$datetime()`  | Now in ISO  | `$datetime()`    | `2025-07-19T14:32:00` |
| `$year(date)`  | Year part   | `$year(%date%)`  | `2025`                |
| `$month(date)` | Month part  | `$month(%date%)` | `06`                  |
| `$day(date)`   | Day part    | `$day(%date%)`   | `20`                  |

#### Conditionals

| Function                   | Description      | Example                           | Output  |
| -------------------------- | ---------------- | --------------------------------- | ------- |
| `$if(cond,true,false)`     | Inline condition | `$if($eq(%artist%,Phish),YES,NO)` | `YES`   |
| `$if2(val1,val2,fallback)` | First non-empty  | `$if2(%non%,%artist%,Unknown)`    | `Phish` |

---

### Live Preview and Customization

* Preview area shows the evaluated result in real-time using sample metadata
* Right-click to copy output
* Modify `SAMPLE_META` in the script for different test data
* All tokens/functions customizable via Python dictionaries/lists

---

## Example Schemes

1. **Basic Scheme:**

```
%artist% - %date% - %venue% - %city% [%format%] [%additional%]
```

**Output:**

```
Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p] [SBD]
```

2. **Date Split:**

```
%artist% - $year(%date%)-%month(%date%)-%day(%date%) - %venue% - %city%
```

**Output:**

```
Phish - 2025-06-20 - SNHU Arena - Manchester, NH
```

3. **Advanced Format Parsing:**

```
%artist% - %date% - %venue% - %city% [%formatN%] [%formatN2%]
```

**Output:**

```
Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p WEBRIP] [WEBRIP]
```

4. **Fallback Example:**

```
%artist% - $if2(%nickname%,%artist%,Unknown)
```

**Output:**

```
Phish - Phish
```

---

## Dependencies

* Python 3.10+
* Tkinter (GUI)
* Mutagen (tag handling)
* Pillow (image support, optional)
* See `requirements.txt` for full list

---

## Contributing

* Open issues for bugs or suggestions
* Fork and submit pull requests
* Improve documentation or add examples

---

## License

Licensed under the MIT License. See LICENSE file for full terms.

---

## Contact

Created and maintained by **DeadThread**.

*End of README*
