#%module
#% description: Multiple Least-cost path creation
#% keywords: lcp
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

import os, sys, string
#import sys
#import string
import grass.script as grass
import grass.lib.vector as vect
#from ctypes import *
import grass.lib.gis as gis


def main():
    # User inputs
    friction = options['friction']
    points = options['points']
    output = options['output']
    radius = int(options['radius'])
    no_close_points = int(options['closepoints'])
    netout = options['netout']
    
    # Get coordinates of input point layer and number of features in the layer
    coordinates, n_feats = pointCoords(points)
    distdict = pointDistances(coordinates, n_feats)
    
    
    # Create temporary filenames in a hope they will be unique
    one_point = "tmp_onepoint_" + str(os.getpid())
    point_radius = "tmp_pointradius_" + str(os.getpid())
    point_radius2 = "tmp_pointradius_" + str(os.getpid()) + "2"
    buffermap = "tmp_buffer_" + str(os.getpid())
    costmap = "tmp_cost_" + str(os.getpid())
    lcpmap = "tmp_lcp_" + str(os.getpid())
    lcptemp = "tmp_lcptemp_" + str(os.getpid())
    cl_points = "tmp_clpoints"

    mapcalcproc = grass.Popen("")
    # Main loop to create a new cost surface + lcp for each point
    for feat in range(1, n_feats +1, 2):

        # Extract point 1
        extract1 = grass.start_command('v.extract', input=points, output=one_point, cats=feat, overwrite=True)
        # Extract point 2
        extract2 = grass.start_command('v.extract', input=points, output=one_point+"2", cats=feat, overwrite=True)
        
        # Meanwhile, get closest points for point 1
        list_closepoints = closestPoints(feat, distdict, no_close_points)
        # Get closest points for point 2
        list_closepoints2 = closestPoints(feat+1, distdict, no_close_points)
        
        # Wait for the extractions to finish
        extract1.wait()
        extract2.wait()
        
        # Perform point radius search
        if radius > 0:
            #Create a buffer around point
            buffproc1 = grass.start_command('v.buffer', input = one_point, output = buffermap, distance = radius, overwrite=True)
            buffproc2 = grass.start_command('v.buffer', input = one_point+"2", output = buffermap+"2", distance = radius, overwrite=True)
            # Make a new layer with points that are within the buffer
            buffproc1.wait()
            buffselproc1 = grass.start_command('v.select', ainput = points, binput = buffermap, output = point_radius, operator = 'within', atype = 'point', overwrite = True)
            buffproc2.wait()
            buffselproc2 = grass.start_command('v.select', ainput = points, binput = buffermap+"2", output = point_radius2, operator = 'within', atype = 'point', overwrite = True)
            buffselproc1.wait()
            buffselproc2.wait()
        elif radius == 0:
            # If point radius is set as 0, use the whole point layer and don't perform pointSearchRadius()
            point_radius = points
            point_radius2 = point_radius
        else:
            # For invalid radius value delete the temporary map and terminate operation
            # !!! SHOULD MOVE THIS TO THE VERY BEGINNING
            grass.run_command('g.remove', vect = one_point + "," + one_point+"2")
            grass.fatal("Invalid radius chosen. Enter 0 for unlimited or positive number for search radius in map units")
        
        
        # Perform closest points search
        if no_close_points > 0:
            # If positive number is entered, extract new layers
            extract1 = grass.start_command('v.extract', input=point_radius, output = cl_points, cats=list_closepoints, overwrite=True)
            extract2 = grass.start_command('v.extract', input=point_radius2, output = cl_points+"2", cats=list_closepoints2, overwrite=True)
            # Call MakeLCP() function to create least cost paths
            extract1.wait()
            lcpproc1 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap, start_points=one_point)
            extract2.wait()
            lcpproc2 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap+"2", start_points=one_point+"2")
            lcpproc1.wait()
            grass.run_command('r.drain', overwrite=True, input=costmap, output=lcpmap, start_points=cl_points)
            lcpproc2.wait()
            grass.run_command('r.drain', overwrite=True, input=costmap+"2", output=lcpmap+"2", start_points=cl_points+"2")            
        else:
            # Create cost surface for with 1 point input
            lcpproc1 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap, start_points=one_point)
            lcpproc2 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap+"2", start_points=one_point+"2")
            # Least-cost paths from every other point to the current point
            lcpproc1.wait()
            grass.run_command('r.drain', overwrite=True, input=costmap, output=lcpmap, start_points=point_radius)
            
            if netout:
                costDistances(costmap, point_radius)
            
            lcpproc2.wait()
            grass.run_command('r.drain', overwrite=True, input=costmap+"2", output=lcpmap+"2", start_points=point_radius2)
    
        # Because point_radius might be equal to points and thus the latter get deleted afterwards, here's a solution to make them different again.
        point_radius = "tmp_pointradius_" + str(os.getpid())
        point_radius2 = "tmp_pointradius_" + str(os.getpid()) + "2"
        
        # If the point is the first feature in a layer, create a new layer from that drain map. For every other points, reuse the previous map and add new path to it.
        if feat == 1:
            grass.mapcalc("$outmap = if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", outmap = output, tempmap = lcpmap, tempmap2 = lcpmap+"2", overwrite=True)
        else:
            mapcalcproc.wait()
            # Rename the cumulative lcp map from previous iteration so that mapcalc can use it (x=x+y doesn't work with mapcalc)
            grass.run_command('g.rename', rast = output + ',' + lcptemp, overwrite=True)
            # output = PreviousLCP + CurrentLCP
            mapcalcproc = grass.mapcalc_start("$outmap = $inmap + if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", inmap = lcptemp, outmap = output, tempmap = lcpmap, tempmap2 = lcpmap+"2")
    
    mapcalcproc.wait()
    # Make 0 values into NULLs
    grass.run_command('r.null', map = output, setnull = "0")
    
    # Delete temporary maps
    grass.run_command('g.remove', rast = costmap + "," + costmap + "2," + lcpmap + "," + lcpmap + "2," + lcptemp, vect = one_point + "," + one_point + "2," + buffermap + "," + buffermap + "2," + point_radius + point_radius2)

def costDistances(costmap, point_radius):
    # Need number of features + their coords
    lcpmap = "tmp_lcp_" + str(os.getpid())
    coordlist, n_feats = pointCoords(point_radius)
    for feat in coordlist:
        x, y = coordlist[feat]
        startpoints = str(x) + "," + str(y)
        grass.run_command('r.drain', overwrite=True, flags = 'a', input=costmap, output=lcpmap, start_coordinates=startpoints)
        print feat

def closestPoints(pointnumber, distdict, totalnumber):
    # Scan the dictionary to find closest points and write the point cats to a list
    i = 0
    closestpoints = ""
    for key, value in sorted(distdict[pointnumber].iteritems(), key=lambda (k,v): (v,k)):
        if closestpoints == "":
            closestpoints = str(key)
        else:
            closestpoints = closestpoints + "," + str(key)
        i = i + 1
        if i == totalnumber:
            return closestpoints

def pointDistances(coordinates, pointnumber):
    # The following writes the distances from points to each other into a two-level dictionary, such as {1: {2: 100, 3: 200, 4: 300, 5: 400}, 2: {1: 100 3: 500 ... etc.
    distlist = {}
    for feat in range(1, pointnumber + 1):
        x1, y1 = coordinates[feat]
        distlist[feat] = {}
        for otherfeat in range(1, pointnumber + 1):
            if otherfeat != feat:
                x2, y2 = coordinates[otherfeat]
                dist = vect.Vect_points_distance(x1,y1,0,x2,y2,0,0)
                distlist[feat][otherfeat] = dist
    return distlist

def pointCoords(layername):
    # Create a new Map_info() object
    map = vect.pointer(vect.Map_info())
    # Load the vector map to Map_info() object. Level should be 2 (with topology)
    vect.Vect_open_old2(map, layername, "", "-1")
    # Get number of point features (1) in the layer
    nlines = vect.Vect_get_num_primitives(map, 1)
    # Create new line and categories structures
    line = vect.Vect_new_line_struct()
    cats = vect.Vect_new_cats_struct()
    # Make an empty list to store all feature coordinates in
    coordlist = {}
    # Iterate through all features and write their coordinates to the list
    for i in range(1, nlines + 1):
        # Read next line from Map_info()
        vect.Vect_read_next_line(map, line, cats, 1)
        # Get line structure values
        x = line.contents.x[0]
        y = line.contents.y[0]
        # Create a new tuple of these coordinates and with their cat id (they do coincide with this iteration integer "i", so could also write cat = cats.contents.cat[0] and use "cat" instead "i") and append this to the general layer coordinate list.
        coordlist[i] = (x,y)
        #linecoords =  {i: x, y}
        #coordlist.append(linecoords)
    # Do some cleanup
    vect.Vect_destroy_line_struct(line)
    vect.Vect_destroy_cats_struct(cats)
    vect.Vect_close(map)
    # Return coordinate list and number of features in the layer as a tuple
    return coordlist, nlines

if __name__ == "__main__":
    options, flags = grass.parser()
    main()


