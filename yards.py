#!/usr/bin/env python

import vinfo, geom
from misc import *
import json

with open('yards.json') as fin:
	g_yards = []
	for raw_yard in json.load(fin):
		yard = []
		g_yards.append(yard)
		for raw_pt in raw_yard:
			yard.append(geom.LatLng(raw_pt[0], raw_pt[1]))

def remove_vehicles_in_yards(vis_):
	filter_in_place(vis_, lambda vi: not in_a_yard_vi(vi))

def in_a_yard_vi(vi_):
	return in_a_yard_latlon(vi_.latlng)

def in_a_yard_latlon(latlng_):
	for yard in g_yards:
		if latlng_.inside_polygon(yard):
			return True
	return False

if __name__ == '__main__':

	pass



