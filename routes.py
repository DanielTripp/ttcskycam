#!/usr/bin/python2.6

import sys, json, os.path, bisect
from backport_OrderedDict import *
import vinfo, geom, mc, c, snaptogrid
from misc import *

FUDGEROUTE_TO_CONFIGROUTES = {'dundas': ['505'], 'queen': ['501', '301'], 'king': ['504'], 'spadina': ['510'], \
'bathurst': ['511', '310'], 'dufferin': ['29', '329'], 'lansdowne': ['47'], 'ossington': ['63', '316'], 'college': ['506', '306'], \
'dupont': ['26']}

CONFIGROUTE_TO_FUDGEROUTE = {}
for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
	for configroute in configroutes:
		CONFIGROUTE_TO_FUDGEROUTE[configroute] = fudgeroute

FUDGEROUTES = FUDGEROUTE_TO_CONFIGROUTES.keys()
CONFIGROUTES = reduce(lambda x, y: x + y, FUDGEROUTE_TO_CONFIGROUTES.values(), [])

class Stop:
	def __init__(self, stoptag_, latlng_, mofr_, dirtags_serviced_):
		assert isinstance(stoptag_, basestring) and isinstance(latlng_, geom.LatLng) and isinstance(mofr_, int)
		self.latlng = latlng_
		self.stoptag = stoptag_
		self.mofr = mofr_
		self.dirtags_serviced = dirtags_serviced_

	@property 
	def is_sunday_only(self):
		for dirtag in self.dirtags_serviced:
			if not dirtag[-3:].lower() == 'sun':
				return False
		return True 

	# 'recorded' currently means 'at an intersection', meaning we have predictions for that stop in our database. 
	@property 
	def are_predictions_recorded(self):
		for i in get_intersections():
			if self.stoptag in (i.froute1_dir0_stoptag, i.froute1_dir1_stoptag, i.froute2_dir0_stoptag, i.froute2_dir1_stoptag):
				return True
		return False

	def __str__(self):
		return 'Stop %10s mofr=%d ( %f, %f )' % ('"'+self.stoptag+'"', self.mofr, self.latlng.lat, self.latlng.lng)

	def __repr__(self):
		return self.__str__()

class RouteInfo:
	def __init__(self, routename_):
		self.name = routename_
		self.init_routepts()
		self.init_stops()

	def init_routepts(self):
		def read(filename_):
			with open(filename_) as fin:
				r = []
				for raw_routept in json.load(fin):
					r.append(geom.LatLng(raw_routept[0], raw_routept[1]))
				return r

		routepts_both_dirs_filename = 'fudge_route_%s.json' % (self.name)
		if os.path.exists(routepts_both_dirs_filename):
			routepts = [read(routepts_both_dirs_filename)]
			self.is_split_by_dir = False
		else:
			routepts = [read('fudge_route_%s_dir0.json' % (self.name)), read('fudge_route_%s_dir1.json' % (self.name))]
			self.is_split_by_dir = True
		self.snaptogridcache = snaptogrid.SnapToGridCache(routepts)
		self.routeptaddr_to_mofr = [[], []]
		for dir in (0, 1):
			if dir == 1 and not self.is_split_by_dir:
				self.routeptaddr_to_mofr[1] = self.routeptaddr_to_mofr[0]
			else:
				for i in range(len(self.routepts(dir))):
					if i==0:
						self.routeptaddr_to_mofr[dir].append(0)
					else:
						prevpt = self.routepts(dir)[i-1]; curpt = self.routepts(dir)[i]
						self.routeptaddr_to_mofr[dir].append(self.routeptaddr_to_mofr[dir][i-1] + prevpt.dist_m(curpt))
			assert len(self.routeptaddr_to_mofr[dir]) == len(self.routepts(dir))
		if self.is_split_by_dir:
			assert (sum(pt1.dist_m(pt2) for pt1, pt2 in hopscotch(self.routepts(0))) - \
					sum(pt1.dist_m(pt2) for pt1, pt2 in hopscotch(self.routepts(1)))) < 0.01

	def init_stops(self):
		self.init_stops_dir_to_stoptag_to_stop()
		self.init_stops_dir_to_mofr_to_stop_ordereddict()

	def init_stops_dir_to_stoptag_to_stop(self):
		self.dir_to_stoptag_to_stop = {}
		with open('stops_%s.json' % self.name, 'r') as fin:
			stops_file_content_json = json.load(fin)
			assert sorted(int(x) for x in stops_file_content_json.keys()) == [0, 1] # The direction signifiers in the file, 0 and 1, 
					# will be strings because JSON doesn't allow ints as keys. 
			for direction_str in stops_file_content_json.keys():
				direction_int = int(direction_str)
				self.dir_to_stoptag_to_stop[direction_int] = {}
				for stoptag, stopdetails in stops_file_content_json[direction_str].iteritems():
					assert set(stopdetails.keys()) == set(['lat', 'lon', 'dirtags_serviced'])
					latlng = geom.LatLng(stopdetails['lat'], stopdetails['lon']); dirtags_serviced = stopdetails['dirtags_serviced']
					new_stop = Stop(stoptag, latlng, self.latlon_to_mofr(latlng), dirtags_serviced)
					if new_stop.mofr != -1 and not new_stop.is_sunday_only:
						self.dir_to_stoptag_to_stop[direction_int][stoptag] = new_stop
	
	def init_stops_dir_to_mofr_to_stop_ordereddict(self):
		self.dir_to_mofr_to_stop_ordereddict = {} # This is a redundant data structure for fast lookups. 
		self.dir_to_mofr_to_stop_ordereddict_keys = {} # This is a redundant data structure on the above redundant data structure. 
		for direction in (0, 1):
			mofr_to_stop_ordereddict = OrderedDict()
			self.dir_to_mofr_to_stop_ordereddict[direction] = mofr_to_stop_ordereddict
			mofr_to_stop_unordereddict = file_under_key(self.dir_to_stoptag_to_stop[direction].values(), lambda stop: stop.mofr, True)
			for mofr in sorted(mofr_to_stop_unordereddict.keys()):
				stop = mofr_to_stop_unordereddict[mofr]
				mofr_to_stop_ordereddict[mofr] = stop

			# Caching the list of keys too.  This may seem like optimization overkill but even this keys() 
			# call was cumulatively taking half a second in a simple path-finding test case. 
			self.dir_to_mofr_to_stop_ordereddict_keys[direction] = mofr_to_stop_ordereddict.keys()

	def mofr_to_stop(self, dir_, mofr_):
		assert dir_ in (0, 1) and isinstance(mofr_, int)
		mofr_to_stop_ordereddict = self.dir_to_mofr_to_stop_ordereddict[dir_]
		ordered_mofrs = self.dir_to_mofr_to_stop_ordereddict_keys[dir_]
		bisect_idx = bisect.bisect_left(ordered_mofrs, mofr_)

		# So either the stop at bisect_idx or bisect_idx-1 is the closest stop that we're looking for:
		possible_stops = []
		def add_possible_stop_maybe(idx__):
			if 0 <= idx__ < len(ordered_mofrs):
				possible_stops.append(mofr_to_stop_ordereddict[ordered_mofrs[idx__]])
		add_possible_stop_maybe(bisect_idx)
		add_possible_stop_maybe(bisect_idx-1)
		return min(possible_stops, key=lambda stop: abs(stop.mofr - mofr_))

	def get_stop(self, stoptag_):
		for direction in (0, 1):
			if stoptag_ in self.dir_to_stoptag_to_stop[direction]:
				return self.dir_to_stoptag_to_stop[direction][stoptag_]
		raise Exception('Could not find stop for stoptag "%s", route %s' % (stoptag_, self.name))

	def latlon_to_mofr(self, post_, tolerance_=0):
		assert isinstance(post_, geom.LatLng) and (tolerance_ in (0, 1, 1.5, 2))
		snap_result = self.snaptogridcache.snap(post_, {0:50, 1:300, 1.5:600, 2:2000}[tolerance_])
		if snap_result is None:
			return -1
		dir = snap_result[1].polylineidx; routeptidx = snap_result[1].startptidx
		r = self.routeptaddr_to_mofr[dir][routeptidx]
		if snap_result[2]:
			r += snap_result[0].dist_m(self.routepts(dir)[routeptidx])
		return int(r)

	def snaptest(self, pt_, tolerance_=0):
		assert isinstance(pt_, geom.LatLng) and (tolerance_ in (0, 1, 2))
		snap_result = self.snaptogridcache.snap(pt_, {0:50, 1:300, 2:750}[tolerance_])
		snapped_pt = (snap_result[0] if snap_result is not None else None)
		mofr = self.latlon_to_mofr(pt_, tolerance_)
		resnapped_pts = [self.mofr_to_latlon(mofr, 0), self.mofr_to_latlon(mofr, 1)]
		return (snapped_pt, mofr, resnapped_pts)

	def max_mofr(self):
		return int(math.ceil(self.routeptaddr_to_mofr[0][-1]))

	def mofr_to_latlon(self, mofr_, dir_):
		r = self.mofr_to_latlonnheading(mofr_, dir_)
		return (r[0] if r != None else None)

	def mofr_to_heading(self, mofr_, dir_):
		r = self.mofr_to_latlonnheading(mofr_, dir_)
		return (r[1] if r != None else None)

	def mofr_to_latlonnheading(self, mofr_, dir_):
		assert dir_ in (0, 1)
		if mofr_ < 0:
			return None
		for i in range(1, len(self.routeptaddr_to_mofr[dir_])):
			if self.routeptaddr_to_mofr[dir_][i] >= mofr_:
				prevpt = self.routepts(dir_)[i-1]; curpt = self.routepts(dir_)[i]
				prevmofr = self.routeptaddr_to_mofr[dir_][i-1]; curmofr = self.routeptaddr_to_mofr[dir_][i]
				pt = curpt.subtract(prevpt).scale((mofr_-prevmofr)/float(curmofr-prevmofr)).add(prevpt)
				return (pt, prevpt.heading(curpt) if dir_==0 else curpt.heading(prevpt))
		return None

	def stoptag_to_mofr(self, dir_, stoptag_):
		return self.dir_to_stoptag_to_stop[dir_][stoptag_].mofr

	def general_heading(self, dir_):
		assert dir_ in (0, 1)
		startpt, endpt = self.routepts(0)[0], self.routepts(0)[-1]
		if dir_:
			startpt, endpt = endpt, startpt
		return startpt.heading(endpt)

	def routepts(self, dir_):
		assert dir_ in (0, 1)
		if self.is_split_by_dir:
			return self.snaptogridcache.polylines[dir_]
		else:
			return self.snaptogridcache.polylines[0]

	def dir_from_latlngs(self, latlng1_, latlng2_):
		mofr1 = self.latlon_to_mofr(latlng1_, tolerance_=2)
		mofr2 = self.latlon_to_mofr(latlng2_, tolerance_=2)
		if mofr1 == -1 or mofr2 == -1:
			raise Exception('Invalid (off-route) latlng argument (or arguments) to dir_from_latlngs.  (%s, %s, %s)' 
					% (self.name, latlng1_, latlng2_))
		return (0 if mofr2 > mofr1 else 1)

	def dir_of_stoptag(self, stoptag_):
		for direction in (0, 1):
			if stoptag_ in self.dir_to_stoptag_to_stop[direction]:
				return direction
		raise Exception('Couldn\'t find dir of stoptag %s in route %s' % (stoptag_, self.name))

	def get_next_downstream_stop_with_predictions_recorded(self, stoptag_):
		direction = self.dir_of_stoptag(stoptag_)
		stop_mofrs = self.dir_to_mofr_to_stop_ordereddict_keys[direction][:]
		if direction == 1:
			stop_mofrs = stop_mofrs[::-1]
		begin_stoptag_mofr = self.dir_to_stoptag_to_stop[direction][stoptag_].mofr
		begin_stoptag_idx_in_stop_mofrs = stop_mofrs.index(begin_stoptag_mofr)
		for stop in [self.dir_to_mofr_to_stop_ordereddict[direction][mofr] for mofr in stop_mofrs[begin_stoptag_idx_in_stop_mofrs:]]:
			if stop.are_predictions_recorded:
				return stop
		raise Exception('failed to find next downstream predictions-recorded stop for route %s stoptag %s' % (self.name, stoptag_))

def max_mofr(route_):
	return routeinfo(route_).max_mofr()

g_routename_to_info = {}

def routeinfo(routename_):
	routename = massage_to_fudgeroute(routename_)
	if routename not in FUDGEROUTES:
		raise Exception('route %s is unknown' % (routename))
	if routename in g_routename_to_info:
		r = g_routename_to_info[routename]
	else:
		mckey = mc.make_key('RouteInfo', routename)
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
		for routept in routeinfo(fudgeroute).routepts(0):
			r_l.append([routept.lat, routept.lng])
	return r

def latlon_to_mofr(route_, latlon_, tolerance_=0):
	assert isinstance(latlon_, geom.LatLng)
	if route_ not in CONFIGROUTES and route_ not in FUDGEROUTES:
		return -1
	else:
		return routeinfo(route_).latlon_to_mofr(latlon_, tolerance_)

def mofr_to_latlon(route_, mofr_):
	return routeinfo(route_).mofr_to_latlon(mofr_)

def mofr_to_latlonnheading(route_, mofr_, dir_):
	return routeinfo(route_).mofr_to_latlonnheading(mofr_, dir_)

def fudgeroute_to_configroutes(fudgeroute_name_):
	if fudgeroute_name_ not in FUDGEROUTE_TO_CONFIGROUTES:
		raise Exception('fudgeroute %s is unknown' % (fudgeroute_name_))
	return FUDGEROUTE_TO_CONFIGROUTES[fudgeroute_name_]

def configroute_to_fudgeroute(configroute_):
	for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
		if configroute_ in configroutes:
			return fudgeroute
	raise Exception('configroute %s is unknown' % (configroute_))

def get_trip_endpoint_info(orig_, dest_, visible_fudgeroutendirs_):
	assert isinstance(orig_, geom.LatLng) and isinstance(dest_, geom.LatLng)
	assert len(set(x[0] for x in visible_fudgeroutendirs_)) == len(visible_fudgeroutendirs_) # no duplicates 
	orig_route_to_mofr = get_route_to_mofr(orig_)
	dest_route_to_mofr = get_route_to_mofr(dest_)
	common_routes = set(orig_route_to_mofr.keys()).intersection(set(dest_route_to_mofr))
	common_routes = common_routes.intersection(set([x[0] for x in visible_fudgeroutendirs_]))
	if not common_routes:
		return None
	else:
		for route in common_routes:
			direction = (0 if orig_route_to_mofr[route] < dest_route_to_mofr[route] else 1)
			routes_dir_in_visible_list = [x for x in visible_fudgeroutendirs_ if x[0] == route][0][1]
			if direction == routes_dir_in_visible_list:
				ri = routeinfo(route)
				orig_stop = ri.mofr_to_stop(direction, orig_route_to_mofr[route])
				dest_stop = ri.mofr_to_stop(direction, dest_route_to_mofr[route])
				orig_latlng = ri.mofr_to_latlon(orig_stop.mofr, direction)
				dest_latlng = ri.mofr_to_latlon(dest_stop.mofr, direction)
				return {'route': route, 'direction': direction, 
						'origstoptag': orig_stop.stoptag, 'origlatlng': orig_latlng, 'origmofr': orig_stop.mofr, 
						'deststoptag': dest_stop.stoptag, 'destlatlng': dest_latlng, 'destmofr': dest_stop.mofr}
		return None

def get_route_to_mofr(latlon_):
	r = {}
	for route in FUDGEROUTES:
		mofr = latlon_to_mofr(route, latlon_, tolerance_=1)
		if mofr != -1:
			r[route] = mofr
	return r

def get_configroute_to_fudgeroute_map():
	return CONFIGROUTE_TO_FUDGEROUTE

def get_heading_from_compassdir(compassdir_):
	assert compassdir_ in ('n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw')
	r = {'n':0, 'e':90, 's':180, 'w':270, 'ne':45, 'se':135, 'sw':225, 'nw':315}[compassdir_]
	CONSIDER_NORTH_TO_BE_THIS_HEADING = 343 # Toronto's street grid is tilted this much from north. 
	r += CONSIDER_NORTH_TO_BE_THIS_HEADING
	r = geom.normalize_heading(r)
	return r

class FactoredSampleScorer(object):
	
	def __init__(self, factor_definitions_min_max_inverse_list_):
		self.min_max_inverse = factor_definitions_min_max_inverse_list_[:]

	def get_score(self, sample_):
		assert (len(sample_) == self.num_factors)
		r = 1.0
		for factoridx, factorval in enumerate(sample_):
			min, max, inverse = self.min_max_inverse[factoridx]
			if inverse:
				r *= (max - factorval)/float(max - min)
			else:
				r *= (factorval - min)/float(max - min)
		return r

	@property 
	def num_factors(self):
		return len(self.min_max_inverse)

def get_fudgeroutes_for_map_bounds(southwest_, northeast_, compassdir_, maxroutes_):
	assert isinstance(southwest_, geom.LatLng) and isinstance(northeast_, geom.LatLng) and isinstance(maxroutes_, int)
	heading = get_heading_from_compassdir(compassdir_)
	bounds_midpt = southwest_.avg(northeast_)
	scorer = FactoredSampleScorer([[0, southwest_.dist_m(northeast_), False], [0, 90, True], [0, bounds_midpt.dist_m(northeast_), True]])
	fudgeroute_n_dir_to_score = {}
	for fudgeroute in FUDGEROUTES:
		for dir in (0, 1):
			fudgeroute_n_dir_to_score[(fudgeroute, dir)] = 0.0
			for routelineseg_pt1, routelineseg_pt2 in hopscotch(routeinfo(fudgeroute).routepts(dir)):
				if dir == 1:
					routelineseg_pt1, routelineseg_pt2 = routelineseg_pt2, routelineseg_pt1
				if geom.does_line_segment_overlap_box(routelineseg_pt1, routelineseg_pt2, southwest_, northeast_):
					routelineseg_pt1, routelineseg_pt2 = geom.constrain_line_segment_to_box(
							routelineseg_pt1, routelineseg_pt2, southwest_, northeast_)
					routelineseg_heading = routelineseg_pt1.heading(routelineseg_pt2)
					routelineseg_midpt = routelineseg_pt1.avg(routelineseg_pt2)
					headings_diff = geom.diff_headings(routelineseg_heading, heading)
					if headings_diff < 80:
						routelineseg_len_m = routelineseg_pt1.dist_m(routelineseg_pt2)
						routelineseg_midpt_dist_from_bounds_centre = bounds_midpt.dist_m(routelineseg_midpt)
						scoresample = (routelineseg_len_m, headings_diff, routelineseg_midpt_dist_from_bounds_centre)
						fudgeroute_n_dir_to_score[(fudgeroute, dir)] += scorer.get_score(scoresample)
						if 0: 
							printerr('fudgeroute_n_dir_to_score(%20s) - line at ( %.5f, %.5f ) - %4.0f, %2d, %4.0f ==> %.3f' % ((fudgeroute, dir), \
									#routelineseg_midpt.lat, routelineseg_midpt.lng,  \
									routelineseg_pt1.lat, routelineseg_pt2.lng, \
									scoresample[0], scoresample[1], scoresample[2], scorer.get_score(scoresample)))
			#printerr('score for '+fudgeroute+' dir '+str(dir)+' = '+str(fudgeroute_n_dir_to_score[(fudgeroute, dir)]))
	
	# If a single fudgeroute is represented in both 0 and 1 directions, then here remove the lower-scored direction.  
	# Because I don't know how to show both directions of a route on a map at the same time. 
	if 0:
		printerr([x for x in sorted(fudgeroute_n_dir_to_score.items(), key=lambda x: x[1], reverse=True)])
	top_fudgeroute_n_dirs = [x[0] for x in sorted(fudgeroute_n_dir_to_score.items(), key=lambda x: x[1], reverse=True) if x[1] > 0.05]
	for i in range(len(top_fudgeroute_n_dirs)-1, -1, -1):
		fudgeroute, dir = top_fudgeroute_n_dirs[i]
		opposite_dir = int(not dir)
		if (fudgeroute, opposite_dir) in top_fudgeroute_n_dirs[:i]:
			top_fudgeroute_n_dirs.pop(i)

	top_fudgeroute_n_dirs = top_fudgeroute_n_dirs[:maxroutes_]

	return top_fudgeroute_n_dirs

def get_fudgeroute_to_compassdir_to_intdir():
	r = {}
	for fudgeroute in FUDGEROUTES:
		r[fudgeroute] = {}
		for intdir in (0, 1):
			routepts = routeinfo(fudgeroute).routepts(intdir)
			if intdir == 0:
				heading = routepts[0].heading(routepts[-1])
			else:
				heading = routepts[-1].heading(routepts[0])
			r[fudgeroute][heading_to_compassdir(heading)] = intdir
	return r

def heading_to_compassdir(heading_):
	assert isinstance(heading_, int) and (0 <= heading_  < 360)
	if heading_ <= 45 or heading_ >= 315:
		return 'n'
	elif heading_ <= 135:
		return 'e'
	elif heading_ <= 225:
		return 's'
	else:
		return 'w'


def snaptest(fudgeroutename_, pt_, tolerance_=0):
	return routeinfo(fudgeroutename_).snaptest(pt_, tolerance_)

class Intersection:

	def __init__(self, froute1_, froute1mofr_, froute2_, froute2mofr_, 
			froute1_dir0_stoptag_, froute1_dir1_stoptag_, froute2_dir0_stoptag_, froute2_dir1_stoptag_, 
			latlng_):
		assert isinstance(latlng_, geom.LatLng)
		self.froute1 = froute1_
		self.froute1mofr = froute1mofr_
		self.froute2 = froute2_
		self.froute2mofr = froute2mofr_
		self.froute1_dir0_stoptag = froute1_dir0_stoptag_
		self.froute1_dir1_stoptag = froute1_dir1_stoptag_
		self.froute2_dir0_stoptag = froute2_dir0_stoptag_
		self.froute2_dir1_stoptag = froute2_dir1_stoptag_
		self.latlng = latlng_

	def __str__(self):
		return 'Intersection(%s, %d, %s, %d, %s)' % (self.froute1, self.froute1mofr, self.froute2, self.froute2mofr, str(self.latlng))

	def __repr__(self):
		return self.__str__()

class HalfIntersection:

	def __init__(self, froute_, mofr_, dir0_stoptag_, dir1_stoptag_, latlng_):
		self.froute = froute_
		self.mofr = mofr_
		self.dir0_stoptag = dir0_stoptag_
		self.dir1_stoptag = dir1_stoptag_
		self.latlng = latlng_

	def __str__(self):
		return 'HalfIntersection(%s, %d, %s, %s, %s)' % (self.froute, self.mofr, self.dir0_stoptag, self.dir1_stoptag, str(self.latlng))

	def __repr__(self):
		return self.__str__()

		

g_intersections = None

def get_intersections():
	global g_intersections
	if g_intersections is not None:
		return g_intersections
	else:
		mckey = mc.make_key('intersections')
		g_intersections = mc.client.get(mckey)
		if not g_intersections:
			g_intersections = get_intersections_impl()
			mc.client.set(mckey, g_intersections)
		return g_intersections

def get_intersections_impl():
	r = []
	for routei, route1 in enumerate(FUDGEROUTES[:]):
		for route2 in FUDGEROUTES[:][routei+1:]:
			ri1 = routeinfo(route1); ri2 = routeinfo(route2)
			new_intersections = []
			for route1_pt1, route1_pt2 in hopscotch(ri1.routepts(0)):
				for route2_pt1, route2_pt2 in hopscotch(ri2.routepts(0)):
					intersect_latlng = geom.get_line_segment_intersection(route1_pt1, route1_pt2, route2_pt1, route2_pt2)
					if intersect_latlng is not None:
						route1mofr = ri1.latlon_to_mofr(intersect_latlng); route2mofr = ri2.latlon_to_mofr(intersect_latlng)
						route1_dir0_stoptag = ri1.mofr_to_stop(0, route1mofr).stoptag
						route1_dir1_stoptag = ri1.mofr_to_stop(1, route1mofr).stoptag
						route2_dir0_stoptag = ri2.mofr_to_stop(0, route2mofr).stoptag
						route2_dir1_stoptag = ri2.mofr_to_stop(1, route2mofr).stoptag
						new_intersection = Intersection(route1, route1mofr, route2, route2mofr, 
								route1_dir0_stoptag, route1_dir1_stoptag, route2_dir0_stoptag, route2_dir1_stoptag, 
								intersect_latlng)
						if not new_intersections:
							new_intersections.append(new_intersection)
						else:
							nearest_old_intersection = min(new_intersections, key=lambda x: x.latlng.dist_m(new_intersection.latlng))
							dist_to_nearest_old_intersection = nearest_old_intersection.latlng.dist_m(new_intersection.latlng)
							if dist_to_nearest_old_intersection > 2000:
								new_intersections.append(new_intersection)
			r += new_intersections
	return r

def get_mofrndirnstoptag_to_halfintersection(froute_, mofr_):
	r = {}
	for i in get_intersections():
		if i.froute1 == froute_:
			direction = mofrs_to_dir(mofr_, i.froute1mofr)
			stoptag = (i.froute1_dir0_stoptag if direction == 0 else i.froute1_dir1_stoptag)
			r[(i.froute1mofr,direction,stoptag)] = HalfIntersection(i.froute2, i.froute2mofr, i.froute2_dir0_stoptag, i.froute2_dir1_stoptag, i.latlng)
		elif i.froute2 == froute_:
			direction = mofrs_to_dir(mofr_, i.froute2mofr)
			stoptag = (i.froute2_dir0_stoptag if direction == 0 else i.froute2_dir1_stoptag)
			r[(i.froute2mofr,direction,stoptag)] = HalfIntersection(i.froute1, i.froute1mofr, i.froute1_dir0_stoptag, i.froute1_dir1_stoptag, i.latlng)
	return r

if __name__ == '__main__':

	import pprint

	ri = routeinfo('queen')

	print ri.get_next_downstream_recorded_stop('10102')

