#!/usr/bin/env
############################################################################
#
# MODULE:       r.circuit
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      An interface to Circuitscape software
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################

#%module
#% description: Circuitscape
#% keywords: lcp
#% keywords: cost
#% keywords: raster
#%end

#%option
#% key: friction
#% type: string
#% gisprompt: old,raster
#% key_desc: friction map name
#% description: Name of friction map 
#% required: yes
#%end

#%option
#% key: points
#% type: string
#% gisprompt: old,vector
#% key_desc: Point layer name
#% description: Point layer
#% required: yes
#%end

#%option
#% key: scenario
#% type: string
#% answer: pairwise
#% options: pairwise, one-to-all, all-to-one
#% key_desc: Mode
#% description: Modelling mode
#% required: yes
#%end

#%flag
#% key: l
#% description: Low memory mode for pairwise mode (requires less memory, but takes longer)
#%end

#%flag
#% key: c
#% description: Write cumulative current map only
#%end

#%flag
#% key: r
#% description: Use rook's move (4 neighbours only, instead of 8)
#%end

import subprocess
import atexit, sys, os
import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis


def cleanup():
    # Cleanup procedures
    print "All done"

    


    
def main():

    # Some preliminaries
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
    
    # Layer and file names
    # User inputs
    friction = options['friction']  # Input friction raster
    points = options['points']  # Input friction raster
    scenario = options['scenario'] # Modelling mode
    # Temporary stuff
    tmp_pointraster = "tmp_circuitscape_pointraster"
    friction_ascii = tmppath + "friction.asc"
    points_ascii = tmppath + "pointfile.asc"
    # Output
    output_prefix = "cs"
    cs_output = tmppath + output_prefix + ".out"
    cs_output_cum = tmppath + output_prefix + "_cum_curmap.asc"
    
    # Get the number of points the list of possible pairs
    n_points, pairlist = pointpairs(points)
    
    # Convert the input points and friction raster into ASCII raster
    grass.run_command('r.out.arc', overwrite=True, input=friction, output=friction_ascii)
    grass.run_command('v.to.rast', overwrite=True, input=points, type="point", output=tmp_pointraster, use="cat")
    grass.run_command('r.out.arc', overwrite=True, input=tmp_pointraster, output=points_ascii)
    
    # Circuitscape settings
    # Options for advanced mode
    ground_file_is_resistances = "True"
    source_file = "(Browse for a current source file)"
    remove_src_or_gnd = "keepall"
    ground_file = "(Browse for a ground point file)"
    use_unit_currents = "False"
    use_direct_grounds = "False"
    
    # Calculation options
    low_memory_mode = "True" if flags["l"] else "False"
    solver = "cg+amg"
    print_timings = "True"
    
    # Options for pairwise and one-to-all and all-to-one modes
    included_pairs_file = "None"
    point_file_contains_polygons = "False"
    use_included_pairs = "False"
    point_file = points_ascii

    # Output options
    write_cum_cur_map_only = "True" if flags["c"] else "False"
    log_transform_maps = "False"
    set_focal_node_currents_to_zero = "False"
    output_file = cs_output
    write_max_cur_maps = "False"
    write_volt_maps = "False"
    set_null_currents_to_nodata = "True"
    set_null_voltages_to_nodata = "True"
    compress_grids = "False"
    write_cur_maps = "True"
    
    # Short circuit regions (aka polygons)
    use_polygons = "False"
    polygon_file = "(Browse for a short-circuit region file)"
    
    # Connection scheme for raster habitat data
    connect_four_neighbors_only = "True" if flags["r"] else "False"
    connect_using_avg_resistances = "True"
    
    # Habitat raster or graph
    habitat_file = friction_ascii
    habitat_map_is_resistances = "True"
    
    # Options for one-to-all and all-to-one modes
    use_variable_source_strengths = "False"
    variable_source_file = "None"
    
    # Version
    version = "3.5.8"
    
    # Mask file
    use_mask = "False"
    mask_file = "None"
    
    # Circuitscape mode
    data_type = "raster"
    scenario = scenario

    
    
    # Toimingud pathide ja muu sellisega, st input stringid tuleb oigesse formaati ajada ini jaoks
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
    
    
    
    # Write the necessary information to a new ini file
    inipath = sys.path[0] + "\\csbatch.ini"
    ini = open(inipath, "w")
    ini.write(inistring)
    ini.close()

    
    # Run Circuitscape
    try:
        cs = subprocess.check_call([CS_Path, inipath], shell=True)
    except:
        print("Error with Circuitscape")
        
    # Import results into GRASS
    curmap_cum_in = tmppath + output_prefix + "_cum_curmap.asc"
    curmap_cum_out = output_prefix + "_" + "cumulative"
    grass.run_command('r.in.gdal', flags="o", overwrite=True, input=curmap_cum_in, output=curmap_cum_out)
    # The following imports all pairwise current maps into GRASS
    if not flags["c"]:
        if scenario == "pairwise":
            for i in range(0,len(pairlist)):
                curpair_in = tmppath + output_prefix + "_curmap_" + pairlist[i] + ".asc"    # The path and filename of circuitscape generated current pair map
                curpair_out = output_prefix + "_" + pairlist[i]     # The output name for r.in.gdal that imports current pair maps into GRASS
                grass.run_command('r.in.gdal', flags="o", overwrite=True, input=curpair_in, output=curpair_out)
        else:
            for i in range(1,n_points+1):
                curmap_in = tmppath + output_prefix + "_curmap_" + str(i) + ".asc"
                curmap_out = output_prefix + "_" + str(i)
                grass.run_command('r.in.gdal', flags="o", overwrite=True, input=curmap_in, output=curmap_out)
                
    # Delete temporary files
    filelist = [ f for f in os.listdir(tmppath) if f.startswith(output_prefix) ]
    for f in filelist:
        os.remove(tmppath+f)
    os.remove(friction_ascii)
    os.remove(points_ascii)
    grass.run_command('g.remove', rast = tmp_pointraster)
    


def pointpairs(pointlayer):
    """ Method creating an array of possible point pairs (handshake problem) """
    
    # First the point layer file must be opened and feature count obtained
    map = vect.pointer(vect.Map_info()) # Create a new Map_info() object
    vect.Vect_open_old2(map, pointlayer, "", "-1")  # Load the vector map to Map_info() object. Level should be 2 (with topology). "-1" means "all layers"
    n_points = vect.Vect_get_num_primitives(map, 1) # Get number of point features (type 1) in the layer
    vect.Vect_close(map)    # Close vector layer
    
    # A "handshake problem" calculation
    pairlist = []
    # n_pairs = n_points * (n_points - 1) / 2     # The number of unique pairs
    for i in range(1,n_points):
        for j in range (1,n_points+1):
            if j > i:
                pairlist.append(str(i) + "_" + (str(j)))
    
    return n_points, pairlist
    
if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
