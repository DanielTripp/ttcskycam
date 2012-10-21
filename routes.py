#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math, threading, json, os.path 
from math import *
from collections import defaultdict
import vinfo, db, geom, mc, c
from misc import *

FUDGEROUTE_TO_CONFIGROUTES = {'dundas': ['505'], 'queen': ['501', '301'], 'king': ['504']}

CONFIGROUTE_TO_FUDGEROUTE = {}
for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
	for configroute in configroutes:
		CONFIGROUTE_TO_FUDGEROUTE[configroute] = fudgeroute

FUDGEROUTES = FUDGEROUTE_TO_CONFIGROUTES.keys()
CONFIGROUTES = reduce(lambda x, y: x + y, FUDGEROUTE_TO_CONFIGROUTES.values(), [])

class Stop:
	def __init__(self, latlon_, stoptag_, mofr_):
		self.latlon = latlon_
		self.stoptag = stoptag_
		self.mofr = mofr_

	def __str__(self):
		return 'Stop %10s ( %f, %f )' % ('"'+self.stoptag+'"', self.lat, self.lon)

class RouteInfo:
	def __init__(self, routename_):
		self.init_routepts(routename_)
		self.init_stops_bothdirs(routename_)

	def init_routepts(self, routename_):
		with open('fudge_route_%s.json' % (routename_)) as fin:
			self.routepts = json.load(fin)

	def init_stops_bothdirs(self, routename_):
		self.stops = {}
		self.init_stops_singledir(routename_, 0)
		self.init_stops_singledir(routename_, 1)
	
	def init_stops_singledir(self, routename_, dir_):
		assert dir_ in (0, 1)
		self.stops[dir_] = []
		if not os.path.exists('stops_%s_dir%d.json' % (routename_, dir_)):
			return
		with open('stops_%s_dir%d.json' % (routename_, dir_)) as fin:
			stopdictlist = json.load(fin)
		for stopdict in stopdictlist:
			assert set(stopdict.keys()) == set(['lat', 'lon', 'stoptag'])
			lat = stopdict['lat']; lon = stopdict['lon']; stoptag = stopdict['stoptag']
			self.stops[dir_].append(Stop((lat, lon), stoptag, self.latlon_to_mofr((lat, lon))))

	def latlon_to_mofr(self, latlon_, tolerance_=0):
		assert tolerance_ in (0, 1, 2)
		post_xy = geom.XY.from_latlon(latlon_)
		route_xys = self.get_xys()
		r = 0.0
		success = False
		for route_pt1, route_pt2 in hopscotch(route_xys):
			if geom.passes(route_pt1, route_pt2, post_xy, tolerance_):
				pass_pt = geom.get_pass_point(route_pt1, route_pt2, post_xy)
				r += geom.dist_latlon(geom.LatLon(route_pt1), geom.LatLon(pass_pt))
				success = True
				break
			else:
				r += geom.dist_latlon(geom.LatLon(route_pt1), geom.LatLon(route_pt2))
		if success:
			return int(r)
		else: # cover cases eg. off the outside of a right angle in the route: 
			best_bet_dist_from_route_pt = sys.maxint; best_bet_mofr = -1
			running_mofr = 0.0
			for i, route_pt in enumerate(route_xys):
				if i > 0:
					running_mofr += geom.dist_latlon(geom.LatLon(route_xys[i]), geom.LatLon(route_xys[i-1]))
				cur_dist_from_route_pt = geom.dist_latlon(geom.LatLon(route_pt), geom.LatLon(*latlon_))
				if best_bet_dist_from_route_pt > cur_dist_from_route_pt:
					best_bet_dist_from_route_pt = cur_dist_from_route_pt
					best_bet_mofr = running_mofr
			return (int(best_bet_mofr) if (best_bet_dist_from_route_pt < {0:50, 1:300, 2:750}[tolerance_]) else -1)

	def get_xys(self):
		return [geom.XY.from_latlon(latlon) for latlon in self.routepts]

	def max_mofr(self):
		r = 0.0
		for route_pt1, route_pt2 in hopscotch(self.get_xys()):
			r += geom.dist_latlon(geom.LatLon(route_pt1), geom.LatLon(route_pt2))
		return int(r)

	def mofr_to_latlon(self, mofr_):
		r = mofr_to_latlonnheading(self, mofr_, 0)
		return (r[0] if r != None else None)

	def mofr_to_heading(self, mofr_, dir_):
		r = self.mofr_to_latlonnheading(mofr_, dir_)
		return (r[1] if r != None else None)

	def mofr_to_latlonnheading(self, mofr_, dir_):
		assert dir_ in (0, 1)
		mofr_remaining = mofr_
		for route_pt1, route_pt2 in hopscotch(self.get_xys()):
			mofr_on_cur_segment = geom.dist_latlon(geom.LatLon(route_pt1), geom.LatLon(route_pt2))
			if mofr_on_cur_segment > mofr_remaining:
				r_latlon = geom.add(route_pt1, geom.scale(float(mofr_remaining)/mofr_on_cur_segment, geom.diff(route_pt2, route_pt1))).latlon()
				r_heading = geom.heading(route_pt1, route_pt2)
				if dir_:
					r_heading = (r_heading + 180) % 360
				return (r_latlon, r_heading)
			else:
				mofr_remaining -= mofr_on_cur_segment
		return None

	def mofr_to_stop(self, mofr_, dir_):
		return min(self.stops[dir_], key=lambda stop: abs(stop.mofr - mofr_))

	def general_heading(self, dir_):
		assert dir_ in (0, 1)
		startpt, endpt = self.routepts[0], self.routepts[-1]
		if dir_:
			startpt, endpt = endpt, startpt
		return geom.heading_from_latlons(geom.LatLon(startpt[0], startpt[1]), geom.LatLon(endpt[0], endpt[1]))

g_routename_to_info = {}

def max_mofr(route_):
	return get_routeinfo(route_).max_mofr()

def get_routeinfo(routename_):
	routename = massage_to_fudgeroute(routename_)
	if routename not in FUDGEROUTES:
		raise Exception('route %s is unknown' % (routename))
	if routename in g_routename_to_info:
		r = g_routename_to_info[routename]
	else:
		mckey = '%s-RouteInfo(%s)' % (c.SITE_VERSION, routename)
		r = mc.client.get(mckey)
		if not r:
			r = RouteInfo(routename)
			mc.client.set(mckey, r)
		g_routename_to_info[routename] = r
	return r

def massage_to_fudgeroute(route_):
	if route_ in FUDGEROUTES:
		return route_
	else:
		return configroute_to_fudgeroute(route_)

def get_all_routes_latlons():
	r = []
	for fudgeroute in FUDGEROUTES:
		r.append(get_routeinfo(fudgeroute).routepts)
	return r

def latlon_to_mofr(latlon_, route_, tolerance_=0):
	if route_ not in CONFIGROUTES and route_ not in FUDGEROUTES:
		return -1
	else:
		return get_routeinfo(route_).latlon_to_mofr(latlon_, tolerance_)

def mofr_to_latlon(mofr_, route_):
	return get_routeinfo(route_).mofr_to_latlon(mofr_)

def mofr_to_latlonnheading(mofr_, route_, dir_):
	return get_routeinfo(route_).mofr_to_latlonnheading(mofr_, dir_)

def fudgeroute_to_configroutes(fudgeroute_name_):
	if fudgeroute_name_ not in FUDGEROUTE_TO_CONFIGROUTES:
		raise Exception('fudgeroute %s is unknown' % (fudgeroute_name_))
	return FUDGEROUTE_TO_CONFIGROUTES[fudgeroute_name_]

def configroute_to_fudgeroute(configroute_):
	for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
		if configroute_ in configroutes:
			return fudgeroute
	raise Exception('configroute %s is unknown' % (configroute_))

#@accepts 
def get_endpoint_info(origlat_, origlon_, destlat_, destlon_):
	orig_route_to_mofr = get_route_to_mofr((origlat_, origlon_))
	dest_route_to_mofr = get_route_to_mofr((destlat_, destlon_))
	common_routes = set(orig_route_to_mofr.keys()).intersection(set(dest_route_to_mofr))
	if not common_routes:
		return None
	else:
		route = list(common_routes)[0]
		direction = (0 if orig_route_to_mofr[route] < dest_route_to_mofr[route] else 1)
		orig_stop = get_routeinfo(route).mofr_to_stop(orig_route_to_mofr[route], direction)
		dest_stop = get_routeinfo(route).mofr_to_stop(dest_route_to_mofr[route], direction)
		return {'route': route, 'direction': direction, 
				'origstoptag': orig_stop.stoptag, 'origlatlon': orig_stop.latlon, 'origmofr': orig_route_to_mofr[route], 
				'deststoptag': dest_stop.stoptag, 'destlatlon': dest_stop.latlon, 'destmofr': dest_route_to_mofr[route]}

def get_route_to_mofr(latlon_):
	r = {}
	for route in FUDGEROUTES:
		mofr = latlon_to_mofr(latlon_, route, tolerance_=1)
		if mofr != -1:
			r[route] = mofr
	return r

def snap_to_line(pt_, line_):
	assert all(isinstance(x, XY) for x in (pt_, line_[0], line_[1]))
	ang1 = angle(line_[1], line_[0], pt_)
	ang2 = angle(line_[0], line_[1], pt_)
	if (ang1 < math.pi/2) and (ang2 < math.pi/2):
		return get_pass_point(line_[0], line_[1], pt_)
	else:
		dist0 = dist(pt_, line_[0]); dist1 = dist(pt_, line_[1])
		return (line_[0] if dist0 < dist1 else line_[1])

def make_snap_db():
	get_routeinfo('queen').get_xys()

if __name__ == '__main__':

	for route in get_all_routes_latlons():
		for pt in route:
			print pt






