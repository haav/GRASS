#!/usr/bin/env python
############################################################################
#
# MODULE:       r.lcp
# AUTHOR(S):    Allar Haav
#
# PURPOSE:      A module for creating least cost paths between points
# COPYRIGHT:    (C) 2013 Allar Haav
#
#       This program is free software under the GNU General Public
#       License (>=v2). Read the file COPYING that comes with GRASS
#       for details.
#
#############################################################################

#%module
#% description: Least-cost path creation between points
#% keywords: lcp
#% keywords: cost
#% keywords: raster
#%end

#%option
#% key: friction
#% type: string
#% gisprompt: old,raster
#% description: Input friction map 
#% required: yes
#%end

#%option
#% key: points
#% type: string
#% gisprompt: old,vector
#% description: Input point layer
#% required: yes
#%end

#%option
#% key: radius
#% type: integer
#% description: Point search radius. 0 for unlimited
#% required: yes
#% answer: 0
#%end

#%option
#% key: nearpoints
#% type: integer
#% description: Number of nearest points to be used. 0 for unlimited
#% required: yes
#% answer: 0
#%end

#%option
#% key: rastout
#% type: string
#% gisprompt: new,raster
#% description: Output least cost path raster layer 
#% required: no
#%end

#%option
#% key: vectout
#% type: string
#% gisprompt: new,vector
#% description: Output vector least cost path layer
#% required: no
#%end

#%flag
#% key: c
#% description: Calculate total cost values for each path and add them to output vector attribute table (very slow)
#%end

#%flag
#% key: k
#% description: Use knight's move in cost surface calculation (only a bit slower, but more accurate paths)
#%end

import os, sys
import atexit
import grass.script as grass
import grass.lib.vector as vect
import grass.lib.gis as gis
from operator import itemgetter

# Create an empty global temporary layer list for cleanup purposes
tmp_rlayers = list()
tmp_vlayers = list()

def main():
    # User inputs
    friction = options['friction']              # Input friction raster
    inpoints = options['points']                # Input point layer
    rastout = options['rastout']                # Output least cost path raster
    radius = int(options['radius'])             # Point search radius
    n_closepoints = int(options['nearpoints'])  # Number of closest points
    vectout = options['vectout']                # Vector layer output
    knight = "k" if flags['k'] else ""          # Knight's move flag
    costatt = "e" if flags['c'] else ""         # Calculate total cost values for paths and add them to attribute table
    
    # Check no vector or raster output is chosen, raise an error
    if (not vectout) and (not rastout):
        grass.message("No output chosen!")
        sys.exit()
        
    # Check overwrite settings
    # If output raster file exists, but overwrite option isn't selected
    if not grass.overwrite():
        if grass.find_file(rastout)['name']:
            grass.message(_("Output raster map <%s> already exists") % rastout)
            sys.exit()
            
    # If output vector file exists, but overwrite option isn't selected
    if not grass.overwrite():
        if grass.find_file(vectout, element = 'vector')['name']:
            grass.message(_("Output vector map <%s> already exists") % vectout)
            sys.exit()
    
    # If overwrite is chosen, remove the previous layers before any action (to lessen the probability of some random errors)
    if grass.overwrite():
        grass.run_command("g.remove", rast = rastout, vect = vectout, quiet = True)
        
    # Get a region resolution to be used in cost attribute calculation, because the default will be in map units
    if vectout and (costatt == "e"): 
        # Get raster calculation region information
        regiondata = grass.read_command("g.region", flags = 'p')
        regvalues = grass.parse_key_val(regiondata, sep= ':')
        # Assign variables for necessary region info bits
        nsres = float(regvalues['nsres'])
        ewres = float(regvalues['ewres'])
        regionres = (nsres + ewres) / 2.0
        rescoefficient = regionres
       
    # Get process id (pid) and create temporary layer names which are also added to tmp_rlayers list
    pid = os.getpid()                           # Process ID, used for getting unique temporary filenames
    costmap1 = "tmp_cost_%d" % pid              # Cost surface for point 1
    tmp_rlayers.append(costmap1)
    costmap2 = "tmp_cost_%d_%i" % (pid, 2)      # Cost surface from point 2 (parallel process)
    tmp_rlayers.append(costmap2)
    costdir1 = "tmp_costdir_%d" % pid           # Temporary cost direction raster 1
    tmp_rlayers.append(costdir1)
    costdir2 = "tmp_costdir_%d_%i" % (pid, 2)   # Temporary cost direction raster 2
    tmp_rlayers.append(costdir2)
    lcpmap1 = "tmp_lcp_%d" % pid                # Least cost path map from costmap1
    tmp_rlayers.append(lcpmap1)
    lcpmap2 = "tmp_lcp_%d_%i" % (pid, 2)        # Least cost path map from costmap2 (parallel process)
    tmp_rlayers.append(lcpmap2)
    lcptemp = "tmp_lcptemp_%d" % pid            # Temporary file for mapcalc
    tmp_rlayers.append(lcptemp)
    region = "tmp_region_%d" % pid              # Temporary vector layer of computational region
    tmp_vlayers.append(region)
    points = "tmp_points_%d" % pid              # Temporary point layer which holds points only inside the region
    tmp_vlayers.append(points)
    if vectout: # if vector output is needed, create the temporary vectorlayers too
        vectdrain1 = "tmp_vectdrain_%d" % pid
        tmp_vlayers.append(vectdrain1)
        vectdrain2 = "tmp_vectdrain2_%d" % pid
        tmp_vlayers.append(vectdrain2)
    
    # Make sure input data points are inside raster computational region: create a region polygon and select points that are inside it
    grass.run_command('v.in.region', overwrite = True, output = region)
    grass.run_command('v.select', overwrite = True, flags = "tc", ainput = inpoints, atype = 'point', binput = region, btype = 'area', output = points , operator = 'within')
    
    # Create a new PointLayerInfo class instance using input point layer and get the categories list as well as total feature count of the layer
    pointlayer = PointLayerInfo(points)
    points_cats = pointlayer.featcats           # A list() of layer feature categories
    points_featcount = pointlayer.featcount     # integer of feature count in point layer
    points_coordsdict = pointlayer.coordsdict   # dict() of point coordinates as tuple (x,y)
    
    # Create an empty dictionaries for storing cost distances between points
    costdict1 = dict()
    costdict2 = dict()
    
    # Create the first mapcalc process, so that it can be checked and stopped in the loop without using more complicated ways
    mapcalc = grass.Popen("", shell=True)
    lcp1 = grass.Popen("", shell=True)
    lcp2 = grass.Popen("", shell=True)
    
    # The main loop for least cost path creation. For each point a cost surface is created, least cost paths created and then added to the general output file. Loop uses a range which has as many items as there are points in the input point layer. To make use of parallel processing, the step is 2, although the "item" is always the first of the selected pair.
    for item in range(0,points_featcount,2):
        
        # Get category number of the point from the point_cats list
        cat1 = points_cats[item]
        
        # Set p2 (i.e. using second or parallel process) to be False by default and make it True if there are enough points left to do so. In that case set it to true and also get the category number of the point from the point_cats list
        p2 = False
        if item+1 < points_featcount:
            p2 = True
            cat2 = points_cats[item+1]
        
        # Create a new PointLayerInfo object from input point layer with centerpoint (from which distances area measured in the class) feature as currently selected point cat
        point1 = PointLayerInfo(points, cat1)
        if p2:  # The same for p2 if needed
            point2 = PointLayerInfo(points, cat2)
        
        # begin cost surface process with the start coordinate of currently selected point. Do the same for second process
        costsurf1 = grass.start_command('r.cost', flags=knight, overwrite=True, input=friction, output=costmap1, outdir=costdir1, start_coordinates=point1.centercoord())
        if p2:
            costsurf2 = grass.start_command('r.cost', flags=knight, overwrite=True, input=friction, output=costmap2, outdir=costdir2, start_coordinates=point2.centercoord())
        
        # Create the drainlist (list of feature coordinates where lcp from current point is made to) depending on whether radius and/or n_closepoints are used. Drainlist point coordinates will be used for r.drain. See PointLayerInfo class below for explanation of the process.
        if radius and n_closepoints:    # If radius and n_closepoints are used
            drainlist1 = point1.near_points_in_radius(n_closepoints, radius)
            if p2:
                drainlist2 = point2.near_points_in_radius(n_closepoints, radius)
        elif radius:                    # If radius is used
            drainlist1 = point1.points_in_radius(radius)
            if p2:
                drainlist2 = point2.points_in_radius(radius)
        elif n_closepoints:             # If n_closepoints is used
            drainlist1 = point1.near_points(n_closepoints)
            if p2:
                drainlist2 = point2.near_points(n_closepoints)
        else:                           # If neither radius or n_closepoints are used
            drainlist1 = point1.cats_without_centerpoint()
            if p2:
                drainlist2 = point2.cats_without_centerpoint()
            
        # Do the least cost path calculation procedures
        drain_coords1 = ""   # An empty string that will be populated with point coordinates which in turn will be used for r.drain start coordinates
        for drainpoint in drainlist1:    # Iterate through all points in drainlist
            drain_x, drain_y = point1.coordsdict[drainpoint]    # variables are assigned coordinate values from the coordinate dictionary
            drain_coords1 = drain_coords1 + str(drain_x) + "," + str(drain_y) + ","     # Add those coordinates to the string that is usable by r.drain
            
        if p2:  # The same thing for second process, see previous section for comments
            drain_coords2 = ""
            for drainpoint in drainlist2:
                drain_x, drain_y = point2.coordsdict[drainpoint]
                drain_coords2 = drain_coords2 + str(drain_x) + "," + str(drain_y) + ","
        
        # Wait for the previous processes to finish their processing
        costsurf1.wait()   
        costsurf2.wait()
        mapcalc.wait()
        
        # If vector output is needed, do the r.drain for each point in the drainlist separately to get the cost values
        if vectout:
            if costatt == "e":
                for drainpoint in drainlist1:   # Each point cat in the drainlist is being iterated
                    drain_x, drain_y = point1.coordsdict[drainpoint]        # Currently selected point's coordinates
                    drain_onecoord = str(str(drain_x) + "," + str(drain_y)) # The coordinate to be used in r.drain on the next line
                    grass.run_command('r.drain', overwrite=True, flags="ad", input=costmap1, indir=costdir1, output = lcpmap1, start_coordinates = drain_onecoord)
                    # Get raster max value (=total cost value for one path) and store it in dictionary with point cat being its key
                    rastinfo = grass.raster_info(lcpmap1)
                    costdict1[drainpoint] = rescoefficient * rastinfo['min']
                    
                if p2:  # Same procedure as in the previous section for parallel process
                    for drainpoint in drainlist2:
                        drain_x, drain_y = point2.coordsdict[drainpoint]
                        drain_onecoord = str(str(drain_x) + "," + str(drain_y))
                        grass.run_command('r.drain', overwrite=True, flags="ad", input=costmap2, indir=costdir2, output = lcpmap2, start_coordinates = drain_onecoord)
                        rastinfo = grass.raster_info(lcpmap2)
                        costdict2[drainpoint] = rescoefficient * rastinfo['min']
            
            # Finally create the vector layer with all paths from the current point. It also (whether we want it or not) creates a raster output
            if len(drainlist1) > 0:
                lcp1 = grass.start_command('r.drain', overwrite=True, flags="d", input=costmap1, indir=costdir1, output = lcpmap1, vector_output = vectdrain1,start_coordinates=drain_coords1)
            if p2 and (len(drainlist2) > 0):
                lcp2 = grass.start_command('r.drain', overwrite=True, flags="d", input=costmap2, indir=costdir2, output = lcpmap2, vector_output = vectdrain2,start_coordinates=drain_coords2)
        
        # If raster output is needed, but path maps have not been made yet (i.e. vectout must be False) then make those
        if not vectout and (len(drainlist1) > 0):
            lcp1 = grass.start_command('r.drain', overwrite=True, flags="d", input=costmap1, indir=costdir1, output = lcpmap1, start_coordinates=drain_coords1)
            if p2 and (len(drainlist2) > 0):
                lcp2 = grass.start_command('r.drain', overwrite=True, flags="d", input=costmap2, indir=costdir2, output = lcpmap2, start_coordinates=drain_coords2)

        # Wait for the lcp processes to finish
        lcp1.wait()
        lcp2.wait()
        
        # If raster output is needed, do the mapcalc stuff: merge the path rasters
        if rastout:
            if len(drainlist1) == 0:
                lcpmap1 = 0
            if len(drainlist2) == 0:
                lcpmap2 = 0
            if cat1 == points_cats[0]:   # If it's the very first iteration
                if p2:  # Technically this should not be False in any situation, but let it be here for additional safety
                    # Add lcpmap1 and lcpmap2 together
                    mapcalc = grass.mapcalc_start("$outmap = if(isnull($tempmap1),0,1) + if(isnull($tempmap2),0,1)", outmap = rastout, tempmap1 = lcpmap1, tempmap2 = lcpmap2, overwrite=True)
                else:   # Just in case
                    mapcalc = grass.mapcalc_start("$outmap = if(isnull($tempmap1),0,1)", outmap = rastout, tempmap1 = lcpmap1, overwrite=True)
            else:
                # Rename the cumulative lcp map from previous iteration so that mapcalc can use it (x=x+y logic doesn't work with mapcalc)
                grass.run_command('g.rename', rast = rastout + ',' + lcptemp, overwrite=True)
                # rastout = Previous LCP + Current LCP
                if p2:
                    mapcalc = grass.mapcalc_start("$outmap = $inmap + if(isnull($tempmap1),0,1) + if(isnull($tempmap2),0,1)", inmap = lcptemp, outmap = rastout, tempmap1 = lcpmap1, tempmap2 = lcpmap2)
                else:
                    mapcalc = grass.mapcalc_start("$outmap = $inmap + if(isnull($tempmap1),0,1)", inmap = lcptemp, outmap = rastout, tempmap1 = lcpmap1)
        
        # If vector output is needed, do all necessary things like merging the vectors and getting values for attribute table (if specified)
        if vectout:
            if costatt == "e":  # Only if cost attributes are needed
                if len(drainlist1) > 0:
                    # Process 1
                    # Add attribute table to the vector path layer
                    grass.run_command('v.db.addtable', map = vectdrain1)
                    # Get path Euclidean distances and add them to the new column in attribute table. Also add the current point cat to the attribute "from_point"
                    grass.run_command('v.db.addcolumn', map = vectdrain1, columns = "length double precision, from_point int, to_point int, cost double precision")
                    grass.run_command('v.to.db', map = vectdrain1, type = "line", option = "length", columns = "length")
                    grass.run_command('v.db.update', map = vectdrain1, column = "from_point", value = str(cat1))
                
                # Same as previous section but for process 2
                if p2 and (len(drainlist2) > 0):
                    grass.run_command('v.db.addtable', map = vectdrain2)
                    grass.run_command('v.db.addcolumn', map = vectdrain2, columns = "length double precision, from_point int, to_point int, cost double precision")
                    grass.run_command('v.to.db', map = vectdrain2, type = "line", option = "length", columns = "length")
                    grass.run_command('v.db.update', map = vectdrain2, column = "from_point", value = str(cat2))
                
                
                # A loop to update the path attribute values to the attribute table
                if len(drainlist1) > 0:
                    drainseq = 1    # This is just a helper counter because for newly created vector layer the cats start from 1 and just go successively, so no need to introduce any unnecessary catlist
                    for drainpoint in drainlist1:
                        # Update to_point column with values from drainlist
                        grass.run_command('v.db.update', map = vectdrain1, column = "to_point", value = str(drainpoint), where = "cat = " + str(drainseq))
                        # Update the cost column using costdict created earlier
                        grass.run_command('v.db.update', map = vectdrain1, column = "cost", value = costdict1[drainpoint], where = "cat = " + str(drainseq))
                        drainseq += 1
                    
                # The same for process 2
                if p2 and (len(drainlist2) > 0):
                    drainseq = 1    # Reset the counter
                    for drainpoint in drainlist2:
                        grass.run_command('v.db.update', map = vectdrain2, column = "to_point", value = str(drainpoint), where = "cat = " + str(drainseq))
                        grass.run_command('v.db.update', map = vectdrain2, column = "cost", value = costdict2[drainpoint], where = "cat = " + str(drainseq))
                        drainseq += 1
                
            # Patch vector layers
            # For both processes, first make sure that drainlists for current iteration are not empty. If they are not (i.e. the drainlist for current iteration > 0), then drain vectors will be used in v.patch, otherwise empty strings will be used in patching. This is to make sure that vectors from previous iterations are not used.
            if len(drainlist1) > 0:
                vect1 = vectdrain1
            else:
                vect1 = ""
            if len(drainlist2) > 0:
                vect2 = vectdrain2
            else:
                vect2 = ""
            
            # If BOTH drain processes resulted in vectors, create a comma character to be used in v.patch (input parameter must be a string type and layers should be separated by comma)
            if (len(drainlist1) > 0) and (len(drainlist2) > 0):
                comma = ","
            else:
                comma = ""
            
            # Finally do the patching
            if cat1 == points_cats[0]:  # If it's the very first iteration
                if p2:  # If iteration has 2 points
                    grass.run_command('v.patch', overwrite = True, flags=costatt, input = vect1 + comma + vect2, output = vectout)
                else:   # Technically this should never be called (because not having 2 points per iteration can happen only for the very last iteration), but I'll leave it here just in case or for future reference
                    grass.run_command('g.rename', overwrite = True, vect = vect1 + "," + vectout)
            else:
                if grass.find_file(vectout, element='vector')['name']:  # Check whether vectout exists or not (this can happen when the first iteration did not produce any vectors, i.e. search radius was too small). If it does exist, add "a" (append) flag to v.patch, otherwise omit it.
                    append = costatt + "a"
                else:
                    append = costatt
                # Choose between two patching scenarios: 1 or 2 process versions.
                if p2:
                    grass.run_command('v.patch', overwrite = True, flags=append, input = vect1 + comma + vect2, output = vectout)
                else:
                    grass.run_command('v.patch', overwrite = True, flags=append, input = vect1, output = vectout)
    
    
    # Make 0 values of raster into NULLs
    if rastout:
        mapcalc.wait()
        nullproc = grass.run_command('r.null', map = rastout, setnull = "0")

    grass.message("All done!")

def cleanup(): # Cleaning service
   for layer in tmp_rlayers:
       grass.run_command("g.remove", rast = layer, quiet = True)
   for layer in tmp_vlayers:
       grass.run_command("g.remove", vect = layer, quiet = True)
    
    
class PointLayerInfo:
    """ PointLayerInfo object, based on an existing vector point layer and has optional centerpoint """
    def __init__(self, layername, centerpoint=False, centercoord=""):   # layername=vector point layer; centerpoint = point cat that is used to measure search radius and closest points
        self.layer = layername
        self.featcount = self.featcount()       # Do the feature count in init stage as this is to be used more than once (integer)
        self.coordsdict = self.getcoords()      # Get layer coordinates in the init stage as this is to be used more than once.
        self.featcats = self.coordsdict.keys()  # Make a list of feature categories using existing coordsdict that has them as keys. Example: [1, 3, 4, 5, 6, 7]
        
        # If centerpoint is specified, get other stuff too
        if centerpoint:
            self.centerpoint = centerpoint      # Centerpoint feature category id (integer)
            self.distances = self.distances()   # Get the distance dict() in init stage as this is to be used more than once
        
    def featcount(self):
        """ Method returning the number of features in the layer """
        # Create a new Map_info() object
        map = vect.pointer(vect.Map_info())
        # Load the vector map to Map_info() object. Level should be 2 (with topology)
        vect.Vect_open_old2(map, self.layer, "", "-1")
        # Get number of point features (1) in the layer
        n_feats = vect.Vect_get_num_primitives(map, 1)
        # Close the Map_info() object
        vect.Vect_close(map)
        # Return number of features in the layer (integer)
        return n_feats

    def getcoords(self):
        """ Method creating a dict() of point coordinates: {a:(xa,ya), b:(xb,yb)...} """
        # Create a new Map_info() object
        map = vect.pointer(vect.Map_info())
        # Load the vector map to Map_info() object. Level should be 2 (with topology)
        vect.Vect_open_old2(map, self.layer, "", "-1")
        # Get number of point features (1) in the layer
        n_lines = vect.Vect_get_num_primitives(map, 1)
        # Create new line and categories structures
        line = vect.Vect_new_line_struct()
        cats = vect.Vect_new_cats_struct()
        # Make an empty list to store all feature cats and their coordinates in
        coordsdict = {}
        # Iterate through all features and write their coordinates to the list
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
        # Return coordinate dictionary. Example: {1: (635185.6745587245, 6434401.869609355), 3: (634763.0860512792, 6437526.1793751), 4: (636855.7953351085, 6435785.045250954), 5: (636705.1202666728, 6432286.035328391), 6: (633607.9105266054, 6432286.035328391), 7: (632762.4559759387, 6435655.297275356)}
        return coordsdict

    def distances(self):
        """ Method that creates a list with euclidean distances from the centerpoint """
        # Get feature count
        n_feats = self.featcount
        # Create a new list to store distances (why list not dict?)
        distlist = []
        # Get centerpoint coordinates using coordsdict
        x1, y1 = self.coordsdict[self.centerpoint]
        for cat in self.featcats:   # Iterate through features (using their cats) to measure distance between them and centerpoint
            if cat != self.centerpoint:
                x2, y2 = self.coordsdict[cat]
                dist = vect.Vect_points_distance(x1,y1,0,x2,y2,0,0)
                distlist.append((cat, dist))
        # Return the distance list that is sorted by distance. Example: [(4, 2168.519832333262), (5, 2604.8934649818007), (6, 2639.3359099498907), (7, 2728.198895582067), (3, 3152.7595149256367)]
        return sorted(distlist, key=itemgetter(1))

    def near_points(self, n_points):
        """ Returns a n_points number of point cats that are nearest to the centerpoint in a list form """
        # If n_points is greater than the number of features in a list, SHUT.DOWN.EVERYTHING.
        if n_points >= self.featcount or n_points <= 0:
            grass.fatal("The nearest point value must be a positive number that is smaller than total feature count in a layer")
        # Iterate through the distance list and write the n_points of nearest point cats into the list
        near_list = []
        for i in range(n_points):
            cat = self.distances[i][0]
            near_list.append(cat)
        # Return n_points nearest points list. Example for n_points value 3: [4, 5, 6]
        return near_list

    def points_in_radius(self, radius):
        """ Returns a list of point cats that are inside the search radius """
        radiuslist = []
        for item in self.distances:         # Iterate through items in distance list
            if item[1] <= radius:           # element 1 in each distance list item is distance value
                radiuslist.append(item[0])  # element 0 in each distance list item is feature cat
        # Return the list of feature cats that are of equal or smaller distance away from the centerpoint. Example for 2630: [4, 5]
        return radiuslist
        
    def near_points_in_radius(self, n_points, radius):
        """ Returns a list of max n_points of feature cats that are in search radius """
        near_points = self.near_points(n_points)
        points_in_radius = self.points_in_radius(radius)
        if len(near_points) >= len(points_in_radius):
            return points_in_radius
        else:
            return near_points
            
    def centercoord(self):
        """ Get the centerpoint coordinate and return this as a string """
        x, y = self.coordsdict[self.centerpoint]
        return str(x) + "," + str(y)
        
    def cats_without_centerpoint(self):
        """ Return a list of feature cats without centerpoint cat """
        catslist = list(self.featcats)      # This copies the list instead of referencing it
        catslist.remove(self.centerpoint)   # Remove the centerpoint cat
        return catslist

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
