#!/usr/bin/python2.6

from collections import defaultdict
import vinfo, db, routes, geom, mc, yards, c
from misc import *

with open('MOFR_STEP') as f:
	MOFR_STEP = int(f.read().strip())

TIME_WINDOW_MINUTES = 30

def get_recent_vehicle_locations(fudgeroute_, dir_, current_, time_, log_=False):
	time_ = massage_time_arg(time_, 15*1000)
	mckey = mc.make_key('get_recent_vehicle_locations', fudgeroute_, dir_, current_, time_)
	r = mc.client.get(mckey)
	if r:
		if log_: printerr('Found in memcache.')
	else:
		if log_: printerr('Not found in memcache.')
		r = get_recent_vehicle_locations_impl(fudgeroute_, dir_, current_, time_, log_)
		mc.client.set(mckey, r)
	return r

def massage_time_arg(time_, now_round_step_millis_):
	if isinstance(time_, str):
		r = str_to_em(time_)
	elif time_==0:
		r = now_em()
	else:
		r = time_
	return round_down(r, now_round_step_millis_)

def get_recent_vehicle_locations_impl(fudgeroute_, dir_, current_, time_, log_=False):
	return db.get_recent_vehicle_locations(fudgeroute_, TIME_WINDOW_MINUTES, dir_, current_, time_window_end_=time_, log_=log_)

# returns: key: vid.  value: list of list of VehicleInfo
# second list - these are 'stretches' of increasing (or decreasing) mofr.  Doing it this way so that if the database gives us a
# single vehicle that say goes from mofr = 1000 to mofr = 1500 (over however many VehicleInfo objects), then goes AWOL for a while,
# then reappears and goes from mofr = 500 to mofr = 1200 (i.e. it doubled back and did part of the same route again), then we can
# handle that.
# The above case is in my opinion only moderately important to handle.  Our traffic-determinging interpolating code needs monotonic
# vis like this, but we could get them another way eg. removing the earlier stretch, because it's probably not very crucial
# to the result anyway.  But the more important case to handle is a buggy GPS or mofr case where a vehicle only appears to doubles back
# (even a little bit) and thus appears to be going in a different direction for a while.  I wouldn't want a case like that to result in
# the discarding of the more important stretch, and I don't want to write code that makes a judgement call about how many metres or
# for how many readings should a vehicle have to go in an opposite direction before we believe that it is really going in that direction.
# So I do it by stretches, like this.
# Example: routes 501/301, westbound, vid = 1531, 2012-10-30 00:45 to 01:15.  The vehicle goes west from 00:45 to 00:54.  Fine.
# Then it also appears to go west briefly between 01:07 and 01:08, but that's a fluke of the mofr reading as it gets bask onto queen
# there.  Then it stands still for a few minutes there.  Then it continues eastward.  I don't want that to mess things up.
# TODO: improve this comment.
def get_vid_to_vises_from_db_for_traffic(fudgeroute_name_, dir_, time_, log_=False):
	r = db.get_vid_to_vises(fudgeroute_name_, dir_, TIME_WINDOW_MINUTES, time_, True, False, log_=log_)
	for vid, vises in r.items():
		for vis in vises:
			filter_in_place(vis, lambda vi: vi.mofr != -1)
	return r

def between(bound1_, value_, bound2_):
	return (bound1_ < value_ < bound2_) or (bound1_ > value_ > bound2_) 

# time_ - 0 for now 
# 
# returns elem 0: visuals list - [[timestamp, vi dict, vi dict, ...], ...] 
#         elem 1: speed map - {mofr1: {'kmph': kmph, 'weight': weight}, ...} 
def get_traffics(fudgeroute_name_, dir_, current_, time_, log_=False):
	time_ = massage_time_arg(time_, 60*1000)
	mckey = mc.make_key('get_traffics', fudgeroute_name_, dir_, time_)
	r = mc.client.get(mckey)
	if r:
		if log_: printerr('Found in memcache.')
	else:
		if log_: printerr('Not found in memcache.')
		r = get_traffics_impl(fudgeroute_name_, dir_, time_, current_, log_=log_)
		mc.client.set(mckey, r)
	return r

def get_traffics_impl(fudgeroute_name_, dir_, time_, current_, log_=False):
	mofr_to_avgspeedandweight = get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, log_=log_)
	return [get_traffics_visuals(mofr_to_avgspeedandweight, fudgeroute_name_, dir_), \
			get_traffics__mofr2speed(mofr_to_avgspeedandweight)]

def get_traffics__mofr2speed(mofr_to_avgspeedandweight_):
	r = {}
	for mofr, traf in mofr_to_avgspeedandweight_.items():
		if traf != None:
			r[mofr] = {'kmph': traf['kmph'], 'weight': traf['weight']}
		else:
			r[mofr] = None
	return r

def get_traffics_visuals(mofr_to_avgspeedandweight_, fudgeroute_name_, dir_):
	r = []
	routept1_mofr = 0
	for routept1, routept2 in hopscotch(routes.get_routeinfo(fudgeroute_name_).routepts(dir_)):
		route_seg_len = routept1.dist_m(routept2)
		routept2_mofr = routept1_mofr + route_seg_len
		routept1_mofr_ref = round(routept1_mofr, MOFR_STEP); routept2_mofr_ref = round(routept2_mofr, MOFR_STEP)
		for mofr_ref in range(routept1_mofr_ref, routept2_mofr_ref+1, MOFR_STEP):
			if mofr_ref not in mofr_to_avgspeedandweight_: continue
			seg_start_mofr = max(mofr_ref - MOFR_STEP/2, routept1_mofr)
			seg_end_mofr = min(mofr_ref + MOFR_STEP/2, routept2_mofr)
			seg_start_latlng = routept1.add(routept2.subtract(routept1).scale((seg_start_mofr-routept1_mofr)/float(route_seg_len)))
			seg_end_latlng   = routept1.add(routept2.subtract(routept1).scale((seg_end_mofr  -routept1_mofr)/float(route_seg_len)))
			r.append({'start_latlon': seg_start_latlng, 'end_latlon': seg_end_latlng, 'mofr': mofr_ref})
		routept1_mofr += route_seg_len
	return r

def get_traffics_impl_old_for_directional_arrows(fudgeroute_name_, dir_, time_, current_, log_=False):
	mofr_to_avgspeedandweight = get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, log_=log_)
	r = []
	for mofr in sorted(mofr_to_avgspeedandweight.keys()):
		traf = mofr_to_avgspeedandweight[mofr]
		if not traf:
			r.append(None)
		else:
			latlon, heading = routes.mofr_to_latlonnheading(fudgeroute_name_, mofr, dir_)
			r.append({'latlon': latlon, 'heading': heading, 'kmph': traf['kmph'], 'weight': traf['weight']})
	return r

def get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, log_=False):
	r = {}
	mofr_to_rawtraffics = get_traffic_rawspeeds(fudgeroute_name_, dir_, time_, log_=log_)
	for mofr, rawtraffics in sorted(mofr_to_rawtraffics.iteritems()): # Here we iterate in sorted key order only to print easier-to-read log msgs.
		if log_: printerr('mofr=%d:' % mofr)
		if not rawtraffics:
			if log_: printerr('\tNo raw traffics.')
			r[mofr] = None
		else:
			for rawtraffic in rawtraffics:
				rawtraffic['weight'] = (time_to_weight(rawtraffic['time'], time_) if current_ else 1.0)
				if log_: printerr('\tInterpolated time %s ==> weight %.3f' % (em_to_str_hms(rawtraffic['time']), rawtraffic['weight']))
			weights_total = sum([x['weight'] for x in rawtraffics])
			if weights_total >= 0.01:
				weighted_avg_speed = abs(sum([x['speed_kmph']*x['weight']/weights_total for x in rawtraffics]))
				r[mofr] = {'kmph': weighted_avg_speed, 'weight': weights_total}
			else:
				if log_: printerr('\tZero or negligible weight tally at this mofr.  Will treat as though there is no traffic here.')
				r[mofr] = None
	return r

def time_to_weight(time_, now_):
	window = TIME_WINDOW_MINUTES*60*1000
	window_begin = now_ - window
	if time_ >= now_: # must be an extrapolation 
		return 1.0
	elif time_ < window_begin + 1000:
		return 0.0
	else:
		# I believe this is a quarter circle: 
		return (1 - ((float(time_ - now_))/window)**2)**0.5

def get_traffic_rawspeeds(fudgeroute_name_, dir_, time_=now_em(), log_=False):
	assert dir_ in (0, 1)
	mofr_to_rawtraffics = {}
	for mofr in range(0, routes.max_mofr(fudgeroute_name_), MOFR_STEP):
		mofr_to_rawtraffics[mofr] = []
	for vid, vises in get_vid_to_vises_from_db_for_traffic(fudgeroute_name_, dir_, time_=time_, log_=log_).items():
		for vis in vises:
			if log_: printerr('For vid "%s":' % (vid))
			if log_:
				for vi in vis[::-1]:
					printerr('\traw vinfo: %s' % (str(vi)))
			if len(vis) < 2:
				continue
			for interp_mofr in range(0, routes.max_mofr(fudgeroute_name_), MOFR_STEP):
				if log_: printerr('\tFor mofr %d:' % (interp_mofr))
				vi_lo, vi_hi = get_bounding_mofr_vis(interp_mofr, vis)
				if vi_lo and vi_hi:
					if log_: printerr('\t\tFound bounding vis at mofrs %d and %d (%s and %s).' % (vi_lo.mofr, vi_hi.mofr, vi_lo.timestr, vi_hi.timestr))
					interp_ratio = (interp_mofr - vi_lo.mofr)/float(vi_hi.mofr - vi_lo.mofr)
					interp_t = int(vi_lo.time + interp_ratio*(vi_hi.time - vi_lo.time))
					speed_kmph = ((vi_hi.mofr - vi_lo.mofr)/1000.0)/((vi_hi.time - vi_lo.time)/(1000.0*60*60))
					if log_: printerr('\t\tSpeed: %.1f.  Interpolated time at this mofr: %s' % (speed_kmph, em_to_str_hms(interp_t)))
					# TODO: fix buggy negative speeds a better way, maybe.
					mofr_to_rawtraffics[interp_mofr].append({'speed_kmph': speed_kmph, 'time':interp_t, 'vid': vid})
				else:
					if log_: printerr('\t\tNo bounding vis found for this mofr step / vid.')
	return mofr_to_rawtraffics

# [1] Here I am trying to implement the following judgement call:
# It is better to show no traffic at all (white) than a misleading orange
# that is derived from one or more vehicles that never traversed that stretch of road,
# but detoured around it.   This will happen in the case of major incidents involving detours eg.
# dundas westbound 2012-09-24 13:35 (preceeding half-hour thereof).  See how vid 4087 detours around
# ossington and college, how no vehicles traverse westbound dundas between ossington and lansdowne
# between 13:05 and 13:35, and how this could result in vid 4087 single-handedly causing a
# decent-looking traffic report for that stretch of road.  I would rather show white (or whatever
# I'm showing to signify 'no traffic data' now) and thus encourage the user to look for the detour.
def get_bounding_mofr_vis(mofr_, vis_):
	assert all(vi1.vehicle_id == vi2.vehicle_id for vi1, vi2 in hopscotch(vis_))
	assert all(vi.mofr != -1 for vi in vis_)

	mofr_key = lambda x: x.mofr

	prev_step_vis = filter(lambda x: mofr_ - MOFR_STEP < x.mofr < mofr_, vis_)
	if prev_step_vis:
		vi_lo = min(prev_step_vis, key=mofr_key)
	else:
		lesser_vis = filter(lambda x: x.mofr < mofr_, vis_)
		if lesser_vis:
			vi_lo = max(lesser_vis, key=mofr_key)
		else:
			vi_lo = None

	greater_vis = filter(lambda x: x.mofr > mofr_, vis_)
	if greater_vis:
		vi_hi = min(greater_vis, key=mofr_key)
	else:
		vi_hi = None

	if vi_lo and vi_hi:
		assert vi_lo.mofr < vi_hi.mofr

	if vi_lo and vi_hi and (abs(vi_hi.time - vi_lo.time) > 1000*60*10): # see [1] above.
		return (None, None)
	else:
		return (vi_lo, vi_hi)

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

# 'off step' means 'steps shifted in phase by half the period, if you will'  
def round_up_off_step(x_, step_):
	r = round_down_off_step(x_, step_)
	return r if r == x_ else r+step_

def round_down_off_step(x_, step_):
	assert type(x_) == int and type(step_) == int
	return ((x_-step_/2)/step_)*step_ + step_/2

def round_up(x_, step_):
	r = round_down(x_, step_)
	return r if r == x_ else r+step_

def round_down(x_, step_):
	assert type(x_) in (int, long, float) and type(step_) in (int, long)
	return (long(x_)/step_)*step_

def round(x_, step_):
	rd = round_down(x_, step_)
	ru = round_up(x_, step_)
	return (rd if x_ - rd < ru - x_ else ru)

def test(a_, b_):
	return 'test func got: %s and %s' % (a_, b_)

if __name__ == '__main__':

	pass 
