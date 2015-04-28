#!/usr/bin/env python

import json
from lru_cache import lru_cache
import vinfo, geom, mc
from misc import *

# Bounding boxes for each yard polygon are maintained as a performance optimization for the operation of determining
# whether a point is within the yard polygon or not.


@lru_cache(1)
@mc.decorate
def get_polygon_n_boundingboxes():
	with open('yards.json') as fin:
		r = []
		for raw_pts in json.load(fin):
			polypts = []
			for raw_pt in raw_pts:
				polypts.append(geom.LatLng(raw_pt[0], raw_pt[1]))
			r.append((polypts, geom.BoundingBox(polypts)))
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


