// QPTIFF → pyramidal OME-TIFF batch exporter for QuPath
// Uses original QPTIFF filename: c1.qptiff → c1.ome.tiff

import static qupath.lib.gui.scripting.QPEx.*

import qupath.lib.common.GeneralTools
import qupath.lib.gui.dialogs.Dialogs
import qupath.lib.images.writers.ome.OMEPyramidWriter
import qupath.lib.images.writers.ome.OMEPyramidWriterCommand

// --- Check project ---
def project = getProject()
if (project == null) {
    Dialogs.showErrorMessage("QPTIFF → OME-TIFF", "Please open a QuPath project first.")
    return
}

// --- Choose output directory ---
def outDir = Dialogs.promptForDirectory("Choose output folder for OME-TIFFs", null)
if (outDir == null) {
    println "No output directory selected, aborting."
    return
}
println "Output directory: " + outDir.getAbsolutePath()

// --- Use QuPath defaults for OME pyramids ---
int defaultTile = OMEPyramidWriterCommand.getDefaultTileSize()
def defaultCompression = OMEPyramidWriterCommand.getDefaultPyramidCompression()
println "Using tile size = ${defaultTile}, compression = ${defaultCompression}"

// --- Iterate over project images ---
def entries = project.getImageList()
if (entries.isEmpty()) {
    Dialogs.showErrorMessage("QPTIFF → OME-TIFF", "Project has no images.")
    return
}

entries.each { entry ->
    // Get original URI(s)
    def uris = entry.getServerBuilder().getURIs()
    def uri = uris.isEmpty() ? null : uris.get(0)

    // Use lowercase string only for extension check
    def uriStringLower = uri == null ? "" : uri.toString().toLowerCase()
    if (!uriStringLower.endsWith(".qptiff")) {
        println "Skip (not QPTIFF): " + entry.getImageName()
        return
    }

    println "\n=== Converting: ${entry.getImageName()} ==="

    // Derive original filename from URI, e.g. c1.qptiff
    String originalName
    if (uri != null) {
        try {
            originalName = new File(uri).getName()  // c1.qptiff
        } catch (Exception e) {
            // Fallback if something weird happens
            originalName = entry.getImageName()
        }
    } else {
        originalName = entry.getImageName()
    }

    // Remove extension → c1
    def baseName = GeneralTools.getNameWithoutExtension(originalName)
    def outFile = new File(outDir, baseName + ".ome.tiff")  // c1.ome.tiff

    println "Original name: ${originalName}"
    println "Writing pyramidal OME-TIFF → " + outFile.getAbsolutePath()

    // Open image data (lazy loading; pixels are read on demand)
    def imageData = entry.readImageData()
    def server = imageData.getServer()

    // Build pyramidal OME writer
    new OMEPyramidWriter.Builder(server)
        .tileSize(defaultTile)             // use QuPath default tile size
        .compression(defaultCompression)   // use QuPath default compression
        .bigTiff(true)                     // for 10+ GB images
        .dyadicDownsampling()              // 1, 2, 4, 8,... pyramid levels
        .allZSlices()
        .allTimePoints()
        .parallelize()                     // internal tile-level parallelism
        .build()
        .writePyramid(outFile.getAbsolutePath())

    imageData.close()
    println "✓ Done: ${entry.getImageName()}"
}

println "\nAll done."
Dialogs.showInfoNotification("QPTIFF → OME-TIFF", "Finished exporting pyramidal OME-TIFFs.")
