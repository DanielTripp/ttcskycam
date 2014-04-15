#!/usr/bin/python2.6

import os, json
import geom, snapgraph, picklestore
from misc import *
from collections import Sequence
from itertools import *
from lru_cache import lru_cache
import shapefile

RDP_SIMPLIFY_EPSILON_METERS = 5

USE_TESTING_SUBSET = False

@picklestore.decorate
def get_polylines():
	r = get_polylines_from_shapefile()
	r += get_polylines_from_supplemental_json_file()
	if USE_TESTING_SUBSET:
		north = 43.6774561; east = -79.3611221; west = -79.4661788
		r = filter(lambda pline: any(pt.lat < north and pt.lng < east and pt.lng > west for pt in pline), r)
	simplify_polylines_via_rdp_algo(r)
	return r

def get_polylines_from_supplemental_json_file():
	with open('streets-supplemental.json') as fin:
		raw_plines = json.load(fin)
		return [[geom.LatLng(pt) for pt in pline] for pline in raw_plines]

# Modifies argument. 
def simplify_polylines_via_rdp_algo(polylines_):
	epsilon = RDP_SIMPLIFY_EPSILON_METERS
	for polyline in polylines_:
		polyline[:] = get_simplified_polyline_via_rdp_algo(polyline, epsilon)

# Thanks to http://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm 
def get_simplified_polyline_via_rdp_algo(pline_, epsilon_):
	log = False
	if len(pline_) <= 2:
		return pline_
	dmax = 0
	index = 0
	if log:
		printerr('---')
		printerr('pline:', pline_)
	if pline_[0].is_close(pline_[-1]):
		# so pline_ is a loop, and the dist_to_lineseg() call below will fail if we try it.  
		# let's go straight to the recurse.  
		dmax = epsilon_*2
		index = len(pline_)/2
		if log: printerr('loop')
	else:
		for i in range(1, len(pline_)-1):
			d = pline_[i].dist_to_lineseg(geom.LineSeg(pline_[0], pline_[-1]))
			if d > dmax:
				index = i
				dmax = d

	# If max distance is greater than epsilon, recursively simplify
	if dmax > epsilon_:
		recResults1 = get_simplified_polyline_via_rdp_algo(pline_[0:index+1], epsilon_)
		recResults2 = get_simplified_polyline_via_rdp_algo(pline_[index:], epsilon_)
		r = recResults1[:-1] + recResults2
		if log:
			printerr('pline again:', pline_)
			printerr('epsilon was exceeded by pt %d (%s).  recursed.' % (index, pline_[index]))
			printerr('recursive results:')
			printerr(recResults1)
			printerr(recResults2)
			printerr('combining into:')
			printerr(r)
			printerr('---')
		return r
	else:
		if log: 
			printerr('epsilon not exceeded.')
			printerr('---')
		return [pline_[0], pline_[-1]]

@picklestore.decorate
def get_polylines_from_shapefile():
	streetname_to_polylines = get_streetname_to_polylines_from_shapefile_directly()
	for plines in streetname_to_polylines.itervalues():
		join_connected_plines(plines)
	return sum(streetname_to_polylines.itervalues(), [])

def join_connected_plines(plines_):
	while True:
		joined_something = False
		for pline1idx, pline2idx in permutation_2_indexes(plines_):
			pline1 = plines_[pline1idx]; pline2 = plines_[pline2idx] 
			if pline1[-1].is_close(pline2[0]):
				pline1 += pline2[1:]
				del plines_[pline2idx]
				joined_something = True
				break
		if not joined_something:
			break

@picklestore.decorate
def get_streetname_to_polylines_from_shapefile_directly():
	# We would include 'Expressway' and 'Expressway Ramp' here too, but highways tend to have a lot of over/underpasses, 
	# so we were creating a lot of false vertexes on them.  We don't support any bus routes that travel on highways 
	# yet, and when normal buses came near these highways with all of their false vertexes (like Lansdowne buses 
	# at Yorkdale), even though we didn't tend to mistakenly think that the buses were on the highway, they were in multisnap 
	# range and performance of graph path-finding suffered a lot.
	# 
	# One might think that 'Collector' and 'Collector Ramp' refer to highways, but they don't.  eg. Adelaide St. is a 'Collector'. 
	street_fcode_descs = ['Access Road', 'Busway', 'Collector', 'Collector Ramp', 
			'Local', 'Major Arterial', 'Major Arterial Ramp', 'Minor Arterial', 'Minor Arterial Ramp', 'Pending', 'Other', 'Other Ramp']
	sf = shapefile.Reader('toronto_street_map/centreline_wgs84/CENTRELINE_WGS84')
	fields = [x for x in sf.fields if x[0] != 'DeletionFlag']
	idx_FCODE_DESC = [x[0] for x in fields].index('FCODE_DESC')
	idx_LF_NAME = [x[0] for x in fields].index('LF_NAME')
	streetname_to_polylines = defaultdict(lambda: [])
	for shape, record in izip(sf.iterShapes(), sf.iterRecords()):
		if record[idx_FCODE_DESC] in street_fcode_descs:
			polyline = [geom.LatLng(pt[1], pt[0]) for pt in shape.points]
			streetname = record[idx_LF_NAME]
			streetname_to_polylines[streetname].append(polyline)
	return dict(streetname_to_polylines)

@picklestore.decorate
def get_snapgraph():
	return snapgraph.SnapGraph(get_polylines(), forpaths=True, forpaths_disttolerance=RDP_SIMPLIFY_EPSILON_METERS+1, name='streets')

def heading(linesegaddr_, referencing_lineseg_aot_point_):
	return snapgraph().heading(linesegaddr_, referencing_lineseg_aot_point_)

if __name__ == '__main__':

	pass


