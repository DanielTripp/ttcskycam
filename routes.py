#!/usr/bin/python2.6

import sys, json, os.path
import vinfo, geom, mc, c, snaptogrid
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
			routepts = []
			for raw_routept in json.load(fin):
				routepts.append(geom.LatLng(raw_routept[0], raw_routept[1]))
		self.snaptogridcache = snaptogrid.SnapToGridCache([routepts])
		self.routeptidx_to_mofr = []
		for i in range(len(self.routepts)):
			if i==0:
				self.routeptidx_to_mofr.append(0)
			else:
				self.routeptidx_to_mofr.append(self.routeptidx_to_mofr[i-1] + self.routepts[i].dist_m(self.routepts[i-1]))
		assert len(self.routeptidx_to_mofr) == len(self.routepts)

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
		snap_result = self.snaptogridcache.snap(post_, {0:50, 1:300, 2:750}[tolerance_])
		if snap_result == None:
			return -1
		routeptidx = snap_result[0].startptidx
		r = self.routeptidx_to_mofr[routeptidx]
		if snap_result[1] != None:
			r += snap_result[1].dist_m(self.routepts[routeptidx])
		return int(r)

	def max_mofr(self):
		return int(math.ceil(self.routeptidx_to_mofr[-1]))

	def mofr_to_latlon(self, mofr_):
		r = self.mofr_to_latlonnheading(mofr_, 0)
		return (r[0] if r != None else None)

	def mofr_to_heading(self, mofr_, dir_):
		r = self.mofr_to_latlonnheading(mofr_, dir_)
		return (r[1] if r != None else None)

	def mofr_to_latlonnheading(self, mofr_, dir_):
		assert dir_ in (0, 1)
		if mofr_ < 0:
			return None
		for i in range(1, len(self.routeptidx_to_mofr)):
			if self.routeptidx_to_mofr[i] >= mofr_:
				prevpt = self.routepts[i-1]; curpt = self.routepts[i]
				prevmofr = self.routeptidx_to_mofr[i-1]; curmofr = self.routeptidx_to_mofr[i]
				pt = curpt.subtract(prevpt).scale((mofr_-prevmofr)/float(curmofr-prevmofr)).add(prevpt)
				return (pt, prevpt.heading(curpt))
		return None

	def mofr_to_stop(self, mofr_, dir_):
		return min(self.stops[dir_], key=lambda stop: abs(stop.mofr - mofr_))

	def general_heading(self, dir_):
		assert dir_ in (0, 1)
		startpt, endpt = self.routepts[0], self.routepts[-1]
		if dir_:
			startpt, endpt = endpt, startpt
		return startpt.heading(endpt)

	@property
	def routepts(self):
		return self.snaptogridcache.polylines[0]

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

	mofr_to_latlonnheading(0, 'dundas', 0)

	t0 = time.time()
	for mofr in [0] + range(-333, 20007, 13):
		#print '%d => %s' % (mofr, repr(mofr_to_latlonnheading(mofr, 'dundas', 0)))
		mofr_to_latlonnheading(mofr, 'dundas', 0)
	t1 = time.time()
	print (t1 - t0)





