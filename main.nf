#!/usr/bin/env nextflow

if( !(nextflow.version >= '22.04.3') ) {
    println "mcmicro requires Nextflow version 22.04.3 or greater"
    println "Run the following command to update: nextflow self-update"
    exit 1
}

nextflow.enable.dsl=2

import mcmicro.*

import org.yaml.snakeyaml.Yaml
import org.yaml.snakeyaml.DumperOptions

// Expecting --in parameter
if( !params.containsKey('in') )
    error "Please specify the project directory with --in"

// Parse MCMICRO parameters (mcp)
mcp = Opts.parseParams(
    params, 
    "$projectDir/config/schema.yml",
    "$projectDir/config/defaults.yml"
)

// Separate out workflow parameters (wfp) and module specs to simplify code
wfp = mcp.workflow

// Identify relevant precomputed intermediates
// The actual paths to intermediate files are given by
//   pre.collect{ "${params.in}/$it" }
pre = Flow.precomputed(wfp)

// Check that deprecated locations are empty
Channel.fromPath( "${params.in}/illumination_profiles/*" )
    .subscribe{ it ->
    error "illumination_profiles/ is deprecated; please use illumination/ instead"
}

// Identify marker information
chMrk = Channel.fromPath( "${params.in}/markers.csv", checkIfExists: true )

// Helper functions for finding raw images and precomputed intermediates
findFiles0 = { key, pattern -> pre[key] ?
    Channel.fromPath("${params.in}/$key/$pattern") : Channel.empty()
}
findFiles = { key, pattern, ife -> pre[key] ?
    Channel.fromPath("${params.in}/$key/$pattern").ifEmpty(ife) : Channel.empty()
}

// Some image formats store multiple fields of view in a single file. Other
// formats store each field separately, typically in .tif files, with a separate
// index file to tie them together. We will look for the index files from
// multiple-file formats in a first, separate pass in order to avoid finding the
// individual .tif files instead. If no multi-file formats are detected, then we
// look for the single-file formats. Also, for multi-file formats we need to
// stage the parent directory and not just the index file.
(formatType, formatPattern) =
    file("${params.in}/raw/**${wfp['multi-formats']}") ?
    ["multi", wfp['multi-formats']] : ["single", wfp['single-formats']]

// PALOM only accepts OME-TIFF; use ASHLAR for other discovered raw formats.
if(Flow.doirun('registration', wfp) && wfp['registration-engine'] == 'palom') {
    def matches = file("${params.in}/raw/**${formatPattern}")
    def rawPaths = matches instanceof List ? matches : (matches ? [matches] : [])
    def nonOmeNames = rawPaths.collect{ it.name.toLowerCase(Locale.ROOT) }.findAll{
        !(it.endsWith('.ome.tif') || it.endsWith('.ome.tiff'))
    }
    if(rawPaths && (formatType == 'multi' || nonOmeNames)) {
        def extensions = nonOmeNames.collect{ name ->
            def dot = name.lastIndexOf('.')
            dot >= 0 ? name.substring(dot) : '(no extension)'
        }.unique().sort().join(', ')
        def reason = nonOmeNames ? "raw/ holds ${extensions} files" :
            'raw/ uses a multi-file format'
        wfp['registration-engine'] = 'ashlar'
        log.warn "palom reads OME-TIFF only; ${reason}, so registration uses ashlar instead. Set registration-engine: ashlar to silence this."
    }
}

// Split CSV at commas outside quotes, preserving empty and trailing cells.
def csvFields = { line ->
    line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/, -1).collect{
        it.trim().replaceAll(/^"|"$/, '').replace('""', '"').trim()
    }
}
if(wfp.background && Flow.doirun('background', wfp)) {
    def markersFile = file("${params.in}/markers.csv")
    if(markersFile.exists()) {
        def rows = markersFile.readLines()
        def header = rows ? csvFields(rows[0]) : []
        def backgroundColumn = header.indexOf('background')
        if(backgroundColumn < 0) {
            wfp.background = false
            log.warn "markers.csv has no 'background' column, so background subtraction is skipped. Add 'background' (the channel to subtract) and 'exposure' columns to run it."
        }
        else if(!header.contains('exposure') && rows.drop(1).any{ row ->
            def fields = csvFields(row)
            fields.size() > backgroundColumn && fields[backgroundColumn] != ''
        }) {
            wfp.background = false
            log.warn "markers.csv has non-empty 'background' values but no 'exposure' column, so background subtraction is skipped. Add 'exposure' (the exposure time for each channel) to run it."
        }
    }
}

rawFiles = findFiles('raw', "**${formatPattern}",
		     {error "No images found in ${params.in}/raw"})

// Here we assemble tuples of 1) path to stage for each raw image (might be a
// directory) and 2) relative path to the main file for each image. Processes
// must input the first as a path and the second as a val to avoid incorrect or
// redundant file staging. They must also only use the second (relative) path to
// construct pathnames for scripts etc. mcmicro.Util.escapePathForShell must be
// used when interpolating these paths into script strings, as we are bypassing
// the normal way that paths are passed to channels which handles this escaping
// automatically.
raw = rawFiles
    .map{ tuple(formatType == "single" ? it : it.parent, it) }
    .map{ toStage, relPath -> tuple(toStage, toStage.parent.relativize(relPath).toString()) }

// Find precomputed intermediates
pre_dfp   = findFiles0('illumination', "*-dfp.tif")
pre_ffp   = findFiles0('illumination', "*-ffp.tif")
pre_img   = findFiles('registration', "*.{ome.tiff,ome.tif,tif,tiff,btf}",
    {error "No pre-stitched image in ${params.in}/registration"})
pre_bsub  = findFiles('background', "*.ome.tif",
    {error "No background subtracted image in ${params.in}/background"})
pre_bsubm = findFiles('background', "*.csv",
    {error "No background subtracted markers file in ${params.in}/background"})
pre_cores = findFiles('dearray', "*.tif",
    {error "No TMA cores in ${params.in}/dearray"})
pre_masks = findFiles('dearray', "masks/*.tif",
    {error "No TMA masks in ${params.in}/dearray/masks"})
pre_pmap  = findFiles('probability-maps', "*/*-pmap.tif",
    {error "No probability maps found in ${params.in}/probability-maps"})
    .map{ f -> tuple(f.getParent().getName(), f) }
    .filter{ wfp['segmentation'].contains(it[0]) }
pre_seg   = findFiles('segmentation', "**.tif",
    {error "No segmentation masks in ${params.in}/segmentation"})
    .map{ f -> tuple(f.getParent().getName(), f) }.groupTuple()
pre_qty   = findFiles('quantification', "*.csv",
    {error "No quantification tables in ${params.in}/quantification"})

// Import individual modules
include {illumination}   from "$projectDir/modules/illumination"
include {registration}   from "$projectDir/modules/registration"
include {dearray}        from "$projectDir/modules/dearray"
include {segmentation}   from "$projectDir/modules/segmentation"
include {quantification} from "$projectDir/modules/quantification"
include {downstream}     from "$projectDir/modules/downstream"
include {viz}            from "$projectDir/modules/viz"
include {background}     from "$projectDir/modules/background"

// Define the primary mcmicro workflow
workflow {
    illumination(wfp, mcp.modules['illumination'], raw)
    registration(mcp, raw,
		 illumination.out.ffp.mix( pre_ffp ),
		 illumination.out.dfp.mix( pre_dfp ))
    img = registration.out.mix(pre_img)

    // Should background subtraction be applied?
    img = img.
        branch{
            nobs: !wfp.background
            bs: wfp.background
        }
    chMrk = chMrk.
        branch{
            nobs: !wfp.background
            bs: wfp.background
        }
    // Apply background if specified
    background(mcp, img.bs, chMrk.bs)
    // Merge against precomputed intermediates
    bsub_image = background.out.image.mix(pre_bsub)
    bsub_marker = background.out.marker.mix(pre_bsubm)
    // Reconcile non-background subtracted and background 
    // subtracted images for downstream processing
    img = img.nobs.mix(bsub_image)
    // Reconcile the marker file to the background subtracted csv
    chMrk = chMrk.nobs.mix(bsub_marker)

    // Are we working with a TMA or a whole-slide image?
    img = img
        .branch {
            wsi: !wfp.tma
            tma: wfp.tma
        }

    // Apply dearray to TMAs only
    dearray(mcp, img.tma)

    // Merge against precomputed intermediates
    tmacores = dearray.out.cores.mix(pre_cores)
    tmamasks = dearray.out.masks.mix(pre_masks)

    // Reconcile WSI and TMA processing for downstream segmentation
    allimg = img.wsi.mix(tmacores)
    segmentation(mcp, allimg, tmamasks, pre_pmap)

    // Merge segmentation masks against precomputed ones and append markers.csv
    segMsk = segmentation.out.mix(pre_seg)
    quantification(mcp, allimg, segMsk, chMrk)

    // Spatial feature tables -> cell state calling
    sft = quantification.out.mix(pre_qty)
    downstream(mcp, sft)

    // Vizualization
    viz(mcp, allimg, chMrk)
}

// Write out parameters used
path_qc = "${params.in}/qc"
workflow.onComplete {
    // Create a provenance directory
    file(path_qc).mkdirs()
    
    // Write out MCMICRO parameters
    DumperOptions style = new DumperOptions();
    style.setPrettyFlow(true);
    style.setDefaultFlowStyle(DumperOptions.FlowStyle.BLOCK);
    file("${params.in}/qc/params.yml").withWriter{ out -> 
        new Yaml(style).dump(mcp, out) 
    }

    // Store additional metadata
    file("${path_qc}/metadata.yml").withWriter{ out ->
        out.println "githubTag: $workflow.revision";
        out.println "githubCommit: $workflow.commitId";
        out.println "roadie: $params.roadie";
    }
}
