#!/usr/bin/env python

import vinfo, geom
from misc import *
import json

with open('yards.json') as fin:
	g_yards = json.load(fin)

def remove_vehicles_in_yards(vis_):
	filter_in_place(vis_, lambda vi: not in_a_yard_vi(vi))

def in_a_yard_vi(vi_):
	return in_a_yard_latlon(vi_.latlon)

def in_a_yard_latlon(latlon_):
	for yard in g_yards:
		if geom.inside_polygon(latlon_, yard):
			return True
	return False

