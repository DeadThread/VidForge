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
        var folderName = decodeURIComponent(folder.name);

        var parts = folderName.split(" - ");
        if (parts.length < 4) {
            alert("Skipping folder with invalid name format:\n" + folderName);
            continue;
        }

        var date = parts[1];
        var venue = parts[2];

        var cityRaw = parts.slice(3).join(" - ");
        if (typeof cityRaw !== "string") cityRaw = "";

        var bracketIndex = cityRaw.search(/[\[\(]/);
        var city;
        if (bracketIndex !== -1) {
            city = cityRaw.substring(0, bracketIndex);
        } else {
            city = cityRaw;
        }
        city = city.trim ? city.trim() : city;

        var finalText = date + "\r" + venue + "\r" + city;

        var doc = app.open(templateFile);

        try {
            var layer = doc.artLayers.getByName("Date / Venue / City");
            layer.textItem.contents = finalText;
        } catch (e) {
            alert("Error: Could not find or edit 'Date / Venue / City' text layer in template.");
            doc.close(SaveOptions.DONOTSAVECHANGES);
            continue;
        }

        // ✅ Always export as Poster.jpg
        var outputFile = new File(folder.fsName + "/Poster.jpg");

        var options = new ExportOptionsSaveForWeb();
        options.format = SaveDocumentType.JPEG;
        options.includeProfile = false;
        options.interlaced = false;
        options.optimized = true;
        options.quality = 90;

        doc.exportDocument(outputFile, ExportType.SAVEFORWEB, options);
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }

    alert("Poster.jpg generated in each subfolder.");
}

main();
