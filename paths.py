#!/usr/bin/python2.6

import sys, json, os.path
import vinfo, geom, routes, predictions, mc, c, snaptogrid
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
		start_stoptag_hints_, dest_stoptag_hints_ = None, None # TDR 
		ri = routes.get_routeinfo(froute_)
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
		return routes.get_routeinfo(self.froute).stoptag_to_mofr(self.dir, self.start_stoptag)

	@property
	def dest_mofr(self):
		assert self.mode == 'transit'
		return routes.get_routeinfo(self.froute).stoptag_to_mofr(self.dir, self.dest_stoptag)

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

def get_path_time_estimate_secs_2(path_):
	r = 0

	WALKING_SPEED_MPS = 5*(1000.0/(60*60))
	TRANSIT_SPEED_MPS = 20*(1000.0/(60*60))
	walking_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'walking')
	r += walking_dist_m/WALKING_SPEED_MPS

	transit_dist_m = sum(leg.dist_m for leg in path_ if leg.mode == 'transit')
	r += transit_dist_m/TRANSIT_SPEED_MPS

	t0 = now_em()
	sim_time = t0
	for leg in path_:
		if leg.mode == 'walking':
			sim_time += walking_dist_m/WALKING_SPEED_MPS
		else:
			for prediction in db.get_predictions(leg.froute, leg.start_stoptag, leg.dest_stoptag):
				if prediction.time_em > sim_time:
					sim_time = prediction.time_em
					break
			sim_time += leg.dist_m/TRANSIT_SPEED_MPS

	return int((sim_time - t0)/1000.0)

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
		ri = routes.get_routeinfo(froute)
		snap_result = ri.snaptogridcache.snap(latlng_, 1000)
		if snap_result is not None:
			pt_on_froute = snap_result[0]
			r.append((froute, ri.latlon_to_mofr(pt_on_froute)))
	return r
			
# return list of list of PathLeg.
def get_paths_by_latlngs(start_latlng_, dest_latlng_):
	r = []
	start_nearby_froutenmofrs = find_nearby_froutenmofrs(start_latlng_)
	dest_nearby_froutenmofrs = find_nearby_froutenmofrs(dest_latlng_)
	for start_froute, start_mofr in start_nearby_froutenmofrs:
		for dest_froute, dest_mofr in dest_nearby_froutenmofrs:
			for transit_path in get_transit_paths_by_mofrs(start_froute, start_mofr, None, dest_froute, dest_mofr, None, 4):
				start_walking_leg = PathLeg.make_walking_leg(start_latlng_, transit_path[0].start_latlng)
				dest_walking_leg = PathLeg.make_walking_leg(transit_path[-1].dest_latlng, dest_latlng_)
				total_path = [start_walking_leg] + transit_path + [dest_walking_leg]
				r.append(total_path)

	r.sort(key=get_path_rough_time_estimate_secs)
	r = r[:50]
	if 0: # TDR 
		import pprint 
		pprint.pprint(r)
	#r.sort(key=get_path_time_estimate_secs_2)
	#r = r[:15]

	return r


if __name__ == '__main__':

	import pprint

	#print len(get_paths('dundas', 1, 'dupont', 7000, 7))
	#pprint.pprint(get_paths('dundas', 400, 'dupont', 7000, 4))


	start_latlng = geom.LatLng(43.64603733174995, -79.42480845650334)
	dest_latlng = geom.LatLng(43.67044104830969, -79.40652651985783)

	#pprint.pprint(get_paths_by_latlngs(start_latlng, dest_latlng))
	get_paths_by_latlngs(start_latlng, dest_latlng)



