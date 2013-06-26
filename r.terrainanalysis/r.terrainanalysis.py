#!/usr/bin/env python
############################################################################
#
# MODULE:       r.terrainanalysis
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for terrain analysis. Currently with only 
#               Deviation from Mean statistic
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Terrain analysis
#% keywords: terrain analysis
#% keywords: dem
#% keywords: raster
#%end

#%option
#% key: input
#% type: string
#% gisprompt: old,raster
#% description: Input raster
#% required: yes
#%end

#%option
#% key: output
#% type: string
#% gisprompt: new,raster
#% description: Output raster
#% required: yes
#%end

#%option
#% key: nsize
#% type: integer
#% description: Neighbourhood cells number (positive odd number)
#% required: yes
#% answer: 1
#%end

#%option
#% key: statistic
#% type: string
#% required: yes
#% multiple: no
#% options: Deviation from Mean
#% description: Statistic
#% answer: Deviation from Mean
#%End

#%flag
#% key: c
#% description: Circular neighbourhood
#%end

import atexit
import grass.script as grass
import grass.lib.gis as gis
import os, sys

tmp_rlayers = list()

def main():
    # Input data
    inraster = options['input']
    outraster = options['output']
    nsize = options['nsize']
    statistic = options['statistic']
    circular = "c" if flags['c'] else ""
    
    # Get process id
    pid = os.getpid()

    # Check overwrite settings
    # If output raster file exists, but overwrite option isn't selected
    if not grass.overwrite():
        if grass.find_file(outraster)['name']:
            grass.message(_("Output raster map <%s> already exists") % outraster)
            sys.exit()
    
    # Choose the statistic
    if statistic == "Deviation from Mean":
        
        # First, get neighbourhood mean rasters
        tmp_avg = "tmp_avg_%d" % pid    # Create a temporary filename
        tmp_rlayers.append(tmp_avg)
        proc_avg = grass.start_command('r.neighbors', overwrite = True, flags = circular, input=inraster, output=tmp_avg, size=nsize)
        
        # Get neighbourhood standard deviation rasters
        tmp_stddev = "tmp_stddev_%d" % pid    # Create a temporary filename
        tmp_rlayers.append(tmp_stddev)
        proc_stddev = grass.start_command('r.neighbors', overwrite = True, flags = circular, method="stddev", input=inraster, output=tmp_stddev, size=nsize)
        
        # Wait for the processes to finish
        proc_avg.wait()
        proc_stddev.wait()
        
        # Calculate Deviation from Mean
        grass.mapcalc("$outmap = ($inraster - $avgraster) / $stddevraster", outmap = outraster, inraster = inraster, avgraster = tmp_avg, stddevraster = tmp_stddev)
    
    
def cleanup(): # Cleaning service
   for layer in tmp_rlayers:
       grass.run_command("g.remove", rast = layer, quiet = True)
       
if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
