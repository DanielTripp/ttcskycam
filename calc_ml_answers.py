#!/usr/bin/env python
#!/usr/bin/env PYTHONOPTIMIZE=on python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random, dateutil
from collections import defaultdict
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph
from misc import *
import geom
import numpy as np

def add_time_zone(timestamp_):
	# We assume that timestamp_ has no time zone and represents a time in the local time zone. 
	dt = datetime.datetime.strptime(timestamp_, '%Y-%m-%d %H:%M:%S')
	dt = dt.replace(tzinfo=dateutil.tz.tzlocal())
	r = dt.strftime('%Y-%m-%d %H:%M:%S %z')
	return r

if __name__ == '__main__':

	direction = 0 
	datazoom = 3
	report_time = 1611938700000L
	report_json_str = db.get_report('locations', 'keele', direction, datazoom, report_time)
	report_obj = json.loads(report_json_str)
	#print json.dumps(report_obj, indent=2, sort_keys=True)
	vid_to_timestamp_to_latlon = defaultdict(dict)
	for report_timeslice in report_obj:
		timestamp = add_time_zone(report_timeslice[0])
		vinfos_for_timeslice = report_timeslice[1:]
		for vinfo in vinfos_for_timeslice:
			vid = vinfo['vehicle_id']
			lat = vinfo['lat']
			lon = vinfo['lon']
			vid_to_timestamp_to_latlon[vid][timestamp] = (lat, lon) 
	
	#pprint.pprint(dict(vid_to_timestamp_to_latlon), indent=2, width=150)

	for vid, timestamp_to_latlon in vid_to_timestamp_to_latlon.iteritems():
		#print vid
		for timestamp, latlon in iteritemssorted(timestamp_to_latlon):
			pass # print timestamp, latlon 
		break

	streets_sg = streets.get_snapgraph()
	if 0:
		print len(streets_sg.plinename2pts)
		max_num_pts = 0
		for plinename, pts in streets_sg.plinename2pts.iteritems():
			max_num_pts = max(max_num_pts, len(pts))
		print max_num_pts
		sys.exit(0)
	start_latlon = geom.LatLng(43.667224383419686, -79.46532130569948)
	dest_latlon =   geom.LatLng(43.65539969538242, -79.46032559867878)
	dists_n_pathsteps = streets_sg.find_paths(start_latlon, 'm', dest_latlon, 'm')
	dist, pathsteps = dists_n_pathsteps[0]
	path = snapgraph.Path([pathsteps], streets_sg)
	edges = path.get_edges()
	for edge in edges:
		print edge.strlong(streets_sg)
	#print path 
	#pprint.pprint(paths, indent=2, width=150)




