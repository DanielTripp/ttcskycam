#!/usr/bin/python2.6

import sys, json, os.path, pprint
import vinfo, geom, routes, predictions, mc, c, snaptogrid, traffic 
from misc import *

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

	def __str__(self):
		dist_kms = self.dist_m/1000.0
		if self.mode == 'walking':
			return 'PathLeg(walking, for %.1f kms, from %s to %s)' % (dist_kms, self.start_latlng, self.dest_latlng)
		else:
			return 'PathLeg(transit, %s, dir=%d for %.1f kms, from stoptag %s %s to stoptag %s %s' \
					% (self.froute, self.dir, dist_kms, self.start_stoptag, self.start_latlng, self.dest_stoptag, self.dest_latlng)

	def __repr__(self):
		return self.__str__()
		

def get_path_rough_time_estimate_secs(path_):
	r = 0

	WALKING_SPEED_MPS = 5*(1000.0/(60*60))
	walking_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'walking')
	r += walking_dist_m/WALKING_SPEED_MPS

	TRANSIT_SPEED_MPS = 20*(1000.0/(60*60))
	transit_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'transit')
	r += transit_dist_m/TRANSIT_SPEED_MPS

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
			return prediction_of_caught_vehicle_at_dest_stop.time
		else:
			return None
	elif ride_time_est_style_ == 'traffic':
		start_mofr = ri.get_stop(start_stoptag_).mofr; dest_mofr = ri.get_stop(dest_stoptag_).mofr;
		ride_time_secs = traffic.get_est_riding_time_secs(froute_, start_mofr, dest_mofr, True, time_retrieved_)
		if ride_time_secs is None:
			return None
		return caught_prediction.time + ride_time_secs*1000
	elif ride_time_est_style_ == 'schedule':
		ride_time = routes.schedule(froute_).get_ride_time(start_stoptag_, dest_stoptag_, caught_prediction.time)
		return caught_prediction.time + ride_time
	else:
		raise Exception()



# start_stoptag_hints_ and dest_stoptag_hints_ can be None, that is okay.  These arguments exist as an optimization 
# (within PathLeg.make_transit_leg()) so that mofr_to_stop() doesn't need to be called in many of these recursive 
# cases where we already know the stoptag, because we just got the mofr from an intersection definition. 
# 
# return list of list of PathLeg.
def get_transit_paths_by_mofrs(start_froute_, start_mofr_, start_stoptag_hints_, dest_froute_, dest_mofr_, dest_stoptag_hints_, \
		max_transit_routes_, visited_froutes_=set()):
	assert max_transit_routes_ >= 1
	visited_froutes = visited_froutes_.copy()
	visited_froutes.add(start_froute_)

	r = []
	if start_froute_ == dest_froute_:
		r.append(PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, dest_mofr_, dest_stoptag_hints_))
	for mofrndirnstoptag, halfint in routes.get_mofrndirnstoptag_to_halfintersection(start_froute_, start_mofr_).iteritems():
		startroutes_crossmofr, direction, startroutes_crossstoptag = mofrndirnstoptag
		if halfint.froute in visited_froutes:
			continue
		if halfint.froute == dest_froute_:
			leg1_dest_stoptag_hints = {direction: startroutes_crossstoptag}
			leg2_start_stoptag_hints = {0: halfint.dir0_stoptag, 1: halfint.dir1_stoptag}
			r.append([PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, startroutes_crossmofr, leg1_dest_stoptag_hints), 
					PathLeg.make_transit_leg(dest_froute_, halfint.mofr, leg2_start_stoptag_hints, dest_mofr_, dest_stoptag_hints_)])
		else:
			if max_transit_routes_ > 1:
				halfint_stoptag_hints = {0: halfint.dir0_stoptag, 1: halfint.dir1_stoptag}
				for subpath in get_transit_paths_by_mofrs(halfint.froute, halfint.mofr, halfint_stoptag_hints, \
							dest_froute_, dest_mofr_, dest_stoptag_hints_, \
							max_transit_routes_-1, visited_froutes):
					num_transit_routes_in_subpath = len(uniq([x.froute for x in subpath]))
					if num_transit_routes_in_subpath < max_transit_routes_+1:
						new_leg = PathLeg.make_transit_leg(start_froute_, start_mofr_, start_stoptag_hints_, \
								startroutes_crossmofr, {direction: startroutes_crossstoptag})
						r.append([new_leg] + subpath)
	return r

def find_nearby_froutenmofrs(latlng_):
	r = []
	for froute in routes.FUDGEROUTES:
		ri = routes.routeinfo(froute)
		snap_result = ri.snaptogridcache.snap(latlng_, 1000)
		if snap_result is not None:
			pt_on_froute = snap_result[0]
			r.append((froute, ri.latlon_to_mofr(pt_on_froute)))
	return r
			
# return list of list of PathLeg.
def get_pathnarrivaltime_by_latlngs(start_latlng_, dest_latlng_, time_):
	time_ = massage_time_arg(time_)
	paths = []
	start_nearby_froutenmofrs = find_nearby_froutenmofrs(start_latlng_)
	dest_nearby_froutenmofrs = find_nearby_froutenmofrs(dest_latlng_)
	for start_froute, start_mofr in start_nearby_froutenmofrs:
		for dest_froute, dest_mofr in dest_nearby_froutenmofrs:
			for transit_path in get_transit_paths_by_mofrs(start_froute, start_mofr, None, dest_froute, dest_mofr, None, 4):
				start_walking_leg = PathLeg.make_walking_leg(start_latlng_, transit_path[0].start_latlng)
				dest_walking_leg = PathLeg.make_walking_leg(transit_path[-1].dest_latlng, dest_latlng_)
				total_path = [start_walking_leg] + transit_path + [dest_walking_leg]
				paths.append(total_path)

	paths.sort(key=get_path_rough_time_estimate_secs)
	paths = paths[:5]
	pathnarrivaltimes = []
	for path in paths:
		pathnarrivaltimes.append((path, get_path_est_arrival_time(time_, path)))
	pathnarrivaltimes.sort(key=lambda x: x[1])

	return pathnarrivaltimes


if __name__ == '__main__':

	import pprint

	#print len(get_paths('dundas', 1, 'dupont', 7000, 7))
	#pprint.pprint(get_paths('dundas', 400, 'dupont', 7000, 4))


	start_latlng = geom.LatLng(43.64603733174995, -79.42480845650334)
	dest_latlng = geom.LatLng(43.67044104830969, -79.40652651985783)

	#pprint.pprint(get_pathnarrivaltime_by_latlngs(start_latlng, dest_latlng, '2013-01-05 18:00'))
	for path, arrivaltime in get_pathnarrivaltime_by_latlngs(start_latlng, dest_latlng, '2013-01-07 13:45'):
		print 'arrival time:', em_to_str(arrivaltime)
		pprint.pprint(path)
		print
	


