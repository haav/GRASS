#!/usr/bin/env python
############################################################################
#
# MODULE:       r.totalcost
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A tool for landscape connectivity analysis. The output of
#               the tool is a "total cost map". Idea from: 
#               Mlekuz, D. In press. "Time Geography, GIS and archaeology." 
#               In Fusion of Culture. Proceedings of the XXXVIII Conference 
#               on Computer Applications and Quantitative Methods in 
#               Archaeology, 6-9 April 2010, Granada.
#               Editors: F. Contreras, M. Farjas and F. J. Melero.
#               Oxford: Archaeopress.
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Total cost map calculation
#% keywords: connectivity
#% keywords: cost
#% keywords: raster
#%end

#%option
#% key: friction
#% type: string
#% gisprompt: old,raster
#% description: Input friction raster with values per map unit
#% required: yes
#%end

#%option G_OPT_R_OUTPUT
#% key: out
#% gisprompt: new,raster
#% description: Output total cost map
#% required: yes
#%end

#%option
#% key: maxcost
#% type: double
#% description: Maximum cost distance
#% required: yes
#%end

#%option
#% key: mempercent
#% type: integer
#% description: Percent of map to keep in memory when calculating cost distances
#% answer: 40
#% required: no
#%end

#%flag
#% key: e
#% description: Only calculate potential cost distance range / edge effect
#%end

#%flag
#% key: k
#% description: Use "Knight's move" instead of "Queen's move"; slower, but more accurate 
#%end

import sys, os, atexit
import grass.lib.gis as gis
import grass.script as grass
#import grass.pygrass as pygrass    # pygrass is currently broken in GRASS 7. Once it gets fixed it'll be used here again

# List to hold temporary layer names for easier removal
tmp_layers = []

def main():
    # Get user inputs
    friction_original = options['friction'] # Input friction map
    out = options['out']                    # Output totalcost raster
    maxcost = options['maxcost']            # Max cost distance in cost units
    knight = "k" if flags["k"] else ""      # Use Knight's move in r.cost instead Queen's move (a bit slower, but more accurate)
    mempercent = int(options['mempercent']) # Percent of map to keep in memory in r.cost calculation

    # Error if no valid friction surface is given
    if not grass.find_file(friction_original)['name']:
        grass.message(_("Friction surface <%s> not found") % friction_original)
        sys.exit()

    # Calculate cost distances / edge effect distances from the friction map. Result is in map units
    info = grass.raster_info(friction_original)             # Read and get raster info
    edgeeffect_min = float(maxcost) / float(info['max'])    # Minimum cost distance / edge effect distance
    edgeeffect_max = float(maxcost) / float(info['min'])    # Maximum cost distance / edge effect distance
    
    # If "Only calculate edge effect" is selected
    if flags['e']:
        grass.message("Minimum distance / edge effect: " + str(edgeeffect_min))
        grass.message("Maximum distance / edge effect: " + str(edgeeffect_max))
        sys.exit()

    # If output file exists, but overwrite option isn't selected
    if not grass.overwrite():
        if grass.find_file(out)['name']:
            grass.message(_("Output raster map <%s> already exists") % out)
            sys.exit()

    # Get raster calculation region information
    regiondata = grass.read_command("g.region", flags = 'p')
    regvalues = grass.parse_key_val(regiondata, sep= ':')
    # Assign variables for necessary region info bits
    nsres = float(regvalues['nsres'])
    ewres = float(regvalues['ewres'])
    # Calculate the mean resolution
    meanres = (nsres + ewres) / 2.0
    
    # Create a list holding cell coordinates
    coordinatelist = []             # An empty list that will be populated with coordinates
    rasterdata = grass.read_command('r.stats', flags="1gn", input = friction_original)  # Read input raster coordinates
    rastervalues = rasterdata.split()   # Split the values from r.stats into list entries
    # rastervalues list is structured like that: [x1, y1, rastervalue1, x2, y2, rastervalue2 ... xn, yn, rastervaluen], so iterate through that list with step of 3 and write a new list that has coordinates in a string: ["x1,y1", "x2,y2" ... "xn,yn"]
    for val in xrange(0,len(rastervalues),3):
        coordinatelist.append(rastervalues[val] + "," + rastervalues[val+1])
        
    # This is the number of cells (and hence cost surfaces) to be used
    n_coords = len(coordinatelist)

    # Create temporary filenames with unique process id in their name. Add each name to the tmp_layers list.
    pid = os.getpid()
    cost1 = str("tmp_totalcost_cost1_%d" % pid)
    tmp_layers.append(cost1)
    cost2 = str("tmp_totalcost_cost2_%d" % pid)
    tmp_layers.append(cost2)
    cost3 = str("tmp_totalcost_cost3_%d" % pid)
    tmp_layers.append(cost3)
    cost4 = str("tmp_totalcost_cost4_%d" % pid)
    tmp_layers.append(cost4)
    friction = str("tmp_friction_%d" % pid)
    tmp_layers.append(friction)
    calctemp = str("tmp_calctemp_%d" % pid)
    tmp_layers.append(calctemp)

    # Assuming the friction values are per map unit (not per cell), the raster should be multiplied with region resolution. This is because r.cost just uses cell values and adds them - slightly different approach compared to ArcGIS which compensates for the resolution automatically. The result is then divided by maxcost so that r.cost max_cost value can be fixed to 1 (it doesn't accept floating point values, hence the workaround).
    grass.mapcalc("$outmap = $inmap * $res / $mcost", outmap = friction, inmap = friction_original, res = meanres, mcost = maxcost)

    # Do the main loop
    for c in xrange(0, n_coords, 4):    # Iterate through the numbers of cells with the step of 4

        # Start four r.cost processes with different coordinates. The first process (costproc1) is always made, but the other 3 have the condition that there exists a successive coordinate in the list. This is because the used step of 4 in the loop. In case there are no coordinates left, assign the redundant cost outputs null-values so they wont be included in the map calc. 
        try:
            costproc1 = grass.start_command('r.cost', overwrite = True, flags = knight, input = friction, output = cost1, start_coordinates = coordinatelist[c], max_cost = 1, percent_memory = mempercent)
            if c+1 < n_coords:
                costproc2 = grass.start_command('r.cost', overwrite = True, flags = knight, input = friction, output = cost2, start_coordinates = coordinatelist[c+1], max_cost = 1, percent_memory = mempercent)
            else:
                cost2 = "null()"
            if c+2 < n_coords:
                costproc3 = grass.start_command('r.cost', overwrite = True, flags = knight, input = friction, output = cost3, start_coordinates = coordinatelist[c+2], max_cost = 1, percent_memory = mempercent)
            else:
                cost3 = "null()"
            if c+3 < n_coords:
                costproc4 = grass.start_command('r.cost', overwrite = True, flags = knight, input = friction, output = cost4, start_coordinates = coordinatelist[c+3], max_cost = 1, percent_memory = mempercent)
            else:
                cost4 = "null()"
        except:
            grass.message("Error with r.cost: " + str(sys.exc_info()[0]))
            sys.exit()

        # For the very first iteration just add those first r.cost results together
        if c == 0:
            # Wait for the r.cost processes to stop before moving on
            costproc1.wait()
            costproc2.wait()
            costproc3.wait()
            costproc4.wait()
            # Do the map algebra: merge the cost surfaces
            try:
                grass.mapcalc("$outmap = if(isnull($tempmap1),0,1) + if(isnull($tempmap2),0,1) + if(isnull($tempmap3),0,1) + if(isnull($tempmap4),0,1)", outmap = out, tempmap1 = cost1, tempmap2 = cost2, tempmap3 = cost3, tempmap4 = cost4, overwrite=True)
            except:
                grass.message("Error with mapcalc: " + str(sys.exc_info()[0]))
                sys.exit()
        # If it's not the first iteration...
        else:
            # Rename the output of previous mapcalc iteration so that it can be used in the mapcalc expression (x = x + y logic doesn't work apparently)
            try:
                # If pygrass gets fixed, replace g.rename with those commented out pygrass-based lines as they seem to be a bit faster (are they really?)
                #map = pygrass.raster.RasterRow(out)
                #map.name = calctemp
                grass.run_command('g.rename', overwrite = True, rast = out + "," + calctemp)
            except:
                grass.message("Error: " + str(sys.exc_info()[0]))
                sys.exit()
            # Wait for the r.cost processes to stop before moving on
            costproc1.wait()
            costproc2.wait()
            costproc3.wait()
            costproc4.wait()
            # Merge the r.cost results and the cumulative map from previous iteration
            try:
                grass.mapcalc("$outmap = if(isnull($inmap),0,$inmap) + if(isnull($tempmap1),0,1) + if(isnull($tempmap2),0,1) + if(isnull($tempmap3),0,1) + if(isnull($tempmap4),0,1)", inmap = calctemp, outmap = out, tempmap1 = cost1, tempmap2 = cost2, tempmap3 = cost3, tempmap4 = cost4, overwrite=True)
            except:
                grass.message("Error with mapcalc: " + str(sys.exc_info()[0]))
                sys.exit()
    
    # Finally print the edge effect values
    grass.message("---------------------------------------------")
    grass.message("Minimum distance / edge effect: " + str(edgeeffect_min))
    grass.message("Maximum distance / edge effect: " + str(edgeeffect_max))


def cleanup():  # Cleaning service
   for layer in tmp_layers:
       grass.run_command("g.remove", rast = layer, quiet = True)


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
