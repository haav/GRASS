############################################################################
#
# MODULE:   r.costfriction
# AUTHOR(S):    Allar Haav
#
# PURPOSE:  Create cost friction raster
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (version 2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################

#%module
#% description: Cost friction surface creation
#% keywords: lcp
#% keywords: raster
#%end
#%option
#% key: dem
#% type: string
#% gisprompt: old,raster
#% key_desc: elevation map name
#% description: Name of elevation map 
#% required: yes
#%end
#%option
#% key: out
#% type: string
#% gisprompt: new,raster
#% key_desc: Output raster
#% description: Name of output raster
#% required: yes
#%end
#%option
#% key: slope
#% type: string
#% gisprompt: raster
#% key_desc: Slope raster
#% description: Name of slope raster
#% required: no
#%end
#%option
#% key: formula
#% type: string
#% required: yes
#% multiple: no
#% options: Tobler, Minetti
#% description: Friction surface formula
#% answer: Tobler
#%End


import os
import grass.script as grass

def main():
    #inputs
    dem = options['dem']
    out = options['out']
    slope = options['slope']
    formula = options['formula']
    # New variable that is later being checked if specified slope output is Null in which case the temporary slope raster is deleted
    delete_slope = slope
    
    # Check if slope output name is specified
    if not slope:
        slope = "tmp_slope" + str(os.getpid())

    # Generate slope
    grass.run_command('r.slope.aspect', elevation=dem, slope=slope, format='percent')

    if formula == 'Tobler':
        expression = "$outmap = 1.0 / (( 6.0 * exp(-3.5 * abs(( $slope / 100) + 0.05 ))) * 1000)"
    elif formula == 'Minetti':
        # Minetti 2002 / Herzog 2010
        expression = "$outmap = 1337.8 * ($slope / 100)^6 + 278.19 * ($slope / 100)^5 - 517.39 * ($slope / 100)^4 - 78.199 * ($slope / 100)^3 + 93.419 * ($slope / 100)^2 + 19.825 * ($slope / 100) + 1.64"
    else:
        grass.fatal("No valid formula chosen")

    # Create friction surface
    grass.mapcalc(expression, outmap = out, slope = slope)
    
    # Delete temporary slope map if necessary
    if not delete_slope:
        grass.run_command('g.remove', rast = slope)
    grass.message("All done")
    
if __name__ == "__main__":
    options, flags = grass.parser()
    main()
