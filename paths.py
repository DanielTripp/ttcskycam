#!/usr/bin/python2.6

import sys, json, os.path, pprint, sqlite3
from collections import *
from lru_cache import lru_cache
import vinfo, geom, routes, predictions, mc, c, snaptogrid, traffic 
from misc import *

PATHS_DB_FILENAME = 'paths.sqlitedb'

g_dbconn = None

def init_dbconn():
	global g_dbconn
	if g_dbconn is None:
		g_dbconn = sqlite3.connect(PATHS_DB_FILENAME)

def get_polygon_from_file(filename_):
	with open(filename_) as fin:
		raw_latlngs = json.load(fin)
	r = []
	for raw_latlng in raw_latlngs:
		r.append(geom.LatLng(raw_latlng[0], raw_latlng[1]))
	return r
	
# return: list of geom.LatLng.  in order.  Last point is probably not the same as first point. 
@mc.decorate
def get_city_bounding_polygon():
	return get_polygon_from_file('paths_db_city_bounding_polygon.json')

@mc.decorate
def get_hires_bounding_polygon():
	return get_polygon_from_file('paths_db_hires_bounding_polygon.json')

@mc.decorate
def get_lores_bounding_polygons():
	with open('paths_db_lores_bounding_polygon.json') as fin:
		raw_polys = json.load(fin)
	r = []
	for raw_poly in raw_polys:
		poly = []
		for raw_latlng in raw_poly:
			poly.append(geom.LatLng(raw_latlng[0], raw_latlng[1]))
		r.append(poly)
	return r

class PathLeg:

	def __init__(self, mode_, start_latlng_, dest_latlng_, froute_, dir_, start_stoptag_, dest_stoptag_):
		assert mode_ in ('walking', 'transit')
		self.mode = mode_
		self.start_latlng = start_latlng_
		self.dest_latlng = dest_latlng_
		self.froute = froute_
		self.dir = dir_
		self.start_stoptag = start_stoptag_
		self.dest_stoptag = dest_stoptag_
		self._beeline_dist_m = None

	@classmethod
	def make_walking_leg(cls, start_latlng_, dest_latlng_):
		return cls('walking', start_latlng_, dest_latlng_, None, None, None, None)

	@classmethod
	def make_transit_leg(cls, froute_, start_mofr_, start_stoptag_hints_, dest_mofr_, dest_stoptag_hints_):
		ri = routes.routeinfo(froute_)
		direction = (0 if start_mofr_ < dest_mofr_ else 1)

		def get_stop(mofr_, stoptag_hints_):
			if stoptag_hints_ is not None and direction in stoptag_hints_:
				stoptag = stoptag_hints_[direction]
				return ri.get_stop(stoptag)
			else:
				return ri.mofr_to_stop(direction, mofr_)

		start_stop = get_stop(start_mofr_, start_stoptag_hints_)
		dest_stop = get_stop(dest_mofr_, dest_stoptag_hints_)
		return cls('transit', start_stop.latlng, dest_stop.latlng, froute_, direction, start_stop.stoptag, dest_stop.stoptag)

	def is_walking(self):
		return self.mode == 'walking'

	def is_transit(self):
		return self.mode == 'transit'

	@property
	def start_mofr(self):
		assert self.mode == 'transit'
		return routes.routeinfo(self.froute).stoptag_to_mofr(self.dir, self.start_stoptag)

	@property
	def dest_mofr(self):
		assert self.mode == 'transit'
		return routes.routeinfo(self.froute).stoptag_to_mofr(self.dir, self.dest_stoptag)

	@property
	def dist_m(self):
		if self.mode == 'walking':
			return int(self.start_latlng.dist_m(self.dest_latlng))
		else:
			return int(abs(self.dest_mofr-self.start_mofr))

	@property
	def beeline_dist_m(self):
		if self._beeline_dist_m == None:
			self._beeline_dist_m = self.start_latlng.dist_m(self.dest_latlng)
		return self._beeline_dist_m

	def __str__(self):
		dist_kms = self.dist_m/1000.0
		if self.mode == 'walking':
			return 'PathLeg(walking, for %.1f kms, from %s to %s)' % (dist_kms, self.start_latlng, self.dest_latlng)
		else:
			return 'PathLeg(transit, %s, dir=%d for %.1f kms, from stoptag %s %s to stoptag %s %s' \
					% (self.froute, self.dir, dist_kms, self.start_stoptag, self.start_latlng, self.dest_stoptag, self.dest_latlng)

	def __repr__(self):
		return self.__str__()

	def __eq__(self, other):
		return self.mode == other.mode \
				and self.start_latlng == other.start_latlng \
				and self.dest_latlng == other.dest_latlng \
				and self.froute == other.froute \
				and self.dir == other.dir \
				and self.start_stoptag == other.start_stoptag \
				and self.dest_stoptag == other.dest_stoptag 

def get_path_rough_time_estimate_secs(path_):
	r = 0

	WALKING_SPEED_MPS = 5*(1000.0/(60*60))
	walking_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'walking')
	r += walking_dist_m/WALKING_SPEED_MPS

	NON_SUBWAY_TRANSIT_SPEED_MPS = 15*(1000.0/(60*60))
	non_subway_transit_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'transit' and not routes.is_subway(leg.froute))
	r += non_subway_transit_dist_m/NON_SUBWAY_TRANSIT_SPEED_MPS

	SUBWAY_TRANSIT_SPEED_MPS = 45*(1000.0/(60*60))
	subway_transit_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'transit' and routes.is_subway(leg.froute))
	r += subway_transit_dist_m/SUBWAY_TRANSIT_SPEED_MPS

	# The initial wait for the first vehicle is not really a 'transfer' but it is the same as a transfer, for our purposes here. 
	num_transfers = len([leg for leg in path_ if leg.mode == 'transit']) 
	TRANSIT_TRANSFER_WAITING_TIME_SECS = 7*60
	r += num_transfers*TRANSIT_TRANSFER_WAITING_TIME_SECS

	return r

def get_path_est_arrival_time(t0_, path_):
	WALKING_SPEED_MPS = 5*(1000.0/(60*60))

	sim_time = t0_

	for leg in path_:
		#print leg
		if leg.mode == 'walking':
			sim_time += (leg.dist_m/WALKING_SPEED_MPS)*1000
		else:
			matched_prediction = None
			for prediction in predictions.get_extrapolated_predictions(leg.froute, leg.start_stoptag, leg.dest_stoptag, t0_):
				if prediction.time > sim_time:
					#print '---------- waited', em_to_str_hm(prediction.time - sim_time)
					sim_time = prediction.time
					matched_prediction = prediction
					break
			else:
				raise Exception('no prediction found for route %s stop %s to %s retrieved time = %s sim_time = %s' \
						% (leg.froute, leg.start_stoptag, leg.dest_stoptag, em_to_str(t0_), em_to_str(sim_time)))
			assert matched_prediction is not None
			leg_riding_time_secs = None
			predictions_at_dest_stop = predictions.get_extrapolated_predictions(leg.froute, leg.dest_stoptag, None, t0_)
			prediction_of_caught_vehicle_at_dest_stop = first(predictions_at_dest_stop, lambda p: p.vehicle_id == matched_prediction.vehicle_id)
			if prediction_of_caught_vehicle_at_dest_stop is not None:
				#printerr('-------- using predictions instead of traffic for travel time')
				sim_time = prediction_of_caught_vehicle_at_dest_stop.time
			else:
				leg_riding_time_secs = traffic.get_est_riding_time_secs(leg.froute, leg.start_mofr, leg.dest_mofr, True, t0_)
				if leg_riding_time_secs is None:
					raise Exception()
				sim_time += leg_riding_time_secs*1000

	return sim_time

def get_est_arrival_time(froute_, start_stoptag_, dest_stoptag_, time_retrieved_, sim_time_, ride_time_est_style_):
	assert is_valid_time_em(time_retrieved_) and is_valid_time_em(sim_time_) and ride_time_est_style_ in ('predictions', 'traffic', 'schedule')
	assert time_retrieved_ <= sim_time_
	ri = routes.routeinfo(froute_)
	assert (ri.get_stop(start_stoptag_).direction == ri.get_stop(dest_stoptag_).direction) and (start_stoptag_ != dest_stoptag_)
	assert mofrs_to_dir(ri.get_stop(start_stoptag_).mofr, ri.get_stop(dest_stoptag_).mofr) == ri.get_stop(start_stoptag_).direction

	for prediction in predictions.get_extrapolated_predictions(froute_, start_stoptag_, dest_stoptag_, time_retrieved_):
		if prediction.time >= sim_time_:
			caught_prediction = prediction
			break
	else:
		raise Exception('No prediction found at starting stop')

	if ride_time_est_style_ == 'predictions':
		predictions_at_dest_stop = predictions.get_extrapolated_predictions(froute_, dest_stoptag_, None, time_retrieved_)
		prediction_of_caught_vehicle_at_dest_stop = first(predictions_at_dest_stop, lambda p: p.vehicle_id == caught_prediction.vehicle_id)
		if prediction_of_caught_vehicle_at_dest_stop is not None:
			return {'time_caught': caught_prediction.time, 'time_arrived': prediction_of_caught_vehicle_at_dest_stop.time}
		else:
			return None
	elif ride_time_est_style_ == 'traffic':
		start_mofr = ri.get_stop(start_stoptag_).mofr; dest_mofr = ri.get_stop(dest_stoptag_).mofr;
		ride_time_secs = traffic.get_est_riding_time_secs(froute_, start_mofr, dest_mofr, True, time_retrieved_)
		if ride_time_secs is None:
			return None
		return {'time_caught': caught_prediction.time, 'time_arrived': caught_prediction.time + ride_time_secs*1000}
	elif ride_time_est_style_ == 'schedule':
		ride_time = routes.schedule(froute_).get_ride_time(start_stoptag_, dest_stoptag_, caught_prediction.time)
		return {'time_caught': caught_prediction.time, 'time_arrived': caught_prediction.time + ride_time}
	else:
		raise Exception()



# start_stoptag_hints_ and dest_stoptag_hints_ can be None, that is okay.  These arguments exist as an optimization 
# (within PathLeg.make_transit_leg()) so that mofr_to_stop() doesn't need to be called in many of these recursive 
# cases where we already know the stoptag, because we just got the mofr from an intersection definition. 
# 
# return list of list of PathLeg.
def get_transit_paths_by_mofrs(start_froute_, start_mofr_, start_stoptag_hints_, dest_froute_, dest_mofr_, dest_stoptag_hints_, \
		max_transit_routes_, max_dist_m_, visited_froutes_=set()):
	assert max_transit_routes_ >= 1
	visited_froutes = visited_froutes_.copy()
	visited_froutes.add(start_froute_)

	start_latlng = routes.mofr_to_latlon(start_froute_, start_mofr_, 0) # TDR ?? 
	dest_latlng = routes.mofr_to_latlon(dest_froute_, dest_mofr_, 0) # TDR ?? 
	r = []
	if start_froute_ == dest_froute_:
		new_path = [PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, dest_mofr_, dest_stoptag_hints_)]
		#if get_path_legs_beeline_dist_m(new_path) < max_dist_m_:
		if 1: # TDR 
			r.append(new_path)
	else:
		for mofrndirnstoptag, halfint in routes.get_mofrndirnstoptag_to_halfintersection(start_froute_, start_mofr_).iteritems():
			startroutes_crossmofr, direction, startroutes_crossstoptag = mofrndirnstoptag
			if halfint.froute in visited_froutes:
				continue
			if halfint.froute == dest_froute_:
				leg1_dest_stoptag_hints = {direction: startroutes_crossstoptag}
				leg2_start_stoptag_hints = {0: halfint.dir0_stoptag, 1: halfint.dir1_stoptag}
				new_path = [PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, startroutes_crossmofr, leg1_dest_stoptag_hints), 
						PathLeg.make_transit_leg(dest_froute_, halfint.mofr, leg2_start_stoptag_hints, dest_mofr_, dest_stoptag_hints_)]
				#if get_path_legs_beeline_dist_m(new_path) < max_dist_m_:
				#if not path_contains_wrong_way_legs(new_path, start_latlng, dest_latlng):
				if 1: # TDR 
					r.append(new_path)
			else:
				if max_transit_routes_ > 1:
					halfint_stoptag_hints = {0: halfint.dir0_stoptag, 1: halfint.dir1_stoptag}
					for subpath in get_transit_paths_by_mofrs(halfint.froute, halfint.mofr, halfint_stoptag_hints, \
								dest_froute_, dest_mofr_, dest_stoptag_hints_, \
								max_transit_routes_-1, max_dist_m_, visited_froutes):
						num_transit_routes_in_subpath = len(uniq([x.froute for x in subpath]))
						if num_transit_routes_in_subpath < max_transit_routes_+1:
							new_leg = PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, \
									startroutes_crossmofr, {direction: startroutes_crossstoptag})
							new_path = [new_leg] + subpath
							#if get_path_legs_beeline_dist_m(new_path) < max_dist_m_:
							#if not path_contains_wrong_way_legs(new_path, start_latlng, dest_latlng):
							if 1: # TDR 
								r.append(new_path)
	for path in r:
		filter_in_place(path, lambda leg: leg.start_stoptag != leg.dest_stoptag)
	filter_in_place(r, lambda path: len(path) > 0)
	#start_latlng = routes.mofr_to_latlon(start_froute_, start_mofr_, 0)  # TDR all this? 
	#dest_latlng = routes.mofr_to_latlon(dest_froute_, dest_mofr_, 0)
	#beeline_dist_start_to_dest_m = start_latlng.dist_m(dest_latlng)
	#filter_in_place(r, lambda path: get_path_legs_beeline_dist_m(path) < 3*beeline_dist_start_to_dest_m)
	return r

def path_contains_wrong_way_legs(path_, start_latlng_, dest_latlng_):
	assert isinstance(path_, Sequence) and all(isinstance(leg, PathLeg) for leg in path_)
	start_dest_heading = start_latlng_.heading(dest_latlng_)
	for leg in path_:
		leg_heading = leg.start_latlng.heading(leg.dest_latlng)
		if geom.diff_headings(leg_heading, start_dest_heading) > 90:
			return True
	return False

def get_path_legs_beeline_dist_m(path_):
	assert isinstance(path_, Sequence) and all(isinstance(leg, PathLeg) for leg in path_)
	r = 0.0
	for leg in path_:
		r += leg.beeline_dist_m
	return r

def find_nearby_froutenmofrs(latlng_, radius_):
	r = []
	for froute in routes.FUDGEROUTES:
		ri = routes.routeinfo(froute)
		snap_result = ri.snaptogridcache.snap(latlng_, radius_)
		if snap_result is not None:
			pt_on_froute = snap_result[0]
			r.append((froute, ri.latlon_to_mofr(pt_on_froute)))
	return r
			
# return list of list of PathLeg.
def get_paths_by_latlngs(start_latlng_, dest_latlng_, radius_m_=1000):
	paths = []
	max_dist_m = start_latlng_.dist_m(dest_latlng_)*3
	start_nearby_froutenmofrs = find_nearby_froutenmofrs(start_latlng_, radius_m_)
	dest_nearby_froutenmofrs = find_nearby_froutenmofrs(dest_latlng_, radius_m_)
	for start_froute, start_mofr in start_nearby_froutenmofrs:
		for dest_froute, dest_mofr in dest_nearby_froutenmofrs:
			for transit_path in get_transit_paths_by_mofrs(start_froute, start_mofr, None, dest_froute, dest_mofr, None, 4, max_dist_m):
				start_walking_leg = PathLeg.make_walking_leg(start_latlng_, transit_path[0].start_latlng)
				dest_walking_leg = PathLeg.make_walking_leg(transit_path[-1].dest_latlng, dest_latlng_)
				total_path = [start_walking_leg] + transit_path + [dest_walking_leg]
				paths.append(total_path)

	paths = filter_paths(paths)

	return paths

def filter_paths(paths_):
	
	if len(paths_) == 0:
		return []
	paths = paths_
	for path in paths:
		remove_too_short_transit_legs(path)
	path_n_time_estimates = [(path, get_path_rough_time_estimate_secs(path)) for path in paths]
	path_n_time_estimates.sort(key=lambda x: x[1])
	remove_consecutive_duplicates(path_n_time_estimates)
	fastest_time_estimate = path_n_time_estimates[0][1]
	max_acceptable_time_estimate = fastest_time_estimate*1.33

	filter_in_place(path_n_time_estimates, lambda x: x[1] < max_acceptable_time_estimate)
	paths = [x[0] for x in path_n_time_estimates]

	paths = paths[:20]

	return paths

def remove_too_short_transit_legs(path_):
	for leg in path_:
		if leg.mode == 'transit' and leg.dist_m < 500:
			leg.mode = 'walking'
			leg.froute = None
			leg.dir = None
			leg.start_stoptag = None
			leg.dest_stoptag = None

	coalesce_consecutive_walking_legs(path_)

def coalesce_consecutive_walking_legs(path_):
	i = 0
	while i < len(path_)-1:
		leg1 = path_[i]
		leg2 = path_[i+1]
		if leg1.mode == 'walking' and leg2.mode == 'walking':
			leg1.dest_latlng = leg2.dest_latlng
			del path_[i+1]
		else:
			i += 1


# Chosen because these form about a 1-km square at Bloor and Dufferin.  Made sense at the time. 
LATSTEP = 0.0089983; LNGSTEP = 0.0124379

# Grid squares are offset from a point that has no large importance, it just makes for more easily
# readable values during debugging:
LATREF = 43.62696696859263; LNGREF = -79.4579391022553

def lat_to_gridlat(lat_):
	return fdiv(lat_ - LATREF, LATSTEP)

def gridlat_to_lat(gridlat_):
	return gridlat_*LATSTEP + LATREF

def lng_to_gridlng(lng_):
	return fdiv(lng_ - LNGREF, LNGSTEP)

def gridlng_to_lng(gridlng_):
	return gridlng_*LNGSTEP + LNGREF

class PathGridSquare(object):

	def __init__(self, arg_):
		if isinstance(arg_, geom.LatLng):
			self.gridlat = lat_to_gridlat(arg_.lat)
			self.gridlng = lng_to_gridlng(arg_.lng)
			if self.should_be_hires():
				midpt_lat = avg(gridlat_to_lat(self.gridlat), gridlat_to_lat(self.gridlat+1))
				midpt_lng = avg(gridlng_to_lng(self.gridlng), gridlng_to_lng(self.gridlng+1))
				north = arg_.lat > midpt_lat
				east = arg_.lng > midpt_lng
				self.hires_quadrant = {(True,True): 1, (True,False):2, (False,False):3, (False,True):4}[(north,east)]
			else:
				self.hires_quadrant = None
		else:
			assert isinstance(arg_[0], int) and isinstance(arg_[1], int)
			self.gridlat = arg_[0]
			self.gridlng = arg_[1]
			self.hires_quadrant = None

	def should_be_hires(self):
		sw_latlng = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))
		for lat in (sw_latlng.lat, sw_latlng.lat+LATSTEP):
			for lng in (sw_latlng.lng, sw_latlng.lng+LNGSTEP):
				corner_latlng = geom.LatLng(lat, lng)
				if corner_latlng.inside_polygon(get_hires_bounding_polygon()):
					return True
		return False

	def __eq__(self, other):
		return (self.gridlat == other.gridlat) and (self.gridlng == other.gridlng) and (self.hires_quadrant == other.hires_quadrant)

	def __hash__(self):
		return self.gridlat + self.gridlng + self.hires_quadrant

	def __str__(self):
		r = '(%d,%d)' % (self.gridlat, self.gridlng)
		if self.hires_quadrant is not None:
			r += '|'+str(self.hires_quadrant)
		return r

	def __repr__(self):
		return self.__str__()

	def latlng(self):
		return self.sw_latlng()

	def ne_latlng(self):
		return self.corner_latlng(1)

	def nw_latlng(self):
		return self.corner_latlng(2)

	def sw_latlng(self):
		return self.corner_latlng(3)

	def se_latlng(self):
		return self.corner_latlng(4)

	def corner_latlngs(self):
		return [self.corner_latlng(corner_quadrant) for corner_quadrant in (1, 2, 3, 4)]

	def corner_latlng(self, corner_quadrant_):
		assert corner_quadrant_ in (1, 2, 3, 4)
		r = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng)) # r starts off SW of large grid square 

		if self.hires_quadrant in (1, 2):
			r.lat += LATSTEP/2
		if self.hires_quadrant in (1, 4):
			r.lng += LNGSTEP/2
		# r is now SW of hires grid square (if applicable).

		if self.hires_quadrant is None:
			latside = LATSTEP; lngside = LNGSTEP
		else:
			latside = LATSTEP/2; lngside = LNGSTEP/2
		if corner_quadrant_ in (1, 2):
			r.lat += latside
		if corner_quadrant_ in (1, 4):
			r.lng += lngside

		return r

	def midpt_latlng(self):
		return self.sw_latlng().avg(self.ne_latlng())

	# ignores hires quadrants. 
	def is_adjacent(self, other_):
		assert isinstance(other_, PathGridSquare)
		return (self != other_) and (abs(self.gridlat - other_.gridlat) <= 1) and (abs(self.gridlng - other_.gridlng) <= 1)

def get_path_froutendirs_by_latlng(orig_latlng_, dest_latlng_):
	assert isinstance(orig_latlng_, geom.LatLng) and isinstance(dest_latlng_, geom.LatLng)
	return get_path_froutendirs_by_pathgridsquare(PathGridSquare(orig_latlng_), PathGridSquare(dest_latlng_), 
			orig_latlng_.heading(dest_latlng_))

#@mc.decorate
def get_path_froutendirs_by_pathgridsquare(orig_pathgridsquare_, dest_pathgridsquare_, heading_):
	assert isinstance(orig_pathgridsquare_, PathGridSquare) and isinstance(dest_pathgridsquare_, PathGridSquare)
	if (orig_pathgridsquare_ == dest_pathgridsquare_) or orig_pathgridsquare_.is_adjacent(dest_pathgridsquare_):
		return get_path_froutendirs_by_pathgridsquare_near(orig_pathgridsquare_, dest_pathgridsquare_, heading_)
	else:
		return get_path_froutendirs_by_pathgridsquare_far(orig_pathgridsquare_, dest_pathgridsquare_)

def get_path_froutendirs_by_pathgridsquare_near(orig_pathgridsquare_, dest_pathgridsquare_, heading_):
	sw, ne = get_path_froutendirs_by_pathgridsquare_near_bounding_box_latlngs(orig_pathgridsquare_, dest_pathgridsquare_)
	return routes.get_fudgeroutes_for_map_bounds(sw, ne, heading_, 99999)

def get_path_froutendirs_by_pathgridsquare_near_bounding_box_latlngs(orig_pathgridsquare_, dest_pathgridsquare_):
	def to_fake_gridsquare(sq__):
		r = [sq__.gridlat*2, sq__.gridlng*2]
		if sq__.hires_quadrant in (1, 2):
			r[0] += 1
		if sq__.hires_quadrant in (1, 4):
			r[1] += 1
		return r
	o = to_fake_gridsquare(orig_pathgridsquare_); d = to_fake_gridsquare(dest_pathgridsquare_)
	sw = (min(o[0], d[0])-1, min(o[1], d[1])-1)
	ne = (max(o[0], d[0])+1, max(o[1], d[1])+1)
	def from_fake_gridsquare(fake__, round_high__):
		r = PathGridSquare((fake__[0]/2, fake__[1]/2))
		latmod = fake__[0] % 2; lngmod = fake__[1] % 2
		if latmod and lngmod:
			r.hires_quadrant = 1
		elif latmod and not lngmod:
			r.hires_quadrant = 2
		elif not latmod and not lngmod:
			r.hires_quadrant = 3
		else:
			r.hires_quadrant = 4
		if not r.should_be_hires():
			if round_high__:
				if r.hires_quadrant in (1, 2):
					r.gridlat += 1
				if r.hires_quadrant in (1, 4):
					r.gridlng += 1
			r.hires_quadrant = None
		return r 
	sw_square = from_fake_gridsquare(sw, False)
	ne_square = from_fake_gridsquare(ne, True)
	return (sw_square.sw_latlng(), ne_square.ne_latlng())

def get_path_froutendirs_by_pathgridsquare_far(orig_pathgridsquare_, dest_pathgridsquare_):
	def get_max_midpt_to_corner_dist_m(gridsquare__):
		dist_midpt_to_sw = gridsquare__.midpt_latlng().dist_m(gridsquare__.sw_latlng())
		dist_midpt_to_ne = gridsquare__.midpt_latlng().dist_m(gridsquare__.ne_latlng())
		return max(dist_midpt_to_sw, dist_midpt_to_ne)
	radius_m = int(max(get_max_midpt_to_corner_dist_m(orig_pathgridsquare_), get_max_midpt_to_corner_dist_m(dest_pathgridsquare_)))
	radius_m += 500
	paths = get_paths_by_latlngs(orig_pathgridsquare_.midpt_latlng(), dest_pathgridsquare_.midpt_latlng(), radius_m)
	if len(paths) == 0:
		return []
	if 0: # TDR
		printerr('------------------')
		for path in paths:
			printerr('minutes: %.1f' % (get_path_rough_time_estimate_secs(path)/60.0))
			for leg in path:
				printerr(leg)
			printerr('---')
	r = []
	froutendirs_to_score = defaultdict(lambda: 0)
	for pathi, path in enumerate(paths):
		for leg in [x for x in path if x.mode == 'transit']:
			if not [x for x in r if x[0] == leg.froute]:
				froutendirs_to_score[(leg.froute, leg.dir)] += len(paths)-pathi
	all_froutendirs = [x[0] for x in sorted(froutendirs_to_score.items(), key=lambda x: x[1], reverse=True)]
	for i in range(len(all_froutendirs)-1, -1, -1):
		froutendir = all_froutendirs[i]
		froutenoppositedir = (froutendir[0], 1 if froutendir[1] == 0 else 0)
		if froutenoppositedir in all_froutendirs[:i]:
			all_froutendirs.pop(i)
	fastest_path_froutendirs = [(leg.froute, leg.dir) for leg in paths[0] if leg.mode == 'transit']
	return (fastest_path_froutendirs, all_froutendirs)

@mc.decorate
def get_pathgridsquares_lores():
	city_bounding_polygon = get_city_bounding_polygon()
	city_sw_latlng = geom.LatLng(min(pt.lat for pt in city_bounding_polygon), min(pt.lng for pt in city_bounding_polygon))
	city_ne_latlng = geom.LatLng(max(pt.lat for pt in city_bounding_polygon), max(pt.lng for pt in city_bounding_polygon))
	sw_pathgridsquare = PathGridSquare(city_sw_latlng); ne_pathgridsquare = PathGridSquare(city_ne_latlng)
	r = []
	for gridlat in range(sw_pathgridsquare.gridlat, ne_pathgridsquare.gridlat+1, 1):
		for gridlng in range(sw_pathgridsquare.gridlng, ne_pathgridsquare.gridlng+1, 1):
			sq = PathGridSquare((gridlat, gridlng))
			if any(latlng.inside_polygon(city_bounding_polygon) for latlng in sq.corner_latlngs()):
				r.append(sq)
	return r

def square_key(gridsq_, quadrant_):
	assert isinstance(gridsq_, PathGridSquare) and quadrant_ in (1, 2, 3, 4, None)
	return '%d,%d%s' % (gridsq_.gridlat, gridsq_.gridlng, ('' if quadrant_ is None else '|'+str(quadrant_)))

@mc.decorate
def pathgridsquares_bothres():
	r = []
	hires_bounding_polygon = get_hires_bounding_polygon()
	for pathgridsquare in get_pathgridsquares_lores():
		if any(latlng.inside_polygon(hires_bounding_polygon) for latlng in pathgridsquare.corner_latlngs()):
			for quadrant in (1, 2, 3, 4):
				r.append((pathgridsquare, quadrant))
		else:
			r.append((pathgridsquare, None))
	return r

@mc.decorate
def pathgridsquares_bothres_ew():
	r = []
	hires_bounding_polygon = get_hires_bounding_polygon()
	lores_bounding_polygons = get_lores_bounding_polygons()
	for square in get_pathgridsquares_lores():
		if any(square.midpt_latlng().inside_polygon(poly) for poly in lores_bounding_polygons):
			for part in ('e', 'w'):
				r.append((square, part))
		elif any(latlng.inside_polygon(hires_bounding_polygon) for latlng in square.corner_latlngs()):
			for part in range(16):
				r.append((square, part))
		else:
			for part in ('a', 'b', 'c', 'd'):
				r.append((square, part))
	return r

def orig_dest_latlngs_and_key_bothres_gen():
	for orig_square, orig_quadrant in pathgridsquares_bothres():
		for dest_square, dest_quadrant in pathgridsquares_bothres():
			if (orig_square, orig_quadrant) != (dest_square, dest_quadrant):
				orig_latlng = orig_square.midpt_latlng(orig_quadrant)
				dest_latlng = dest_square.midpt_latlng(dest_quadrant)
				orig_key = square_key(orig_square, orig_quadrant)
				dest_key = square_key(dest_square, dest_quadrant)
				yield (orig_latlng, dest_latlng, '%s %s' % (orig_key, dest_key))

def get_pathgridsquare(latlng_):
	return str(PathGridSquare(latlng_))

def build_db_main():
	init_dbconn()
	g_dbconn.execute('create table t (key text unique, value text)')
	for i, (orig_latlng, dest_latlng, orig_dest_key) in enumerate(orig_dest_latlngs_and_key_bothres_gen()):
		val = None
		g_dbconn.execute('insert into t values (?, ?)', [orig_dest_key, ])
		#if i % 10000 == 0:
		if 1:
			g_dbconn.commit()
			print i



if __name__ == '__main__':

	def approx_route_combos(orig_pathgridsquare_, dest_pathgridsquare_):
		def get_max_midpt_to_corner_dist_m(gridsquare__):
			dist_midpt_to_sw = gridsquare__.latlng().dist_m(gridsquare__.midpt_latlng())
			ne = PathGridSquare((gridsquare__.gridlat+1, gridsquare__.gridlng+1))
			dist_midpt_to_ne = ne.latlng().dist_m(gridsquare__.midpt_latlng())
			return max(dist_midpt_to_sw, dist_midpt_to_ne)
		radius_m = int(max(get_max_midpt_to_corner_dist_m(orig_pathgridsquare_), get_max_midpt_to_corner_dist_m(dest_pathgridsquare_)))
		radius_m += 500
		o = len(find_nearby_froutenmofrs(orig_pathgridsquare_.midpt_latlng(), radius_m))
		d = len(find_nearby_froutenmofrs(dest_pathgridsquare_.midpt_latlng(), radius_m))
		return o*d

	def intWithCommas(x):
			if type(x) not in [type(0), type(0L)]:
					raise TypeError("Parameter must be an integer.")
			if x < 0:
					return '-' + intWithCommas(-x)
			result = ''
			while x >= 1000:
					x, r = divmod(x, 1000)
					result = ",%03d%s" % (r, result)
			return "%d%s" % (x, result)


	def num_combos():
		r = 0
		for sq1, quad1 in pathgridsquares_bothres():
			for sq2, quad2 in pathgridsquares_bothres():
				if (sq1, quad1) != (sq2, quad2):
					r += 1
		return r


	if 0:
		#o = PathGridSquare(geom.LatLng(43.671993112040994, -79.54188151558537))
		#d = PathGridSquare(geom.LatLng(43.73751562846032, -79.28576274117131))
		o = PathGridSquare(geom.LatLng(43.64255915003969, -79.43021578987737))
		#d = PathGridSquare(geom.LatLng(43.66690219292239, -79.40558238228459))
		d = PathGridSquare(geom.LatLng(43.695331309135526, -79.4498710175385)) # way up dufferin 
		t0 = time.time()
		print get_path_froutendirs_by_pathgridsquare_far(o, d)
		print (time.time() - t0)
		print approx_route_combos(o, d)

	
	numcombos_to_count = defaultdict(lambda: 0)
	for i, (origsquare, origquadrant) in enumerate(pathgridsquares_bothres()):
		for j, (destsquare, destquadrant) in enumerate(pathgridsquares_bothres()):
			if (origsquare, origquadrant) != (destsquare, destquadrant):
				print '---'
				print i, j
				#print origsquare, origquadrant, '->', destsquare, destquadrant 
				num_combos = approx_route_combos(origsquare, destsquare)
				if 0:
					t0 = time.time()
					get_path_froutendirs_by_pathgridsquare_far(origsquare, destsquare)
					print 'finding paths took %.1f seconds' % ((time.time() - t0))
					print 'nearby route combos: %d' % num_combos
				numcombos_to_count[num_combos] += 1


	if 0:
		nc = num_combos()
		print intWithCommas(nc)
		SECONDS_PER_COMBO = 5
		print 'hours: %.1f' % ((nc*SECONDS_PER_COMBO)/(60.0*60.0),)
		print 'days: %.1f' % ((nc*SECONDS_PER_COMBO)/(60.0*60.0*24),)





