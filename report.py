#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math
from collections import defaultdict
import db, vinfo, geom
from misc import *

def get_recent_travel_times(route_, orig_, post_, dir_, n_, end_time_em_=now_em()):
	assert type(route_) == str and isinstance(orig_, geom.XY) and isinstance(post_, geom.XY) \
		and type(dir_) == str and type(n_) == int
	r = []
	for standvi, forevi in db.get_recent_passing_vehicles(route_, post_, n_, end_time_em_=end_time_em_, dir_=dir_):
		assert standvi.route_tag == forevi.route_tag
		assert standvi.vehicle_id == forevi.vehicle_id
		post_t = standvi.get_pass_time_interp(forevi, post_)
		paststandvi, pastforevi = db.find_passing(standvi.route_tag, standvi.vehicle_id, dir_, standvi.time, orig_)
		orig_t = paststandvi.get_pass_time_interp(pastforevi, orig_)
		travel_time = post_t - orig_t
		r.append((standvi.vehicle_id, post_t, travel_time))
	return r

if __name__ == '__main__':

	if 0:
		route = '505'
		post = geom.XY.from_latlon((43.650, -79.409))
		orig =  geom.XY.from_latlon((43.652, -79.449))
	else:
		route = '501'
		post =  geom.XY.from_latlon((43.652, -79.38))
		orig = geom.XY.from_latlon((43.645, -79.409))
	direction = 'east'

	for vid, post_t_em, travel_time in get_recent_travel_times(route, orig, post, direction, 5, 1325442533000):
		print '%s took %s arriving at %s' % (vid, m_to_str(travel_time), em_to_str(post_t_em))

