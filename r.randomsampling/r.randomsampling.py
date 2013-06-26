#!/usr/bin/env python
############################################################################
#
# MODULE:       r.randomsampling
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for random sampling of a raster map
#
#
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Random sampling
#% keywords: random
#% keywords: monte carlo
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
#% description: Output file
#% required: yes
#% answer: C:\\MSc\\GIS\\Analyses\\file.csv
#%end

#%option
#% key: size
#% type: integer
#% description: Sample size
#% required: yes
#% answer: 1
#%end

#%option
#% key: nsim
#% type: integer
#% description: Number of iterations to be carried out
#% required: yes
#% answer: 1
#%end

import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis
import os, sys

def main():
    # Input data
    input = options['input']                  # Raster
    size = int(options['size'])                    # Sample size
    nsim = int(options['nsim'])                    # No of simulations
    filepath = options['output']              # Output file path
    
    
    # Create new csv file
    csv = open(filepath, "w")
    classes = ""
    for n in range(1,size+1):
        classes = classes + str("p") + str(n)
        if n != size:
            classes = classes + ","
    csv.write(classes)
    csv.close()

    for i in range(0,nsim):
        # Create size * nsim random points
        grass.run_command('r.random', overwrite = True, flags = "b", input=input, n=size, vector_output="tmp_mc")
        # r.random -b --overwrite input=slope@slope_aspect n=1370000 vector_output=randomvector
        
        # Open vector point layer and read values
        content = attributes("tmp_mc", "value")

        # Append data to a csv file
        csv = open(filepath, "a")
        csv.write("\n")
        for item in content:
            csv.write(str(item))
            if item != content[len(content)-1]:
                csv.write(",")
        csv.close()
    
    
def attributes(layer, column):
    # Method that returns attribute data as a list
    temp = grass.tempfile()
    # Create and open a new file for writing with that temporary name.
    layer_temp = file(temp, 'w')
    # Get vector layer attribute data and write it to layer_temp
    grass.run_command("v.db.select", flags="c", map=layer, columns=column, stdout = layer_temp)
    layer_temp.close()
    
    # Create a list for holding the attribute values
    attlist = []
    # Open the file where attribute data is stored and write each feature attribute data into the list
    layer_temp = file(temp)
    for feat in layer_temp:
        attlist.append(float(feat))
    layer_temp.close()
    return attlist
    
if __name__ == "__main__":
    options, flags = grass.parser()
    main()
