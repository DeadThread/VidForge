# SchemeEditor - Detailed README

## Overview

`SchemeEditor` is a powerful tool for defining **custom folder and filename naming schemes** for your media files (like videos). It uses **tokens** (placeholders for metadata) and **functions** (to manipulate or conditionally format that metadata) to give you complete flexibility over how your files and folders are named.

The tool supports nested function calls, conditional logic, math operations, and more, allowing for very sophisticated naming schemes.

---

## Tokens

Tokens are placeholders wrapped in `%` signs that get replaced by metadata values when your scheme is evaluated.

| Token        | Description                                  | Example Value                      |
|--------------|----------------------------------------------|----------------------------------|
| `%artist%`   | Artist or performer name                      | `Phish`                          |
| `%date%`     | Date of the recording or event (YYYY-MM-DD) | `2025-06-20`                     |
| `%venue%`    | Venue name                                   | `SNHU Arena`                     |
| `%city%`     | City and state                               | `Manchester, NH`                 |
| `%format%`   | The first format tag                         | `2160p`                         |
| `%formatN%`  | All format tags combined (space-separated)  | `2160p WEBRIP`                   |
| `%formatN#%` | The Nth format tag (e.g., `%formatN2%`)     | `WEBRIP`                        |
| `%additional%`| The first additional tag                     | `SBD`                          |
| `%additionalN%`| All additional tags combined (space-separated)| `SBD AUD DAT`                  |
| `%additionalN#%`| The Nth additional tag (e.g., `%additionalN2%`)| `AUD`                       |
| `%year%`     | Extracted year from `%date%`                  | `2025`                         |
| `%month%`    | Extracted month from `%date%`                 | `06`                           |
| `%day%`      | Extracted day from `%date%`                   | `20`                           |

---

## Functions

Functions are wrapped in `$` and parentheses and allow you to manipulate text, perform math, apply logic, or control formatting.

### Text Functions

| Function                  | Description                                           | Example                                   | Output             |
|---------------------------|-------------------------------------------------------|-------------------------------------------|--------------------|
| `$upper(text)`            | Converts text to uppercase                            | `$upper(%artist%)`                        | `PHISH`            |
| `$lower(text)`            | Converts text to lowercase                            | `$lower(%artist%)`                        | `phish`            |
| `$title(text)`            | Converts text to title case                           | `$title("phish concert")`                 | `Phish Concert`    |
| `$substr(text,start,end)` | Extracts a substring from `start` (0-based) to `end` | `$substr(%artist%,0,3)`                    | `Phi`              |
| `$left(text,n)`           | Leftmost `n` characters of text                       | `$left(%artist%,3)`                       | `Phi`              |
| `$right(text,n)`          | Rightmost `n` characters of text                      | `$right(%artist%,3)`                      | `ish`              |
| `$replace(text,search,replace)` | Replaces occurrences of `search` with `replace`| `$replace(%city%,", NH","")`               | `Manchester`       |
| `$len(text)`              | Length of the text                                    | `$len(%artist%)`                          | `5`                |
| `$pad(text,n,ch)`         | Pads text to length `n` with character `ch` (default space) | `$pad(%artist%,7,"_")`               | `Phish__`          |

### Math Functions

| Function          | Description               | Example               | Output   |
|-------------------|---------------------------|-----------------------|----------|
| `$add(x,y)`       | Adds numbers              | `$add(10,20)`         | `30`     |
| `$sub(x,y)`       | Subtracts numbers         | `$sub(10,5)`          | `5`      |
| `$mul(x,y)`       | Multiplies numbers        | `$mul(4,5)`           | `20`     |
| `$div(x,y)`       | Divides numbers (no div by zero) | `$div(10,2)`   | `5`      |

### Logical and Comparison Functions

| Function             | Description                           | Example                            | Output |
|----------------------|-------------------------------------|----------------------------------|--------|
| `$eq(x,y)`           | Returns `1` if `x == y`, else `0`   | `$eq(%artist%,Phish)`             | `1`    |
| `$lt(x,y)`           | Returns `1` if `x < y`, else `0`    | `$lt(2,3)`                       | `1`    |
| `$gt(x,y)`           | Returns `1` if `x > y`, else `0`    | `$gt(3,2)`                       | `1`    |
| `$and(x,y,...)`      | Returns `1` if all arguments are true/non-empty | `$and($gt(5,3),$lt(1,2))`| `1`    |
| `$or(x,y,...)`       | Returns `1` if any argument is true/non-empty   | `$or(0,1,0)`                 | `1`    |
| `$not(x)`            | Returns `1` if `x` is false/empty, else `0`    | `$not(0)`                    | `1`    |

### Date and Time Functions

| Function         | Description                           | Example               | Output                     |
|------------------|-------------------------------------|-----------------------|----------------------------|
| `$datetime()`    | Returns current date/time in ISO format | `$datetime()`       | `2025-06-30T20:24:54`     |
| `$year(date)`    | Extracts year from a date string     | `$year(%date%)`       | `2025`                     |
| `$month(date)`   | Extracts month from a date string    | `$month(%date%)`      | `06`                       |
| `$day(date)`     | Extracts day from a date string      | `$day(%date%)`        | `20`                       |

### Conditional Functions

| Function                             | Description                                                | Example                                         | Output            |
|------------------------------------|------------------------------------------------------------|-------------------------------------------------|-------------------|
| `$if(condition,true_val,false_val)`| Returns `true_val` if `condition` is true (non-empty/non-zero), else `false_val` | `$if($eq(%artist%,Phish),YES,NO)`      | `YES`             |
| `$if2(value1,value2,...,fallback)`  | Returns first non-empty value, or fallback if all empty    | `$if2(%nonexistent%,%artist%,fallback)`          | `Phish`           |

---

## Examples

### Example 1: Basic Folder and Filename

**Folder Scheme:**

%artist%/%year%


**Filename Scheme:**

%artist% - %date% - %venue% - %city% [%formatN%] [%additionalN%]


**Live Preview:**

(Root Folder)/Phish/2025/Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p WEBRIP] [SBD AUD DAT]


---

### Example 2: Using Functions and Conditionals

**Filename Scheme:**

$upper(%artist%) - $year(%date%) - $replace(%venue%, "Arena", "Hall") - $if($eq(%city%,Manchester, NH), "NH", %city%)


**Preview:**

PHISH - 2025 - SNHU Hall - NH


---

### Example 3: Complex Logic

**Filename Scheme:**

%artist% - %date% - $if($gt($len(%venue%),10), $substr(%venue%,0,10), %venue%) - %city%


**Preview:**

Phish - 2025-06-20 - SNHU Arena - Manchester, NH


---

## Usage Tips

- Double-click tokens or functions in the left pane to insert them into the folder or filename scheme editors.
- Use the **Reset** button to restore default schemes.
- The **Save** button currently shows your scheme but can be extended to save it to disk or send to your main app.
- Use the **Help** button for a quick guide.
- The **Live Preview** updates automatically as you type.
- Right-click on the live preview text to copy it to your clipboard.

---

## Notes

- All function arguments are strings; numeric operations will attempt to convert strings to numbers.
- Functions and tokens can be nested for advanced formatting.
- Date tokens (`%year%`, `%month%`, `%day%`) are parsed from `%date%` metadata.
- The `$if2` function is useful for fallback logic when multiple metadata fields may be empty.

---

## Conclusion

This SchemeEditor lets you create **flexible, dynamic naming schemes** using tokens and functions for your media files — perfect for organizing large video or audio collections with rich metadata.

Experiment with the tokens and functions to tailor your file naming exactly how you want it!

---

*End of README*