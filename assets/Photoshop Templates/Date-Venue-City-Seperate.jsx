#target photoshop

function main() {
    var templateFile = File.openDialog("Select your PSD template");
    var rootFolder = Folder.selectDialog("Select root folder containing subfolders");
    if (!templateFile || !rootFolder) {
        alert("Cancelled by user.");
        return;
    }

    var subfolders = rootFolder.getFiles(function(f) {
        return f instanceof Folder;
    });

    if (subfolders.length === 0) {
        alert("No subfolders found in the selected root folder.");
        return;
    }

    for (var i = 0; i < subfolders.length; i++) {
        var folder = subfolders[i];

        // Decode folder name safely
        var folderName = decodeFolderName(folder.name);
        $.writeln("Raw folder name: " + folder.name);
        $.writeln("Decoded folder name: " + folderName);

        var parts = folderName.split(" - ");
        if (parts.length < 4) {
            alert("Skipping folder with invalid name format:\n" + folderName);
            continue;
        }

        var date = safeTrim(parts[1]);
        var venue = safeTrim(parts[2]);
        var cityRaw = parts.slice(3).join(" - ");
        var bracketIndex = cityRaw.search(/[\[\(]/);
        var city = bracketIndex !== -1 ? cityRaw.substring(0, bracketIndex) : cityRaw;
        city = safeTrim(city);

        var doc;
        try {
            doc = app.open(templateFile);

            // Log all text layers for debug
            var allTextLayers = findTextLayers(doc);
            $.writeln("Text layers in template:");
            for (var t = 0; t < allTextLayers.length; t++) {
                $.writeln(" - " + allTextLayers[t].name);
            }

            // Update text layers
            setTextAndPreservePosition(doc, "Date", date);
            setTextAndPreservePosition(doc, "Venue", venue);
            setTextAndPreservePosition(doc, "City", city);

            // Export image as Poster.jpg inside the folder
            var jpgFile = new File(folder.fsName + "/Poster.jpg");
            var jpgOptions = new ExportOptionsSaveForWeb();
            jpgOptions.format = SaveDocumentType.JPEG;
            jpgOptions.includeProfile = false;
            jpgOptions.interlaced = false;
            jpgOptions.optimized = true;
            jpgOptions.quality = 90;
            doc.exportDocument(jpgFile, ExportType.SAVEFORWEB, jpgOptions);

            // Save PSD as Poster.psd inside the folder
            var psdFile = new File(folder.fsName + "/Poster.psd");
            var psdSaveOptions = new PhotoshopSaveOptions();
            psdSaveOptions.layers = true; // preserve layers
            doc.saveAs(psdFile, psdSaveOptions, true); // true = asCopy

        } catch (e) {
            alert("⚠️ Error processing folder '" + folderName + "':\n" + e.message);
        } finally {
            if (doc) doc.close(SaveOptions.DONOTSAVECHANGES);
        }
    }

    alert("✅ Poster.jpg and Poster.psd generated in each subfolder.");
}

// Helper: safely decode folder name or fallback
function decodeFolderName(name) {
    try {
        return decodeURIComponent(name);
    } catch (e) {
        return name;
    }
}

// Trim whitespace manually
function safeTrim(value) {
    return ("" + value).replace(/^\s+|\s+$/g, "");
}

// Recursive search for all text layers (inside groups)
function findTextLayers(parent) {
    var layers = [];
    for (var i = 0; i < parent.layers.length; i++) {
        var layer = parent.layers[i];
        if (layer.typename === "ArtLayer" && layer.kind === LayerKind.TEXT) {
            layers.push(layer);
        } else if (layer.typename === "LayerSet") {
            layers = layers.concat(findTextLayers(layer));
        }
    }
    return layers;
}

// Recursive find text layer by name
function getTextLayerByName(parent, name) {
    for (var i = 0; i < parent.layers.length; i++) {
        var layer = parent.layers[i];
        if (layer.typename === "ArtLayer" && layer.kind === LayerKind.TEXT && layer.name === name) {
            return layer;
        } else if (layer.typename === "LayerSet") {
            var found = getTextLayerByName(layer, name);
            if (found) return found;
        }
    }
    return null;
}

// Set text content on the layer preserving position and justification
function setTextAndPreservePosition(doc, layerName, newText) {
    try {
        var layer = getTextLayerByName(doc, layerName);
        if (!layer) throw new Error("Layer not found");

        var pos = [layer.textItem.position[0], layer.textItem.position[1]];
        var justification = layer.textItem.justification;

        layer.textItem.justification = Justification.LEFT;
        layer.textItem.contents = newText;
        layer.textItem.position = pos;
        layer.textItem.justification = justification;

        $.writeln("✓ Updated '" + layerName + "' with: " + newText);
    } catch (e) {
        $.writeln("❌ Could not update layer: " + layerName + " — " + e.message);
        alert("Missing or misnamed layer: " + layerName);
    }
}

main();
