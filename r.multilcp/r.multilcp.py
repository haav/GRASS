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


def main():
    # User inputs
    friction = options['friction']  # Input friction raster
    points = options['points']      # Input point layer
    output = options['output']      # Output least cost path raster
    radius = int(options['radius']) # Point search radius
    n_closepoints = int(options['closepoints'])   # Number of closest points
    netout = options['netout']      # Network output

    # Get process id (pid) and create temporary layer names
    # KAS TEHA EHK CLASS NENDEST NING KUSTUTAMINE OLEKS MEETOD?
    pid = os.getpid() # Process ID, used for making (more or less) unique temporary filenames
    onepoint1 = "tmp_onepoint_%d" % pid # Layer with one point extracted from main vector point file
    onepoint2 = "tmp_onepoint_%d_%i" % (pid, 2) # Layer with one point extracted from main vector point file; parallel process
    pointradius1 = "tmp_pointradius_%d" % pid  # Layer with points that are inside selected radius from onepoint1
    pointradius2 = "tmp_pointradius_%d_%i" % (pid, 2) # Layer with points that are inside selected radius from onepoint2; parallel process
    buffermap1 = "tmp_buffer_%d" % pid # Layer with buffer of selected radius around onepoint1
    buffermap2 = "tmp_buffer_%d_%i" % (pid, 2) # Layer with buffer of selected radius around onepoint2; parallel process
    costmap1 = "tmp_cost_%d" % pid # Cost surface from onepoint1
    costmap2 = "tmp_cost_%d_%i" % (pid, 2) # Cost surface from onepoint2; parallel process
    lcpmap1 = "tmp_lcp_%d" % pid # Least cost path map from costmap1
    lcpmap2 = "tmp_lcp_%d_%i" % (pid, 2) # Least cost path map from costmap2; parallel process
    closepoints1 = "tmp_clpoints_%d" % pid # Closest points (number specified by n_closepoints) from onepoint1
    closepoints2 = "tmp_clpoints_%d_%i" % (pid, 2) # Closest points (number specified by n_closepoints) from onepoint2; parallel process
    lcptemp = "tmp_lcptemp_%d" % pid # Temporary file for mapcalc
    
    # Create a a long string of all temporary layernames for easy deletion them later on
    # MOTLE KAS ON EHK ELEGANTSEM VIIS?
    tmpvars = onepoint1 + "," + onepoint2 + "," + pointradius1 + "," + pointradius2 + "," + buffermap1 + "," + buffermap2 + "," + costmap1 + "," + costmap2 + "," + lcpmap1 + "," + lcpmap2 + "," + closepoints1 + "," + closepoints2 + "," + lcptemp
    
    # Get coordinates of input point layer and also the total number of point features in the layer
    all_coords, n_feats = pointCoords(points)
    distdict = pointDistances(all_coords, n_feats)

    # Initiate new Popen() object for multiprocessing mapcalc
    mapcalcproc = grass.Popen("")

    # Main loop creating cost surface for each point, iterating over every two points as 2 points are processed simultaneously
    # PAREM JA TAPSEM SELGITUS EHK VAJA. LOOPI SISU VOIKS TRY ALLA PANNA JA EXCEPTIONISSE CLEANUP JA FATAL
    for feat in range(1, n_feats +1, 2):
        
        # Extract points 1 and 2
        extract1 = grass.start_command('v.extract', input=points, output=onepoint1, cats=feat, overwrite=True, quiet=True)
        extract2 = grass.start_command('v.extract', input=points, output=onepoint2, cats=feat, overwrite=True, quiet=True)
        # Meanwhile, get closest points for points 1 & 2
        list_closepoints1 = closestPoints(feat, distdict, n_closepoints)
        list_closepoints2 = closestPoints(feat+1, distdict, n_closepoints)
        # Wait for the extractions to finish
        extract1.wait()
        extract2.wait()

        # Perform point radius search
        if radius > 0:
            #Create buffers around points 1 and 2
            buffproc1 = grass.start_command('v.buffer', input = onepoint1, output = buffermap1, distance = radius, overwrite=True, quiet=True)
            buffproc2 = grass.start_command('v.buffer', input = onepoint2, output = buffermap2, distance = radius, overwrite=True, quiet=True)
            buffproc1.wait()
            # Make a new layer with points that are within the buffer
            buffproc1 = grass.start_command('v.select', ainput = points, binput = buffermap1, output = pointradius1, operator = 'within', atype = 'point', overwrite = True, quiet=True)
            buffproc2.wait()
            buffproc2 = grass.start_command('v.select', ainput = points, binput = buffermap2, output = pointradius2, operator = 'within', atype = 'point', overwrite = True, quiet=True)
            buffproc1.wait()
            buffproc2.wait()
        elif radius == 0:
            # KAS LEIDUB JALLEGI EHK MONI ELEGANTSEM VARIANT? VAHEST SAAB SELLE ARA JATTA
            # If point radius is set as 0, use the whole point layer
            pointradius1 = points
            pointradius2 = pointradius1
        else:
            # For invalid radius value delete the temporary map and terminate operation
            # SELLINE KONTROLL VOIKS KYLL PARIS ALGUSES OLLA
            cleanUp(tmpvars)
            grass.fatal("Invalid radius value. Enter 0 for unlimited or positive number for search radius in map units")

        # Perform closest points search
        # SIIN VOIKS MOELDA KUIDAS SEE SUHESTUB RAADIUSEGA - MIS JARJEKORRAS NEED TULEVAD JA KAS SEE PEAKS OLEMA VALIKULINE. SEE VOIB TAHENDADA SIINSE STRUKTUURI TOSIST MUUTUST. NT LCP TEGEMISE ASI VOIB JU PARIS OMAETTE FUNKTSIOON OLLA. LISAKS, JARGNEVA IF ELSE SYSTEEMI SAAB LAGUNDADA NING TEHA IF PUHUL VAID MUUTUJATE SAMASTAMINE NING KOGU COST JA LCP TEGEMINE OLEKS VAID YHE KASU ALL
        if n_closepoints > 0:
            # If positive number is entered, extract new layers
            # PANE TAHELE, ET SIIN ON INPUT POINTRADIUS
            extract1 = grass.start_command('v.extract', input=pointradius1, output = closepoints1, cats=list_closepoints1, overwrite=True, quiet=True)
            extract2 = grass.start_command('v.extract', input=pointradius2, output = closepoints2, cats=list_closepoints2, overwrite=True, quiet=True)
            # Create cost surfaces
            # RATSUKAIK VOIKS OLLA VALIKULINE (flags="k")
            lcpproc1 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap1, start_points=onepoint1)
            lcpproc2 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap2, start_points=onepoint2)
            # Wait until previous actions are finished, then proceed with r.drain (shortest path module)
            extract1.wait()
            extract2.wait()
            lcpproc1.wait()
            lcpproc1 = grass.start_command('r.drain', overwrite=True, input=costmap1, output=lcpmap1, start_points=closepoints1)
            lcpproc2.wait()
            lcpproc2 = grass.start_command('r.drain', overwrite=True, input=costmap2, output=lcpmap2, start_points=closepoints2)
            lcpproc1.wait()
            lcpproc2.wait()
        else:
            # Create cost surfaces for 2 points
            lcpproc1 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap1, start_points=onepoint1)
            lcpproc2 = grass.start_command('r.cost', flags="k", overwrite=True, input=friction, output=costmap2, start_points=onepoint2)
            # Least-cost paths from every other point to the current point
            lcpproc1.wait()
            lcpproc1 = grass.start_command('r.drain', overwrite=True, input=costmap1, output=lcpmap1, start_points=pointradius1)
            lcpproc2.wait()
            lcpproc2 = grass.start_command('r.drain', overwrite=True, input=costmap2, output=lcpmap2, start_points=pointradius2)
            lcpproc2.wait()

        # Because <pointradius1> or <pointradius2> might be equal to <points> (if no search radius is specified) and thus the latter get deleted afterwards, here's a solution to make them different again.
        # VAGA KOLE LAHENDUS, KINDLASTI ON MIDAGI PAREMAT VOIMALIK TEHA
        pointradius1 = "tmp_pointradius_%d" % pid
        pointradius2 = "tmp_pointradius_%d_%i" % (pid, 2)

        # If the point is the first feature in a layer, create a new layer from that drain map. For every other points, reuse the previous map and add new path to it.
        if feat == 1:
            grass.mapcalc("$outmap = if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", outmap = output, tempmap = lcpmap1, tempmap2 = lcpmap2, overwrite=True)
        else:
            # Wait for the mapcalc operation from previous iteration to finish
            mapcalcproc.wait()
            # Rename the cumulative lcp map from previous iteration so that mapcalc can use it (x=x+y doesn't work with mapcalc)
            grass.run_command('g.rename', rast = output + ',' + lcptemp, overwrite=True)
            # output = Previous LCP + Current LCP
            mapcalcproc = grass.mapcalc_start("$outmap = $inmap + if(isnull($tempmap),0,1) + if(isnull($tempmap2),0,1)", inmap = lcptemp, outmap = output, tempmap = lcpmap1, tempmap2 = lcpmap2)

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

def costDistances(costmap, point_radius):
    pass
    """
    # Need number of features + their coords
    lcpmap = "tmp_lcp_" + str(os.getpid())
    coordlist, n_feats = pointCoords(point_radius)
    for feat in coordlist:
        x, y = coordlist[feat]
        startpoints = str(x) + "," + str(y)
        grass.run_command('r.drain', overwrite=True, flags = 'a', input=costmap, output=lcpmap, start_coordinates=startpoints)
        grass.raster_info('elevation')print feat
    """

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
