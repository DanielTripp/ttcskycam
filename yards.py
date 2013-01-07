#!/usr/bin/env python

import json
import vinfo, geom, mc
from misc import *

# Bounding boxes for each yard polygon are maintained as a performance optimization for the operation of determining
# whether a point is within the yard polygon or not.

class BoundingBox:
	
	def __init__(self, polygon_pts_):
		assert isinstance(polygon_pts_[0], geom.LatLng)
		self.southwest = geom.LatLng(min(pt.lat for pt in polygon_pts_), min(pt.lng for pt in polygon_pts_))
		self.northeast = geom.LatLng(max(pt.lat for pt in polygon_pts_), max(pt.lng for pt in polygon_pts_))


g_polygon_n_boundingboxes = None

def get_polygon_n_boundingboxes():
	global g_polygon_n_boundingboxes
	mckey = mc.make_key('get_polygon_n_boundingboxes')
	g_polygon_n_boundingboxes = mc.client.get(mckey)
	if not g_polygon_n_boundingboxes:
		g_polygon_n_boundingboxes = get_polygon_n_boundingboxes_impl()
		mc.client.set(mckey, g_polygon_n_boundingboxes)
	return g_polygon_n_boundingboxes

def get_polygon_n_boundingboxes_impl():
	with open('yards.json') as fin:
		r = []
		for raw_pts in json.load(fin):
			polypts = []
			for raw_pt in raw_pts:
				polypts.append(geom.LatLng(raw_pt[0], raw_pt[1]))
			r.append((polypts, BoundingBox(polypts)))
		return r

def remove_vehicles_in_yards(vis_):
	filter_in_place(vis_, lambda vi: not in_a_yard_latlng(vi.latlng))

def in_a_yard_latlng(latlng_):
	for yard_polygon_pts, yard_bounding_box in get_polygon_n_boundingboxes():
		# The order here is important because the entire point of maintaining the bounding boxes is for them to
		# act as a fail-fast pre-test for the full 'inside polygon' test.  This short-circuit boolean 'and'
		# operator here accomplishes this.
		if latlng_.is_within_box(yard_bounding_box.southwest, yard_bounding_box.northeast) \
				and latlng_.inside_polygon(yard_polygon_pts):
			return True
	return False

if __name__ == '__main__':

	pass



