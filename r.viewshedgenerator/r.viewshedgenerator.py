#!/usr/bin/env python
############################################################################
#
# MODULE:       r.viewshedgenerator
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A small script for generating a bunch of single viewsheds
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Single viewshed generator
#% keywords: visibility
#% keywords: viewshed
#% keywords: raster
#%end

#%option
#% key: dem
#% type: string
#% gisprompt: old,raster
#% description: Input elevation model
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
#% key: obs_height
#% type: double
#% description: Observer's height
#% answer: 1.75
#% required: no
#%end

#%option
#% key: target_height
#% type: double
#% description: Offset for target elevation above the ground
#% answer: 0.0
#% required: no
#%end

#%option
#% key: maxradius
#% type: double
#% description: Maximum visibility radius. Default (-1) is infinity
#% answer: -1
#% required: no
#%end

#%flag
#% key: c
#% description: Take into account the Earth's curvature
#%end

#%option
#% key: prefix
#% type: string
#% answer: viewshed_
#% description: Output layer name prefix (point number will follow)
#% required:no
#%end

import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis
import os, sys

def main():
    # Input data
    points = options['points']                  # Point layer
    dem = options['dem']                        # Elevation model
    curvature = "c" if flags['c'] else ""       # Earth's curvature flag
    obs_height = options['obs_height']          # Observer's height
    target_height = options['target_height']    # Target height offset
    maxradius = options['maxradius']            # Max radius
    output_prefix = options['prefix']           # Output layer prefix
    
    
    """ Routine for getting point coordinates """
    # Create a new Map_info() object
    map = vect.pointer(vect.Map_info())
    # Load the vector map to Map_info() object. Level should be 2 (with topology)
    vect.Vect_open_old2(map, points, "", "-1")
    # Get number of point features (1) in the layer
    n_lines = vect.Vect_get_num_primitives(map, 1)
    # Create new line and categories structures
    line = vect.Vect_new_line_struct()
    cats = vect.Vect_new_cats_struct()
    # Make an empty dictionary to store all feature cats and their coordinates in
    coordsdict = {}
    # Iterate through all features and write their coordinates to the dictionary
    for i in xrange(0, n_lines):
        # Read next line from Map_info()
        vect.Vect_read_next_line(map, line, cats, 1)
        # Get line structure values, i.e. coordinates
        x = line.contents.x[0]
        y = line.contents.y[0]
        # Get the point category number
        cat = cats.contents.cat[0]
        coordsdict[cat] = (x,y)
    # Do some cleanup
    vect.Vect_destroy_line_struct(line)
    vect.Vect_destroy_cats_struct(cats)
    vect.Vect_close(map)
    
    # Do the loop
    for pointnumber in range(1,n_lines + 1):
        # Get x and y coordinates from dictionary created earlier and merge them into one string
        xcoord, ycoord = coordsdict[pointnumber]
        point_coords = str(str(xcoord) + "," + str(ycoord))
        # Generate output raster name
        outraster = str(str(output_prefix) + str(pointnumber))
        # Run r.viewshed
        grass.run_command('r.viewshed', flags = curvature, overwrite = True, input = dem, output = outraster, coordinates = point_coords, obs_elev = obs_height, tgt_elev = target_height, max_dist = maxradius)
        
if __name__ == "__main__":
    options, flags = grass.parser()
    main()
