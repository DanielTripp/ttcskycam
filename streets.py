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
def get_streetname_to_polyline():
	r = get_streetname_to_polyline_from_shapefile()
	r.update({'street %d from supplemental file' % i: pline for i, pline in enumerate(get_polylines_from_supplemental_json_file())})
	if USE_TESTING_SUBSET:
		north = 43.6774561; east = -79.3611221; west = -79.4661788
		for streetname in r.keys():
			pline = r[streetname]
			if not any(pt.lat < north and pt.lng < east and pt.lng > west for pt in pline):
				del r[streetname]
	simplify_polylines_via_rdp_algo(r)
	return r

def get_polylines_from_supplemental_json_file():
	with open('streets-supplemental.json') as fin:
		raw_plines = json.load(fin)
		return [[geom.LatLng(pt) for pt in pline] for pline in raw_plines]

# Modifies argument. 
def simplify_polylines_via_rdp_algo(name_to_polyline_):
	epsilon = RDP_SIMPLIFY_EPSILON_METERS
	for pline in name_to_polyline_.itervalues():
		pline[:] = geom.get_simplified_polyline_via_rdp_algo(pline, epsilon)

# return dict.  keys are street names as strings, values are polylines i.e. lists of geom.LatLng. 
#			If there's a streetname that has more than one polyline, we will add numbers to it in order to make 
#			it unique in this dict. 
@picklestore.decorate
def get_streetname_to_polyline_from_shapefile():
	streetname_to_polylines = get_streetname_to_polylines_from_shapefile_directly()
	for plines in streetname_to_polylines.itervalues():
		join_connected_plines(plines)
	r = {}
	for streetname, polylines in streetname_to_polylines.iteritems():
		assert len(polylines) > 0
		if len(polylines) == 1:
			assert streetname not in r
			r[streetname] = polylines[0]
		else:
			for i, polyline in enumerate(polylines):
				unique_streetname = snapgraph.add_suffix_to_plinename(streetname, ' (part %d)' % i)
				assert unique_streetname not in r
				r[unique_streetname] = polyline
	return r

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
			# Because we can't assume that these plines will be in an order in the shapefile that is sensible for joining
			# them end-to-end (i.e. visual order, when looking at the whole street, all plines included.)  
			# The order of the latlngs of one pline could be in the reverse order compared to its neighbours.  
			# Most of them aren't, but I found at least one that is.
			elif pline1[0].is_close(pline2[0]):
				pline1[:] = pline2[-1::-1] + pline1[1:]
				del plines_[pline2idx]
				joined_something = True
				break
		if not joined_something:
			break

# returns: dict.  keys are strings, values are lists of polylines i.e. lists of lists of geom.LatLng.
# 				A single streetname could have multiple polylines.
@picklestore.decorate
def get_streetname_to_polylines_from_shapefile_directly():
	# We would include 'Expressway' and 'Expressway Ramp' here too, but highways tend to have a lot of over/underpasses, 
	# so we were creating a lot of false vertexes on them.  We don't support any bus routes that travel on highways 
	# yet, and when normal buses came near these highways with all of their false vertexes (like Lansdowne buses 
	# at Yorkdale), even though we didn't tend to mistakenly think that the buses were on the highway, they were in multisnap 
	# range and performance of graph path-finding suffered a lot.
	# 
	# One might think that 'Collector' and 'Collector Ramp' refer to highways, but they don't.  
	# eg. part of Adelaide St. is a 'Collector'. 
	street_fcode_descs = ['Access Road', 'Busway', 'Collector', 'Collector Ramp', 
			'Local', 'Major Arterial', 'Major Arterial Ramp', 'Minor Arterial', 'Minor Arterial Ramp', 
			'Pending', 'Other', 'Other Ramp']
	sf = shapefile.Reader('toronto_street_map/centreline_wgs84/CENTRELINE_WGS84')
	fields = [x for x in sf.fields if x[0] != 'DeletionFlag']
	idx_FCODE_DESC = [x[0] for x in fields].index('FCODE_DESC')
	idx_LF_NAME = [x[0] for x in fields].index('LF_NAME')
	streetname_to_polylines = defaultdict(lambda: [])
	for shape, record in izip(sf.iterShapes(), sf.iterRecords()):
		streettype = record[idx_FCODE_DESC] 
		if streettype in street_fcode_descs:
			polyline = [geom.LatLng(pt[1], pt[0]) for pt in shape.points]
			streetname = record[idx_LF_NAME]
			streetname = snapgraph.set_plinename_weight(streetname, get_weight_by_streettype(streettype))
			streetname_to_polylines[streetname].append(polyline)
	return dict(streetname_to_polylines)

def get_weight_by_streettype(type_):
	if type_ in ('Busway', 'Major Arterial', 'Major Arterial Ramp'):
		return 0.5
	elif type_ in ('Minor Arterial', 'Minor Arterial Ramp'):
		return 0.75
	elif type_ in ('Collector', 'Collector Ramp'):
		return 0.85
	else:
		return 1.0

@picklestore.decorate
def get_snapgraph():
	return snapgraph.SnapGraph(get_streetname_to_polyline(), forpaths=True, 
			forpaths_disttolerance=RDP_SIMPLIFY_EPSILON_METERS+1, name='streets')

def heading(linesegaddr_, referencing_lineseg_aot_point_):
	return snapgraph().heading(linesegaddr_, referencing_lineseg_aot_point_)

if __name__ == '__main__':

	pass


