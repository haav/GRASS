#!/usr/bin/env python
############################################################################
#
# MODULE:       r.friction
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for creating friction surface from DEM. Currently
#               only two forumlae are provided: the Tobler's Hiker's formula
#               and Minetti's. More info and citations below in the code.
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Creates a friction surface from input raster DEM. Useful for cost surface analyses.
#% keywords: friction
#% keywords: cost
#% keywords: raster
#%end
#%option G_OPT_R_INPUT
#% key: input
#% gisprompt: old,raster
#% description: Input elevation map 
#% required: yes
#%end
#%option G_OPT_R_OUTPUT
#% key: friction
#% gisprompt: new,raster
#% description: Output friction raster
#% required: yes
#%end
#%option G_OPT_R_OUTPUT
#% key: slope
#% gisprompt: new,raster
#% description: Optional output slope raster
#% required: no
#%end
#%option
#% key: formula
#% type: string
#% required: yes
#% multiple: no
#% options: Hiker, Minetti
#% description: Friction surface formula
#% answer: Hiker
#%End

import os, sys
import grass.script as grass

def main():
    # User inputs
    dem = options['input']          # Elevation map
    out = options['friction']       # Output friction surface
    slope = options['slope']        # Optional output slope
    formula = options['formula']    # Formula

    # Error if no friction surface is given
    if not grass.find_file(dem)['name']:
        grass.message(_("Input raster <%s> not found") % dem)
        sys.exit()

    # If output raster exists, but overwrite option isn't selected
    if not grass.overwrite():
        if grass.find_file(out)['name']:
            grass.message(_("Output raster map <%s> already exists") % out)
            sys.exit()

    # Check if slope output name is specified and give error message if it needs to be overwritten but overwrite option isn't selected
    if not slope:
        slope = "tmp_slope_%d_" %os.getpid()
    else:
        if not grass.overwrite():
            if grass.find_file(slope)['name']:
                grass.message(_("Output raster map <%s> already exists") % slope)
                sys.exit()

    # Generate slope (in percent)
    grass.run_command('r.slope.aspect', elevation=dem, slope=slope, format='percent')

    # Choose formula
    if formula == 'Hiker':
        # So-called "Hiker's formula"
        # Tobler W (1993) Three Presentations on Geographical Analysis and Modeling. Technical Report 93-1. California
        # Gorenflo LJ and Gale N (1990) Mapping Regional Settlement in information Space. Journal of Antropological Archaeology (9): 240 - 274
        expression = "$outmap = 1.0 / (( 6.0 * exp(-3.5 * abs(( $slope / 100) + 0.05 ))) * 1000)"
    elif formula == 'Minetti':
        # This formula is presentedy by I. Herzog who based the formula on the physiological data by Minetti.
        # Herzog, I. In press. "Theory and Practice of Cost Functions." In Fusion  of  Cultures.  Proceedings  of  the
        # XXXVIII  Conference  on  Computer  Applications  and Quantitative Methods in Archaeology, CAA 2010.
        expression = "$outmap = 1337.8 * ($slope / 100)^6 + 278.19 * ($slope / 100)^5 - 517.39 * ($slope / 100)^4 - 78.199 * ($slope / 100)^3 + 93.419 * ($slope / 100)^2 + 19.825 * ($slope / 100) + 1.64"
    else:
        grass.message("No valid formula chosen")
        sys.exit()

    # Create friction surface
    try:
        grass.mapcalc(expression, outmap = out, slope = slope)
        grass.message("Friction raster <" + out + "> complete")
    except:
        grass.run_command('g.remove', rast = slope)
        grass.message("Unable to finish operation. Temporary slope raster deleted.")
        sys.exit()

    # Delete temporary slope map if necessary
    if not options['slope']:
        grass.run_command('g.remove', rast = slope)

    grass.message("All done")

if __name__ == "__main__":
    options, flags = grass.parser()
    main()
