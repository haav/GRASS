#!/usr/bin/env python
############################################################################
#
# MODULE:       r.multilcp
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for creating multiple least cost paths between points
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################

# KONTROLLI YLE RAADIUS JA CLOSEST PUNKTID. ERITI VIIMANE TEKITAB KAHTLUSI. KOOS NEED KAH HASTI TOOTADA EI TAHA.

#%module
#% description: Multiple Least-cost path creation
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
#% key_desc: point layer name
#% description: Point layer
#% required: yes
#%end
#%option
#% key: output
#% type: string
#% gisprompt: new,raster
#% key_desc: output raster name
#% description: Name of output map 
#% required: yes
#%end
#%option
#% key: radius
#% type: integer
#% key_desc: Search radius. 0 for unlimited
#% description: Radius
#% required: no
#% answer: 0
#%end
#%option
#% key: closepoints
#% type: integer
#% key_desc: Number of closest points. 0 for unlimited
#% description: Closest points
#% required: no
#% answer: 0
#%end
#%option
#% key: netout
#% type: string
#% gisprompt: new,vector
#% key_desc: output vector name
#% description: Name of output network vector 
#% required: no
#%end

#KONTROLLI KAS ON VAJA SYS, STRING JA GIS
import os, sys, string
import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis
from operator import itemgetter


def main():
    # User inputs
    friction = options['friction']  # Input friction raster
    points = options['points']      # Input point layer
    output = options['output']      # Output least cost path raster
    radius = int(options['radius']) # Point search radius
    n_closepoints = int(options['closepoints'])   # Number of closest points
    netout = options['netout']      # Network output

    # Initiate PontLayer() object
    input_points = PointLayer(points)

    # Get process id (pid) and create temporary layer names
    pid = os.getpid() # Process ID, used for making (more or less) unique temporary filenames
    costmap1 = "tmp_cost_%d" % pid # Cost surface from onepoint1
    costmap2 = "tmp_cost_%d_%i" % (pid, 2) # Cost surface from onepoint2; parallel process
    lcpmap1 = "tmp_lcp_%d" % pid # Least cost path map from costmap1
    lcpmap2 = "tmp_lcp_%d_%i" % (pid, 2) # Least cost path map from costmap2; parallel process
    lcptemp = "tmp_lcptemp_%d" % pid # Temporary file for mapcalc
    
    # Create a a long string of all temporary layernames for easy deletion them later on
    tmpvars = costmap1 + "," + costmap2 + "," + lcpmap1 + "," + lcpmap2 + "," + lcptemp
    
    # Get coordinates of input point layer and also the total number of point features in the layer
    #all_coords, n_feats = pointCoords(points)
    #distdict = pointDistances(all_coords, n_feats)
    n_feats = input_points.featCount()

    # Initiate new Popen() object for multiprocessing mapcalc
    mapcalcproc = grass.Popen("")

    # Main loop that creates least cost paths for all points
    for feat in range(1, n_feats +1, 2):
        # Initiate new PointLayer() objects
        layer_point1 = PointLayer(points, feat)
        layer_point2 = PointLayer(points, feat+1)

        if radius > 0 and n_closepoints <= 0:
            drainpointlayer1 = None
            drainpointlayer2 = None
            drainpoints1 = layer_point1.pointsInRadius(radius, stringoutput=True)
            drainpoints2 = layer_point2.pointsInRadius(radius, stringoutput=True)
        elif radius > 0 and n_closepoints > 0:
            drainpointlayer1 = None
            drainpointlayer2 = None
            drainpoints1 = layer_point1.closePointsInRadius(n_closepoints, radius)
            drainpoints2 = layer_point2.closePointsInRadius(n_closepoints, radius)
        elif radius == 0 and n_closepoints > 0:
            drainpointlayer1 = None
            drainpointlayer2 = None
            drainpoints1 = layer_point1.closePoints(n_closepoints)
            drainpoints2 = layer_point2.closePoints(n_closepoints)
        else:
            drainpointlayer1 = points
            drainpointlayer2 = points
            drainpoints1 = None
            drainpoints2 = None

        try:
            lcpproc1 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap1, start_coordinates=layer_point1.oneCoord())
            lcpproc2 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap2, start_coordinates=layer_point2.oneCoord())
            # Least-cost paths from every other point to the current point
            lcpproc1.wait()
            lcpproc1 = grass.start_command('r.drain', overwrite=True, input=costmap1, output=lcpmap1, start_coordinates=drainpoints1, start_points=drainpointlayer1)
            lcpproc2.wait()
            lcpproc2 = grass.start_command('r.drain', overwrite=True, input=costmap2, output=lcpmap2, start_coordinates=drainpoints2, start_points=drainpointlayer2)
            lcpproc1.wait()
            lcpproc2.wait()
        except:
            cleanUp(tmpvars)
            grass.fatal("Problem with lcp creation")

        try:
            if feat == 1:
                mapcalcproc = grass.mapcalc_start("$outmap = if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", outmap = output, tempmap = lcpmap1, tempmap2 = lcpmap2, overwrite=True)
            else:
                # Wait for the mapcalc operation from previous iteration to finish
                mapcalcproc.wait()
                # Rename the cumulative lcp map from previous iteration so that mapcalc can use it (x=x+y doesn't work with mapcalc)
                grass.run_command('g.rename', rast = output + ',' + lcptemp, overwrite=True)
                # output = Previous LCP + Current LCP
                mapcalcproc = grass.start_command('r.mapcalc', "$outmap = $inmap + if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", inmap = lcptemp, outmap = output, tempmap = lcpmap1, tempmap2 = lcpmap2)
        except:
            cleanUp(tmpvars)
            grass.fatal("Problem with mapcalc")
            
    # Wait for last mapcalc to finish
    mapcalcproc.wait()
    # Make 0 values into NULLs
    nullproc = grass.start_command('r.null', map = output, setnull = "0")
    cleanUp(tmpvars)
    nullproc.wait()
    grass.message("All done")

def cleanUp(tmpvars):
    # Delete temporary maps
    grass.run_command('g.remove', rast = tmpvars, vect = tmpvars)

class PointLayer:
    def __init__(self, layername, centerpoint=0):
        self.layer = layername
        if centerpoint > 0:
            self.centerpoint = centerpoint
            self.featcount = self.featCount()
            self.coordsdict = self.getCoords()
            self.distances = self.distances()



    def distances(self):
        # Get feature count /// Could be reused from main?
        n_feats = self.featcount
        # Get coordinates dictionary for the layer /// Could be reused from main?
        distlist = []
        x1, y1 = self.coordsdict[self.centerpoint]
        for feat in range(1, n_feats + 1):
            # if feat == self.centerpoint:
                # pass
            # else:
                x2, y2 = self.coordsdict[feat]
                dist = vect.Vect_points_distance(x1,y1,0,x2,y2,0,0)
                distlist.append((feat, dist))
        return sorted(distlist, key=itemgetter(1))

    def pointsInRadius(self, radius, stringoutput=False):
        """ Returns a list of point id-s that are inside the search radius """
        if stringoutput == False:
            # Create new list
            radiuslist = []
            # Get the list of distances between points
            # Iterate through the distance list and write the point id-s that are inside the search radius into the radiuslist
            for feat in self.distances:
                if feat[1] <= radius:   # second element [1] is distance
                    radiuslist.append(feat[0])  # first element [0] is point id
            return radiuslist
        if stringoutput == True:
            pointsradstring = ""
            iter_no = 0
            for feat in self.distances:
                if feat[1] <= radius:
                    featid = feat[0]
                    pointsradstring = pointsradstring + str(self.coordsdict[featid][0]) + "," + str(self.coordsdict[featid][1]) + ","
            pointsradstring = pointsradstring[:-1]
            return pointsradstring
            
    def closePoints(self, n_points):
        """ Returns a n_points number of point id-s that are closest to the centerpoint in a list form """
        # Create a new list
        n_points = n_points + 1
        #closepoints = []
        clpointsstring = ""
        # Get the list of distances between points
        # If n_points is greater than the number of features in a list, SHUT.DOWN.EVERYTHING.
        if n_points > self.featcount:
            grass.fatal("The specified number of closest points is too high: it must be less than number of features - 1.")
        #Iterate through the distance list and write the n_points of closest point id-s into the list
        for feat in range(0, n_points):
            featid = self.distances[feat][0]
            clpointsstring = clpointsstring + str(self.coordsdict[featid][0]) + "," + str(self.coordsdict[featid][1]) + ","
            #closepoints.append(distlist[feat][0])
            #closepoints.append(distlist[feat][0]) # Write the first tuple element [0] (that is feature id) of each feature list element [feat] into the list
        clpointsstring = clpointsstring[:-1]
        return clpointsstring

    def closePointsInRadius(self, n_points, radius):
        """ Returns a n_points number of point id-s in a search radius that are closest to the centerpoint in a list form """
        # Create a new list
        n_points = n_points + 1
        #closepointsinradius = []
        clpointsinradstring = ""
        # Get the list of points in search radius
        radiuslist = self.pointsInRadius(radius)
        # If n_points is greater than the number of features in a list, SHUT.DOWN.EVERYTHING.
        # Get the number of features in radiuslist
        n_radfeats = len(radiuslist)
        if n_radfeats == 0:
            return [0]
        if n_points > n_radfeats:
            n_points = n_radfeats
        #Iterate through the radius list and write the n_points of closest point id-s into the list
        for feat in range(0, n_points):
            featid = self.distances[feat][0]
            clpointsinradstring = clpointsinradstring + str(self.coordsdict[featid][0]) + "," + str(self.coordsdict[featid][1]) + ","
            # Make sure it's not the last iteration and insert a comma to the end of the string
            #closepointsinradius.append(radiuslist[feat]) # Ilmselt pole seda siis enam vaja?
        #return closepointsinradius
        #Output is a string like: "x1,y1,x2,y2,x3,y3".
        clpointsinradstring = clpointsinradstring[:-1]
        return clpointsinradstring
        
    def featCount(self):
        """ Method returning the number of features in the layer """
        # Create a new Map_info() object
        map = vect.pointer(vect.Map_info())
        # Load the vector map to Map_info() object. Level should be 2 (with topology)
        vect.Vect_open_old2(map, self.layer, "", "-1")
        # Get number of point features (1) in the layer
        n_lines = vect.Vect_get_num_primitives(map, 1)
        # Do some cleanup
        vect.Vect_close(map)
        # Return number of features in the layer as a tuple
        return n_lines

    def getCoords(self):
        # Create a new Map_info() object
        map = vect.pointer(vect.Map_info())
        # Load the vector map to Map_info() object. Level should be 2 (with topology)
        vect.Vect_open_old2(map, self.layer, "", "-1")
        # Get number of point features (1) in the layer
        n_lines = vect.Vect_get_num_primitives(map, 1)
        # Create new line and categories structures
        line = vect.Vect_new_line_struct()
        cats = vect.Vect_new_cats_struct()
        # Make an empty list to store all feature coordinates in
        coordsdict = {}
        # Iterate through all features and write their coordinates to the list
        for i in range(1, n_lines + 1):
            # Read next line from Map_info()
            vect.Vect_read_next_line(map, line, cats, 1)
            # Get line structure values
            x = line.contents.x[0]
            y = line.contents.y[0]
            # Create a new tuple of these coordinates and with their cat id (they do coincide with this iteration integer "i", so could also write cat = cats.contents.cat[0] and use "cat" instead "i") and append this to the general layer coordinate list.
            coordsdict[i] = (x,y)
        # Do some cleanup
        vect.Vect_destroy_line_struct(line)
        vect.Vect_destroy_cats_struct(cats)
        vect.Vect_close(map)
        # Return coordinate dictionary
        return coordsdict

    def oneCoord(self):
        """ Get the centerpoint coordinate """
        return str(self.coordsdict[self.centerpoint][0]) + "," + str(self.coordsdict[self.centerpoint][1])

if __name__ == "__main__":
    options, flags = grass.parser()
    main()
