#!/usr/bin/python2.6

import sys, json, os.path
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
		assert isinstance(latlon_, geom.LatLng) and isinstance(stoptag_, basestring) and isinstance(mofr_, int)
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
			self.routepts = []
			for raw_routept in json.load(fin):
				self.routepts.append(geom.LatLng(raw_routept[0], raw_routept[1]))

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
			for stopdict in json.load(fin):
				assert set(stopdict.keys()) == set(['lat', 'lon', 'stoptag'])
				latlng = geom.LatLng(stopdict['lat'], stopdict['lon']); stoptag = stopdict['stoptag']
				self.stops[dir_].append(Stop(latlng, stoptag, self.latlon_to_mofr(latlng)))

	def latlon_to_mofr(self, post_, tolerance_=0):
		assert isinstance(post_, geom.LatLng) and (tolerance_ in (0, 1, 2))
		r = 0.0
		success = False
		for routept1, routept2 in hopscotch(self.routepts):
			if geom.passes(routept1, routept2, post_, tolerance_):
				pass_pt = geom.get_pass_point(routept1, routept2, post_)
				r += routept1.dist_m(pass_pt)
				success = True
				break
			else:
				r += routept1.dist_m(routept2)
		if success:
			return int(r)
		else: # cover cases eg. off the outside of a right angle in the route: 
			best_bet_dist_from_route_pt = sys.maxint; best_bet_mofr = -1
			running_mofr = 0.0
			for i, route_pt in enumerate(self.routepts):
				if i > 0:
					running_mofr += self.routepts[i].dist_m(self.routepts[i-1])
				cur_dist_from_route_pt = route_pt.dist_m(post_)
				if best_bet_dist_from_route_pt > cur_dist_from_route_pt:
					best_bet_dist_from_route_pt = cur_dist_from_route_pt
					best_bet_mofr = running_mofr
			return (int(best_bet_mofr) if (best_bet_dist_from_route_pt < {0:50, 1:300, 2:750}[tolerance_]) else -1)

	def max_mofr(self):
		r = 0.0
		for routept1, routept2 in hopscotch(self.routepts):
			r += routept1.dist_m(routept2)
		return int(r)

	def mofr_to_latlon(self, mofr_):
		r = self.mofr_to_latlonnheading(mofr_, 0)
		return (r[0] if r != None else None)

	def mofr_to_heading(self, mofr_, dir_):
		r = self.mofr_to_latlonnheading(mofr_, dir_)
		return (r[1] if r != None else None)

	def mofr_to_latlonnheading(self, mofr_, dir_):
		assert dir_ in (0, 1)
		mofr_remaining = mofr_
		for routept1, routept2 in hopscotch(self.routepts):
			mofr_on_cur_segment = routept1.dist_m(routept2)
			if mofr_on_cur_segment > mofr_remaining:
				r_latlon = routept1.add(routept2.subtract(routept1).scale(float(mofr_remaining)/mofr_on_cur_segment))
				r_heading = routept1.heading(routept2)
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
		return startpt.heading(endpt)

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
		r_l = []
		r.append(r_l)
		for routept in get_routeinfo(fudgeroute).routepts:
			r_l.append([routept.lat, routept.lng])
	return r

def latlon_to_mofr(latlon_, route_, tolerance_=0):
	assert isinstance(latlon_, geom.LatLng)
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

def get_endpoint_info(origlat_, origlon_, destlat_, destlon_):
	orig_route_to_mofr = get_route_to_mofr(geom.LatLng(origlat_, origlon_))
	dest_route_to_mofr = get_route_to_mofr(geom.LatLng(destlat_, destlon_))
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

if __name__ == '__main__':

	pass



