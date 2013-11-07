#!/usr/bin/python2.6

import os, json
import geom, snapgraph, picklestore
from misc import *
from collections import Sequence
from itertools import *
from lru_cache import lru_cache
import shapefile

@picklestore.decorate
def get_polylines():
	street_fcode_descs = ['Access Road', 'Busway', 'Collector', 'Collector Ramp', 'Expressway', 'Expressway Ramp', 'Local', 'Major Arterial', 'Major Arterial Ramp', 'Minor Arterial', 'Minor Arterial Ramp', 'Pending', 'Other', 'Other Ramp']
	sf = shapefile.Reader('toronto_street_map/centreline_wgs84/CENTRELINE_WGS84')
	fields = [x for x in sf.fields if x[0] != 'DeletionFlag']
	idx_FCODE_DESC = [x[0] for x in fields].index('FCODE_DESC')
	idx_LF_NAME = [x[0] for x in fields].index('LF_NAME')
	polylines = []
	for shape, record in izip(sf.iterShapes(), sf.iterRecords()):
		if record[idx_FCODE_DESC] in street_fcode_descs:
			polyline = [geom.LatLng(pt[1], pt[0]) for pt in shape.points]
			polylines.append(polyline)
	return polylines

@picklestore.decorate
def get_snapgraph():
	return snapgraph.SnapGraph(get_polylines())

# This uses no search radius for the snap.  That is - it is unlimited, and will keep going until a line segment is found, 
# no matter how far away.  This is okay because we are confident that the Toronto map data that we're using is accurate. 
@lru_cache(1000)
def snap(latlng_):
	assert isinstance(latlng_, geom.LatLng)
	return get_snapgraph().snap(latlng_, None)

def heading(linesegaddr_, referencing_lineseg_aot_point_):
	return snapgraph().heading(linesegaddr_, referencing_lineseg_aot_point_)

if __name__ == '__main__':

	pass


