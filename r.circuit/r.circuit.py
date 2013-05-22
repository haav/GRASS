#!/usr/bin/env python
############################################################################
#
# MODULE:       r.circuit
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      An interface to an external landscape connectivty analysis
#               software Circuitscape (http://www.circuitscape.org/)
#               by Brad McRae and Viral Shah.
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Circuitscape interface to GRASS
#% keywords: circuitscape
#% keywords: cost
#% keywords: raster
#%end

#%option
#% key: cost
#% type: string
#% gisprompt: old,raster
#% description: Input friction surface 
#% required: yes
#%end

#%option
#% key: costtype
#% type: string
#% answer: Resistance
#% options: Resistance, Conductance
#% description: Friction surface type
#% required:yes
#%end

#%option
#% key: features
#% type: string
#% gisprompt: old,vector
#% description: Input vector feature layer
#% required: yes
#%end

#%option
#% key: scenario
#% type: string
#% answer: pairwise
#% options: pairwise, one-to-all, all-to-one
#% description: Modelling mode
#% required: yes
#%end

#%option
#% key: prefix
#% type: string
#% answer: cs
#% description: Output layer name prefix (e.g. "cs" will result in "cs_cumulative")
#% required:yes
#%end

#%option
#% key: maptype
#% type: string
#% answer: Current
#% options: Current, Voltage, Both
#% description: Output map type
#% required: no
#%end

#%option
#% key: connecttype
#% type: string
#% answer: Average resistance
#% options: Average resistance, Average conductance
#% description: Connect type
#% required: no
#%end

#%flag
#% key: m
#% description: Low memory mode for pairwise mode (requires less memory, but takes longer)
#%end

#%flag
#% key: l
#% description: Current maps logarithmic transformation
#%end

#%flag
#% key: c
#% description: Write cumulative current map only
#%end

#%flag
#% key: r
#% description: Use rook's move (4 neighbours only, instead of 8)
#%end

#%flag
#% key: x
#% description: Also write maximum current map
#%end

#%flag
#% key: n
#% description: Do not treat Null current/voltage as NoData
#%end

#%flag
#% key: p
#% description: Vector layer contains polygons
#%end

#%flag
#% key: o
#% description: Allow output files to overwrite existing files
#%end

import subprocess
import atexit, sys, os
import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis


def main():
    # Some preliminaries: get working environment settings
    env = grass.gisenv()
    gisdbase = env['GISDBASE']
    location = env['LOCATION_NAME']
    mapset = env['MAPSET']
    path = os.path.join(gisdbase, location, mapset)
    tmppath = path + "\\.tmp\\" # This is a temporary folder where tempfiles will be stored
    
    # Get the cs_run.exe path from circuitscape.ini
    cfgpath = sys.path[0] + "\\circuitscape.ini"
    cfg = open(cfgpath, "r")
    CS_Path = cfg.read()
    cfg.close()
    
    # User inputs
    cost = options['cost']          # Input friction surface
    costtype = options['costtype']  # Input friction surface type: resistance or conductance
    if costtype == "Resistance":
        costtype = "True"
    elif costtype == "Conductance":
        costtype = "False"
    connecttype = options['connecttype']  # Cell connect type: average resistance or conductance
    if connecttype == "Average resistance":
        connecttype = "True"
    elif connecttype == "Average conductance":
        connecttype = "False"
    features = options['features']      # Input vector layer
    scenario = options['scenario']      # Modelling mode
    maptype = options['maptype']        # Calculated map type: current, voltage or both
    if maptype == "Current":
        currentmap = "True"
        voltagemap = "False"
    elif maptype == "Voltage":
        voltagemap = "True"
        currentmap = "False"
    elif maptype == "Both":
        voltagemap = "True"
        currentmap = "True"
    poly = True if flags["p"] else False    # Vector layer contains polygons
    overw = True if flags["o"] else False   # Overwrite output layers if needed
    # The pair inclusion/exclusion matrix is not actually implemented here as the feature does not seem to work with Circuitscape version 3.5.8. The option is nevertheless retained here for future developments.
    # pairfile = "None" if not options['pairfile'] else options['pairfile']
    pairfile = "None"

    # Some temporary layers
    tmp_featraster = "tmp_circuitscape_featraster"     # Temporary layer name for rasterised vector layer
    cost_ascii = tmppath + "cost.asc"                  # Cost surface ascii file path and name
    feats_ascii = tmppath + "feats.asc"                # Rasterised ascii vector layer file path and name

    # Output settings
    output_prefix = options['prefix']                           # The prefix will be added to the output files
    cs_output = tmppath + output_prefix + ".out"                # The general output file path and name template
    cs_output_cum = tmppath + output_prefix + "_cum_curmap.asc" # The cumulative current map path and name

    # Get the number of features and the list of possible pairs
    featlist, pairlist = featpairs(features)
    n_feats = len(featlist)
    
    # Convert the input features and cost raster into ASCII raster
    grass.run_command('r.out.arc', overwrite=True, input=cost, output=cost_ascii)
    if poly:
        grass.run_command('v.to.rast', overwrite=True, input=features, type="area", output=tmp_featraster, use="cat")
    else:
        grass.run_command('v.to.rast', overwrite=True, input=features, type="point", output=tmp_featraster, use="cat")
    grass.run_command('r.out.arc', overwrite=True, input=tmp_featraster, output=feats_ascii)
    
    
    """ Circuitscape-specific settings """
    
    # Options for advanced mode (not implemented yet, perhaps in the future?)
    ground_file_is_resistances = "True"
    source_file = "(Browse for a current source file)"
    remove_src_or_gnd = "keepall"
    ground_file = "(Browse for a ground point file)"
    use_unit_currents = "False"
    use_direct_grounds = "False"
    
    # Calculation options
    low_memory_mode = "True" if flags["m"] else "False"
    solver = "cg+amg"   # No idea what this does
    print_timings = "True"
    
    # Options for pairwise and one-to-all and all-to-one modes
    included_pairs_file = pairfile
    point_file_contains_polygons = str(poly)
    use_included_pairs = "False" if pairfile == "None" else "True"
    point_file = feats_ascii

    # Output options
    write_cum_cur_map_only = "True" if flags["c"] else "False"
    log_transform_maps = "True" if flags["l"] else "False"
    set_focal_node_currents_to_zero = "False"
    output_file = cs_output
    write_max_cur_maps = "True" if flags["x"] else "False"
    write_volt_maps = voltagemap
    set_null_currents_to_nodata = "False" if flags["n"] else "True"
    set_null_voltages_to_nodata = "False" if flags["n"] else "True"
    compress_grids = "False"
    write_cur_maps = currentmap

    # Short circuit regions (aka polygons)
    use_polygons = "False"
    polygon_file = "(Browse for a short-circuit region file)"

    # Connection scheme for raster habitat data
    connect_four_neighbors_only = "True" if flags["r"] else "False"
    connect_using_avg_resistances = connecttype

    # Habitat raster or graph
    habitat_file = cost_ascii
    habitat_map_is_resistances = costtype

    # Options for one-to-all and all-to-one modes
    use_variable_source_strengths = "False"
    variable_source_file = "None"

    # Version
    version = "3.5.8"   # That should ideally be obtained from reading cs_run.exe

    # Mask file
    use_mask = "False"
    mask_file = "None"

    # Circuitscape mode
    data_type = "raster"
    scenario = scenario

    # The following long string is a properly formatted .ini file for Circuitscape
    inistring = ("[Options for advanced mode]\n" +
                "ground_file_is_resistances = " + ground_file_is_resistances + "\n" +
                "source_file = " + source_file + "\n" +
                "remove_src_or_gnd = " + remove_src_or_gnd + "\n" +
                "ground_file = " + ground_file + "\n" +
                "use_unit_currents = " + use_unit_currents + "\n" +
                "use_direct_grounds = " + use_direct_grounds + "\n" +
                "\n" +
                "[Calculation options]\n" +
                "low_memory_mode = " + low_memory_mode + "\n" +
                "solver = " + solver + "\n" +
                "print_timings = " + print_timings + "\n" +
                "\n" +
                "[Options for pairwise and one-to-all and all-to-one modes]" + "\n" +
                "included_pairs_file = " + included_pairs_file + "\n" +
                "point_file_contains_polygons = " + point_file_contains_polygons + "\n" +
                "use_included_pairs = " + use_included_pairs + "\n" +
                "point_file = " + point_file + "\n" +
                "\n"  +
                "[Output options]" + "\n" +
                "write_cum_cur_map_only = " + write_cum_cur_map_only + "\n" +
                "log_transform_maps = " + log_transform_maps + "\n" +
                "set_focal_node_currents_to_zero = " + set_focal_node_currents_to_zero + "\n" +
                "output_file = " + output_file + "\n" +
                "write_max_cur_maps = " + write_max_cur_maps + "\n" +
                "write_volt_maps = " + write_volt_maps + "\n" +
                "set_null_currents_to_nodata = " + set_null_currents_to_nodata + "\n" +
                "set_null_voltages_to_nodata = " + set_null_voltages_to_nodata + "\n" +
                "compress_grids = " + compress_grids + "\n" +
                "write_cur_maps = " + write_cur_maps + "\n" +
                "\n" +
                "[Short circuit regions (aka polygons)]" + "\n" +
                "use_polygons = " + use_polygons + "\n" +
                "polygon_file = " + polygon_file + "\n" +
                "\n" +
                "[Connection scheme for raster habitat data]" + "\n" +
                "connect_four_neighbors_only = " + connect_four_neighbors_only + "\n" +
                "connect_using_avg_resistances = " + connect_using_avg_resistances + "\n" +
                "\n" +
                "[Habitat raster or graph]\n" +
                "habitat_file = " + habitat_file + "\n" +
                "habitat_map_is_resistances = " + habitat_map_is_resistances + "\n" +
                "\n" +
                "[Options for one-to-all and all-to-one modes]\n" +
                "use_variable_source_strengths = " + use_variable_source_strengths + "\n" +
                "variable_source_file = " + variable_source_file + "\n" +
                "\n" +
                "[Version]\n" +
                "version = " + version + "\n" +
                "\n" +
                "[Mask file]\n" +
                "use_mask = " + use_mask + "\n" +
                "mask_file = " + mask_file + "\n" +
                "\n" +
                "[Circuitscape mode]\n" +
                "data_type = " + data_type + "\n" +
                "scenario = " + scenario + "\n"
                )

    # Write the .ini file content to a new file
    inipath = tmppath + "csbatch.ini"
    ini = open(inipath, "w")
    ini.write(inistring)
    ini.close()

    # Finally run Circuitscape
    try:
        cs = subprocess.check_call([CS_Path, inipath], shell=False)
    except:
        print("Error with running Circuitscape")


    # Import results into GRASS

    # Import cumulative current map
    curmap_cum_in = tmppath + output_prefix + "_cum_curmap.asc"
    curmap_cum_out = output_prefix + "_" + "cumulative"
    grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=curmap_cum_in, output=curmap_cum_out)

    # If the maximum current map flag ("x") is checked, import that too
    if flags["x"]:
        max_curmap_in = tmppath + output_prefix + "_max_curmap.asc"
        max_curmap_out = output_prefix + "_" + "maxcurrent"
        grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=curmap_cum_in, output=max_curmap_out)

    # If "write cumulative current map only" flag ("c") is NOT checked AND current maps are created, import all current maps
    if (not flags["c"]) and (maptype == "Current" or maptype == "Both"):
        if scenario == "pairwise":  # for pairwise mode, there's going to be a lot more maps
            for pair in pairlist:    # import current maps with all possible pairs
                curpair_in = tmppath + output_prefix + "_curmap_" + pair + ".asc"    # The path and filename of circuitscape generated current pair map
                curpair_out = output_prefix + "_cur_" + pair     # The output name for r.in.gdal that imports current pair maps into GRASS
                grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=curpair_in, output=curpair_out)
        else:   # for all-to-one, or one-to-all mode
            for feat in featlist:    # Iterate through all features
                curmap_in = tmppath + output_prefix + "_curmap_" + str(feat) + ".asc"
                curmap_out = output_prefix + "_cur_" + str(feat)
                grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=curmap_in, output=curmap_out)

    # If voltage map are created, import them
    if maptype == "Voltage" or maptype == "Both":
        if scenario == "pairwise":
            for pair in pairlist:
                voltpair_in = tmppath + output_prefix + "_voltmap_" + pair + ".asc"    # The path and filename of circuitscape generated voltage pair map
                voltpair_out = output_prefix + "_volt_" + pair     # The output name for r.in.gdal that imports current pair maps into GRASS
                grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=voltpair_in, output=voltpair_out)
        else:
            for feat in featlist:
                voltmap_in = tmppath + output_prefix + "_voltmap_" + str(feat) + ".asc"
                voltmap_out = output_prefix + "_volt_" + str(feat)
                grass.run_command('r.in.gdal', flags="o", overwrite=overw, input=voltmap_in, output=voltmap_out)


    # Delete temporary files
    filelist = [ file for file in os.listdir(tmppath) if file.startswith(output_prefix) ]    # Create a list of files in tmp dir that starts with our prefix
    for file in filelist:   # Delete each file in the tmpdir that is specified in the filelist created previously
        os.remove(tmppath+file)
    os.remove(cost_ascii)   # Delete ascii cost raster
    os.remove(feats_ascii)  # Delete ascii features raster
    grass.run_command('g.remove', rast = tmp_featraster)    # And finally get rid of the temporary rasterised feature layer


def featpairs(vectlayer):
    # Method creating a list of possible feature pairs. Perhaps should use ctypes instead of grass.script?

    featdict = grass.vector.vector_db_select(vectlayer, columns='cat')['values']    # Get the dictionary of feature categories
    featlist = featdict.keys()  # Create a list of the dictionary keys
    n_feats = len(featlist)     # Get the number of features (i.e. list item count)
    pairlist = []               # New list for storing feature pairs
    for feat in featlist:       # A loop that creates list of feature pairs (e.g. ["1_2","1_3","1_4","2_3","2_4"...])
        for feat2 in featlist:
            if feat2 > feat:
                pairlist.append(str(feat) + "_" + str(feat2))
    return featlist, pairlist    # Return feature count and the pair list


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
