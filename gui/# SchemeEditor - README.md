# SchemeEditor - README

## Overview

`SchemeEditor` is a Python script built with `Tkinter` that allows users to create and test customizable naming schemes for their media files. It provides a user-friendly interface for inserting tokens (placeholders for metadata), functions (for data manipulation), and conditional logic to format filenames based on various metadata fields.

### Main Features:
- **Tokens**: Insert placeholders for artist, date, venue, city, format, and additional metadata.
- **Functions**: Perform various operations on text like changing case, trimming, padding, etc.
- **Preview**: See a live preview of the resulting output as you build the naming scheme.
- **Save Scheme**: Save the current scheme for later use or reference.
- **Reset Default**: Return the editor to a default naming scheme layout.
- **Right-click**: Copy the previewed naming scheme text to the clipboard with a simple right-click.

---

## Components of the SchemeEditor

### 1. **Tokens / Functions List**:

In the left pane, you’ll find a list of available tokens and functions that you can insert into your naming scheme.

#### **Tokens**:
Tokens represent pieces of metadata that will be dynamically replaced when evaluated. They are enclosed in `%` symbols.

- `%artist%`: The artist name (e.g., `Phish`)
- `%date%`: The date (in `YYYY-MM-DD` format, e.g., `2025-06-20`)
- `%venue%`: The venue name (e.g., `SNHU Arena`)
- `%city%`: The city and state (e.g., `Manchester, NH`)
- `%format%`: The first format (e.g., `2160p`)
- `%formatN%`: All formats combined from the comma-separated list (e.g., `2160p WEBRIP`)
- `%formatN#%`: The number specified tag format in the list (e.g., `%formatN2%` → `WEBRIP`)
- `%additional%`: The first additional metadata (e.g., `SBD`)
- `%additionalN%`: All additional metadata combined (e.g., `SBD AUD DAT`)
- `%additionalN#%`: The number specified additional metadata in the list (e.g., `%additionalN2%` → `AUD`)

#### **Functions**:
Functions allow you to manipulate text, math, or date/time.

- `$upper(text)`: Converts text to uppercase.
- `$lower(text)`: Converts text to lowercase.
- `$title(text)`: Converts text to title case.
- `$substr(text,start,end)`: Extracts a substring from the text.
- `$left(text,n)`: Takes the leftmost `n` characters from the text.
- `$right(text,n)`: Takes the rightmost `n` characters from the text.
- `$replace(text,search,replace)`: Replaces a part of the text.
- `$len(text)`: Returns the length of the text.
- `$pad(text,n,ch)`: Pads the text to the right with the given character until it reaches length `n`.

#### **Math Functions**:
- `$add(x,y)`: Adds numbers.
- `$sub(x,y)`: Subtracts numbers.
- `$mul(x,y)`: Multiplies numbers.
- `$div(x,y)`: Divides numbers.

#### **Comparisons and Logic**:
- `$eq(x,y)`: Checks if two values are equal.
- `$lt(x,y)`: Checks if `x` is less than `y`.
- `$gt(x,y)`: Checks if `x` is greater than `y`.
- `$and(x,y,...)`: Returns true if all conditions are true.
- `$or(x,y,...)`: Returns true if any condition is true.
- `$not(x)`: Negates a condition.

#### **Date/Time Functions**:
- `$datetime()`: Returns the current date and time in ISO format.
- `$year(date)`: Extracts the year from a date.
- `$month(date)`: Extracts the month from a date.
- `$day(date)`: Extracts the day from a date.

#### **Conditionals**:
- `$if(condition,true_value,false_value)`: Returns one of two values based on a condition.
- `$if2(value1,value2,...,fallback)`: Returns the first non-empty value from the list or the fallback if all values are empty.

---

### 2. **Scheme Editor**:

The main section of the interface is the text editor where you define your naming scheme. This editor accepts tokens, functions, and regular text.

- You can type any text and include tokens or functions for dynamic data replacement.
- **Live Preview**: As you edit your scheme, the preview area on the right shows you what the final result would look like with the current sample metadata.
- **Reset Default**: You can click the “Reset Default” button to revert the editor to a default naming scheme (e.g., `%artist% - %date% - %venue% - %city% [%format%] [%additional%]`).

---

### 3. **Preview Area**:

As you type or modify the naming scheme in the editor, a live preview is shown in the "Live Preview" section. This section dynamically updates based on the metadata you provide.

- **Sample Metadata**: The preview uses a sample set of metadata (e.g., `artist`, `date`, `venue`, etc.) for rendering the preview. You can modify this sample metadata in the code or use the "get_live_metadata" function to fetch real-time data.
  
- **Context Menu**: You can right-click the preview text and select **Copy** to copy the result to your clipboard.

---

## Customization

You can customize the behavior of `SchemeEditor` by modifying the metadata, tokens, and functions:

1. **Metadata**: Modify the `SAMPLE_META` dictionary at the top of the script to provide new sample metadata for the preview.
2. **Tokens**: The list of tokens (`TOKENS`) is fully customizable. Add or remove tokens to suit your needs.
3. **Functions**: Similarly, you can expand the available functions to include your own logic.

---

## Example Schemes

1. **Phish Naming Scheme**:

%artist% - %date% - %venue% - %city% [%format%] [%additional%]

**Result**: `Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p] [SBD]`

2. **Custom Format with Date Functions**:

%artist% - $year(%date%)-%month(%date%)-%day(%date%) - %venue% - %city%

**Result**: `Phish - 2025-06-20 - SNHU Arena - Manchester, NH`

3. **Format N#**:

%artist% - %date% - %venue% - %city% [%formatN%] [%formatN2%]

**Expected Result**: `Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p WEBRIP] [WEBRIP]`

4. **All Formats Combined**:

%artist% - %date% - %venue% - %city% [%formatN%]

**Result**: `Phish - 2025-06-20 - SNHU Arena - Manchester, NH [2160p WEBRIP]`

---

## Conclusion

The `SchemeEditor` script is a flexible tool for managing and organizing media files with custom naming conventions. You can experiment with tokens, functions, and conditionals to generate complex naming schemes for your files. Whether you're working with music, videos, or any other form of media, this tool offers a robust solution for automating file renaming and metadata embedding.
