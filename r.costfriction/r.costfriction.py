#!/usr/bin/env python
############################################################################
#
# MODULE:       r.costfriction
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for creating cost friction map from DEM.
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################

#%module
#% description: Creates a cost friction raster from input raster DEM. Useful for cost surface analyses, e.g. finding least cost paths.
#% keywords: friction
#% keywords: cost surface
#% keywords: raster
#%end
#%option
#% key: input
#% type: name
#% gisprompt: old,raster
#% description: Name of input elevation map 
#% required: yes
#%end
#%option
#% key: friction
#% type: name
#% gisprompt: new,raster
#% description: Name of output friction raster
#% required: yes
#%end
#%option
#% key: slope
#% type: name
#% gisprompt: new,raster
#% description: Optional output slope raster
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
    dem = options['input']
    out = options['friction']
    slope = options['slope']
    formula = options['formula']
    # New variable that is later being checked if specified slope output is Null in which case the temporary slope raster is deleted
    delete_slope = slope

    # Check if slope output name is specified
    if not slope:
        slope = "tmp_slope" + str(os.getpid())

    # Generate slope (in percent)
    grass.run_command('r.slope.aspect', elevation=dem, slope=slope, format='percent')

    # Choose formula
    if formula == 'Tobler':
        # Tobler W (1993) Three Presentations on Geographical Analysis and Modeling. Technical Report 93-1. California
        # Gorenflo LJ and Gale N (1990) Mapping Regional Settlement in information Space. Journal of Antropological Archaeology (9): 240 - 274
        expression = "$outmap = 1.0 / (( 6.0 * exp(-3.5 * abs(( $slope / 100) + 0.05 ))) * 1000)"
    elif formula == 'Minetti':
        # Minetti 2002 / Herzog 2010
        # KONTROLLI SEE VALEM ÜLE NING PANE KA TÄPSEMAD VIITED!
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
