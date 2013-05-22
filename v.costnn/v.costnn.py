#!/usr/bin/env python
############################################################################
#
# MODULE:       v.costnn
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for cost distance based nearest neighbour analysis.
#               Relies on r.lcp module to measure cost distances.
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################
#%module
#% description: Cost distance based nearest neighbour analysis
#% keywords: nn
#% keywords: cost
#% keywords: raster
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
#% key: friction
#% type: string
#% gisprompt: old,raster
#% key_desc: friction map name
#% description: Name of friction map 
#% required: yes
#%end

#%option
#% key: simulations
#% type: integer
#% description: Number of simulations to be carried out
#% required: yes
#% answer: 19
#%end

import grass.script as grass
import grass.lib.gis as gis
import os, sys
import math

def main():
    # Input data
    inputlayer = options['points']       # Point layer
    frictionlayer = options['friction']  # Friction layer
    simulations = int(options['simulations']) # Number of simulations
    
    # Create a temporary filename
    pid = os.getpid()
    costnn = "tmp_costnn_%d" % pid
    randompoints = "tmp_randompoints_%d" % pid
    
    # Do the initial lcp vector layer for input point layer
    grass.run_command("r.lcp", overwrite = True, flags="c", friction = frictionlayer, points = inputlayer, radius = 0, nearpoints = 1, vectout = costnn)
    
    # Get input point layer nearest neighbour costs
    maincosts = attributes(costnn, "cost")
    # Number of points in the input point layer
    n_points = len(maincosts)
    
    # This is the mean cost distance for input point layer
    mainlayer = sum(maincosts)/n_points
    # Create an empty list to hold simulated pattern mean cost distance values
    mc = list()

    # Monte Carlo loop
    for i in range(simulations):
        # Create random points and create lcp-s
        grass.run_command("v.random", overwrite = True, output = randompoints, n = n_points)
        grass.run_command("r.lcp", overwrite = True, flags="c", friction = frictionlayer, points = randompoints, radius = 0, nearpoints = 1, vectout = costnn)
        # Get the mean of distances and add it to the mc list
        mccosts = attributes(costnn, "cost")
        mcmean = float(sum(mccosts)) / float(len(mccosts))
        mc.append(mcmean)
    
    # Calculate the distribution for simulated patterns
    # Get the mean of the distribution of mean simulated pattern cost distances
    mc_mean = float(sum(mc)) / float(len(mc))
    # Calculate population standard deviation
    mc_diff = []
    for i in mc:
        mc_diff.append((i - mc_mean)**2)
    mc_stddev = math.sqrt(float(sum(mc_diff))/float(n_points))
    
    # Get the 95% and 99% upper and lower values
    mc_upper95 = mc_mean + 1.96*mc_stddev
    mc_lower95 = mc_mean - 1.96*mc_stddev
    mc_upper99 = mc_mean + 2.58*mc_stddev
    mc_lower99 = mc_mean - 2.58*mc_stddev
    
    print("Clustered pattern if input mean NN distance > simulated upper values.\nOrdered pattern if input mean NN distance < simulated lower values.\nNot significantly clustered or ordered if input mean NN distance falls inside simulated distribution.")
    print("--------------------------------------------------")
    print("Number of points: " + str(n_points))
    print("Input point nearest neighbour distance mean: " + str(mainlayer))
    print("Simulated distribution nearest neighbour distance mean: " + str(mc_mean))
    print("Simulated distribution standard deviation: " + str(mc_stddev))
    print("Simulated distribution upper 95% value: " + str(mc_upper95))
    print("Simulated distribution lower 95% value: " + str(mc_lower95))
    print("Simulated distribution upper 99% value: " + str(mc_upper99))
    print("Simulated distribution lower 99% value: " + str(mc_lower99))

    # Delete temporary files
    grass.run_command("g.remove", vect = costnn, quiet = True)
    grass.run_command("g.remove", vect = randompoints, quiet = True)

def attributes(layer, column):
    # Method that returns attribute data as a list
    temp = grass.tempfile()
    # ... and create and open a new file for writing with that temporary name.
    layer_temp = file(temp, 'w')
    # Get vector layer attribute data and write it to layer_temp
    grass.run_command("v.db.select", flags="c", map=layer, columns=column, stdout = layer_temp)
    layer_temp.close()
    
    # Create a list for holding the attribute values
    attlist = []
    # Open the file where attribute data ise stored and write each feature attribute data into the list
    layer_temp = file(temp)
    for feat in layer_temp:
        attlist.append(float(feat))
    layer_temp.close()
    return attlist


if __name__ == "__main__":
    options, flags = grass.parser()
    main()
