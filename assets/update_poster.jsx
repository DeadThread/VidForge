// update_poster.jsx
#target photoshop

// Arguments passed via $.localFile.read() are not easy, so this script
// expects these variables set before execution (passed as arguments from Python):
// app.open(templatePath);
// then call updateLayers(city, venue, date, saveFolder)

function updateLayers(city, venue, date, saveFolder) {
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

    function setText(layer, text) {
        if (!layer) return;
        layer.textItem.contents = text;
    }

    try {
        var doc = app.activeDocument;

        setText(getTextLayerByName(doc, "City"), city);
        setText(getTextLayerByName(doc, "Venue"), venue);
        setText(getTextLayerByName(doc, "Date"), date);

        // Save PSD as Poster.psd in saveFolder
        var psdFile = new File(saveFolder + "/Poster.psd");
        var psdSaveOptions = new PhotoshopSaveOptions();
        psdSaveOptions.layers = true;
        doc.saveAs(psdFile, psdSaveOptions, true);

        // Export JPG as Poster.jpg
        var jpgFile = new File(saveFolder + "/Poster.jpg");
        var jpgOptions = new ExportOptionsSaveForWeb();
        jpgOptions.format = SaveDocumentType.JPEG;
        jpgOptions.includeProfile = false;
        jpgOptions.interlaced = false;
        jpgOptions.optimized = true;
        jpgOptions.quality = 90;
        doc.exportDocument(jpgFile, ExportType.SAVEFORWEB, jpgOptions);

        alert("Poster.psd and Poster.jpg saved successfully!");

    } catch(e) {
        alert("Error in updateLayers: " + e.message);
    }
}

updateLayers(cityArg, venueArg, dateArg, saveFolderArg);
