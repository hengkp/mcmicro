import mcmicro.*

process palom_align {
    container "${params.contPfx}${module.container}:${module.version}"
    publishDir "${params.in}/registration", mode: 'copy', pattern: '*.ome.tif'
    
    // Provenance
    publishDir "${Flow.QC(params.in, 'provenance')}", mode: 'copy',
      pattern: '.command.{sh,log}',
      saveAs: {fn -> fn.replace('.command', "${module.name}")}
    
    input:
      val mcp
      val module
      val sampleName
      path lraw       // Only for staging
      val lrelPath    // Use this for paths
      path lffp
      path ldfp

    output:
      path "*.ome.tif", emit: img
      tuple path('.command.sh'), path('.command.log')
      path "versions.yml", emit: versions

    when: Flow.doirun('registration', mcp.workflow)
    
    script:
    def imgs = lrelPath.collect{ Util.escapeForShell(it) }.join(" ")
    def opts = Opts.moduleOpts(module, mcp)
    def outputName = Util.escapeForShell("${sampleName}.ome.tif")
    """
    # Create working directories
    mkdir -p ome_cycles registration
    
    # Run PALOM registration
    python /usr/local/bin/register_akoya_palom.py \\
      --input-dir . \\
      --pattern "*.{ome.tiff,ome.tif}" \\
      --output ${outputName} \\
      ${opts}
    
    # Record versions
    cat <<-END_VERSIONS > versions.yml
    "${module.name}":
        palom: \$(python -c 'import palom; print(palom.__version__)')
        python: \$(python --version | sed 's/Python //g')
    END_VERSIONS
    """
}

process ashlar {
    container "${params.contPfx}${module.container}:${module.version}"
    publishDir "${params.in}/registration", mode: 'copy', pattern: '*.tif'
    
    // Provenance
    publishDir "${Flow.QC(params.in, 'provenance')}", mode: 'copy', 
      pattern: '.command.{sh,log}',
      saveAs: {fn -> fn.replace('.command', "${module.name}")}
    
    input:
      val mcp
      val module
      val sampleName
      path lraw       // Only for staging
      val lrelPath    // Use this for paths
      path lffp
      path ldfp

    output:
      path "*.ome.tif", emit: img
      tuple path('.command.sh'), path('.command.log')

    when: Flow.doirun('registration', mcp.workflow)
    
    script:
    def imgs = lrelPath.collect{ Util.escapeForShell(it) }.join(" ")
    def ilp = "--ffp $lffp --dfp $ldfp"
    if (ilp == '--ffp  --dfp ') ilp = ''  // Don't supply empty --ffp --dfp
    """
    ashlar $imgs ${Opts.moduleOpts(module, mcp)} $ilp -o ${sampleName}.ome.tif
    """
}

workflow registration {
    take:
      mcp     // MCMICRO parameters as read by Opts.parseParams()
      raw     // raw image tiles
      ffp     // flat-field profiles
      dfp     // dark-field profiles

    main:
      rawst = raw.toSortedList{a, b -> a[0] <=> b[0]}.transpose()
      sampleName  = file(params.in).name

      // Determine which registration engine to use
      def engine = mcp.workflow['registration-engine'] ?: 'ashlar'
      
      // Validate engine parameter
      if (!(engine in ['ashlar', 'palom'])) {
        error "Unknown registration engine: ${engine}. Valid options: ashlar, palom"
      }
      
      // Execute the selected registration engine
      if (engine == 'palom') {
        // Use PALOM module specification
        palom_align(
          mcp,
          mcp.modules['registration-palom'],
          sampleName,
          rawst.first(),
          rawst.last(),
          ffp.toSortedList{a, b -> a.getName() <=> b.getName()},
          dfp.toSortedList{a, b -> a.getName() <=> b.getName()}
        )
        registered = palom_align.out.img
      } else {
        // Use ASHLAR (default)
        ashlar(
          mcp,
          mcp.modules['registration'],
          sampleName,
          rawst.first(),
          rawst.last(),
          ffp.toSortedList{a, b -> a.getName() <=> b.getName()},
          dfp.toSortedList{a, b -> a.getName() <=> b.getName()}
        )
        registered = ashlar.out.img
      }

    emit:
      registered
}
