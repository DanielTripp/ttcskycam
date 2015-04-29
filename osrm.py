#!/usr/bin/env python

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

import sys, urllib, json
import geom
from misc import *

def get_path(latlngs_, log=False):
	assert all(isinstance(e, geom.LatLng) for e in latlngs_)
	url_pts_part = '&'.join(['loc=%f,%f' % (pt.lat, pt.lng) for pt in latlngs_])
	url = 'http://localhost:5000/viaroute?' + url_pts_part
	response = json.load(urllib.urlopen(url))
	if log:
		printerr('OSRM viaroute response: "%s"' % response)
	encoded_route_polyline = response['route_geometry']
	return geom.decode_line(encoded_route_polyline)

if __name__ == '__main__':

	latlng_strs = sys.argv[1:]
	latlngs = [geom.LatLng([float(floatstr) for floatstr in pairstr.split(',')]) for pairstr in latlng_strs]
	print get_path(latlngs, log=True)


