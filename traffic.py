#!/usr/bin/python2.6

from collections import *
import vinfo, db, routes, geom, mc, yards, c
from misc import *

with open('MOFR_STEP') as f:
	MOFR_STEP = int(f.read().strip())

TIME_WINDOW_MINUTES = 30

def get_recent_vehicle_locations_dirfromlatlngs(fudgeroute_name_, latlng1_, latlng2_, current_, time_, log_=False):
	return get_recent_vehicle_locations(fudgeroute_name_, routes.routeinfo(fudgeroute_name_).dir_from_latlngs(latlng1_, latlng2_), current_, time_, log_)

def get_recent_vehicle_locations(fudgeroute_, dir_, current_, time_, log_=False):
	time_ = massage_time_arg(time_, 15*1000)
	return mc.get(get_recent_vehicle_locations_impl, [fudgeroute_, dir_, current_, time_, log_])

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
def get_vid_to_vis_from_db_for_traffic(fudgeroute_name_, dir_, time_, window_minutes_, usewidemofr_=False, log_=False):
	r = db.get_vid_to_vis(fudgeroute_name_, dir_, window_minutes_, time_, True, False, log_=log_)
	for vid, vis in r.items():
		filter_in_place(vis, lambda vi: (vi.widemofr if usewidemofr_ else vi.mofr) != -1)
	return r

def between(bound1_, value_, bound2_):
	return (bound1_ < value_ < bound2_) or (bound1_ > value_ > bound2_) 

def get_traffics_dirfromlatlngs(fudgeroute_name_, latlng1_, latlng2_, current_, time_, log_=False):
	return get_traffics(fudgeroute_name_, routes.dir_from_latlngs(fudgeroute_name_, latlng1_, latlng2_), current_, time_, log_)

# time_ - 0 for now 
# 
# returns elem 0: visuals list - [[timestamp, vi dict, vi dict, ...], ...] 
#         elem 1: speed map - {mofr1: {'kmph': kmph, 'weight': weight}, ...} 
def get_traffics(fudgeroute_name_, dir_, current_, time_, window_minutes_=TIME_WINDOW_MINUTES, log_=False):
	time_ = massage_time_arg(time_, 60*1000)
	return mc.get(get_traffics_impl, [fudgeroute_name_, dir_, current_, time_, window_minutes_, log_])

def get_traffics_impl(fudgeroute_name_, dir_, current_, time_, window_minutes_, log_=False):
	mofr_to_avgspeedandweight = get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, window_minutes_, log_=log_)
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
	for routept1, routept2 in hopscotch(routes.routeinfo(fudgeroute_name_).routepts(dir_)):
		route_seg_len = routept1.dist_m(routept2)
		routept2_mofr = routept1_mofr + route_seg_len
		routept1_mofr_ref = round(routept1_mofr, MOFR_STEP); routept2_mofr_ref = round(routept2_mofr, MOFR_STEP)
		for mofr_ref in range(routept1_mofr_ref, routept2_mofr_ref+1, MOFR_STEP):
			if mofr_ref not in mofr_to_avgspeedandweight_: continue
			seg_start_mofr = max(mofr_ref - MOFR_STEP/2, routept1_mofr)
			seg_end_mofr = min(mofr_ref + MOFR_STEP/2, routept2_mofr)
			seg_start_latlng = routept1.add(routept2.subtract(routept1).scale((seg_start_mofr-routept1_mofr)/float(route_seg_len)))
			seg_end_latlng   = routept1.add(routept2.subtract(routept1).scale((seg_end_mofr  -routept1_mofr)/float(route_seg_len)))
			r.append({'start_latlon': seg_start_latlng, 'end_latlon': seg_end_latlng, 'mofr': mofr_ref, 
					'start_mofr': routept1_mofr, 'end_mofr': routept2_mofr})
		routept1_mofr += route_seg_len
	return r

def get_mofr_to_kmph(froute_, dir_, current_, time_, window_minutes_=TIME_WINDOW_MINUTES, log_=False):
	time_ = massage_time_arg(time_, 60*1000)
	return mc.get(get_mofr_to_kmph_impl, [froute_, dir_, current_, time_, window_minutes_, log_])

def get_mofr_to_kmph_impl(froute_, dir_, current_, time_, window_minutes_, log_=False):
	r = {}
	for mofr, avgspeedandweight in get_traffic_avgspeedsandweights(froute_, dir_, time_, current_, window_minutes_, log_=log_).iteritems():
		if avgspeedandweight is not None:
			r[mofr] = avgspeedandweight['kmph']
		else:
			r[mofr] = None
	return r

def get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, window_minutes_, log_=False):
	r = {}
	mofr_to_rawtraffics = get_traffic_rawspeeds(fudgeroute_name_, dir_, time_, window_minutes_, log_=log_)
	for mofr, rawtraffics in sorted(mofr_to_rawtraffics.iteritems()): # Here we iterate in sorted key order only to print easier-to-read log msgs.
		if log_: printerr('mofr=%d:' % mofr)
		if not rawtraffics:
			if log_: printerr('\tNo raw traffics.')
			r[mofr] = None
		else:
			for rawtraf in rawtraffics:
				rawtraf['weight'] = (time_to_weight(rawtraf['time'], time_, window_minutes_) if current_ else 1.0)
				if log_: printerr('\tInterpolated time %s (kmph=%.1f, vid=%s) ==> weight %.3f' \
						% (em_to_str_hms(rawtraf['time']), rawtraf['speed_kmph'], rawtraf['vid'], rawtraf['weight']))
			weights_total = sum([x['weight'] for x in rawtraffics])
			if weights_total >= 0.01:
				weighted_avg_speed = abs(sum([x['speed_kmph']*x['weight']/weights_total for x in rawtraffics]))
				r[mofr] = {'kmph': weighted_avg_speed, 'weight': weights_total}
				if log_: printerr('\tWeight speed: %.1f kmph.' % weighted_avg_speed)
			else:
				if log_: printerr('\tWeighted speed: none.  (Due to zero or negligible weight tally at this mofr.')
				r[mofr] = None
	return r

def time_to_weight(time_, now_, window_minutes_):
	window = window_minutes_*60*1000
	window_begin = now_ - window
	if time_ >= now_: # must be an extrapolation 
		return 1.0
	elif time_ < window_begin + 1000:
		return 0.0
	else:
		# I believe this is a quarter circle: 
		return (1 - ((float(time_ - now_))/window)**2)**0.5

def get_traffic_rawspeeds(fudgeroute_name_, dir_, time_, window_minutes_, usewidemofr_=False, singlemofr_=None, log_=False):
	assert dir_ in (0, 1)
	mofr_to_rawtraffics = {}
	mofrs_to_get = (range(0, routes.max_mofr(fudgeroute_name_), MOFR_STEP) if singlemofr_ is None else [singlemofr_])
	for mofr in mofrs_to_get:
		mofr_to_rawtraffics[mofr] = []
	for vid, vis in get_vid_to_vis_from_db_for_traffic(fudgeroute_name_, dir_, time_, window_minutes_, usewidemofr_=usewidemofr_, log_=log_).items():
		if log_: printerr('For vid "%s":' % (vid))
		if log_:
			for vi in vis[::-1]:
				printerr('\traw vinfo: %s' % (str(vi)))
		if len(vis) < 2:
			continue
		def mofr(vi__): return (vi__.widemofr if usewidemofr_ else vi__.mofr)
		assert all(mofr(vi) != -1 for vi in vis)
		for interp_mofr in mofrs_to_get:
			if log_: printerr('\tFor mofr %d:' % (interp_mofr))
			vi_lo, vi_hi = get_bounding_mofr_vis(interp_mofr, vis, usewidemofr_)
			if vi_lo and vi_hi:
				if log_: printerr('\t\tFound bounding vis at mofrs %d and %d (%s and %s).' % (mofr(vi_lo), mofr(vi_hi), vi_lo.timestr, vi_hi.timestr))
				interp_ratio = (interp_mofr - mofr(vi_lo))/float(mofr(vi_hi) - mofr(vi_lo))
				interp_t = int(vi_lo.time + interp_ratio*(vi_hi.time - vi_lo.time))
				speed_kmph = ((mofr(vi_hi) - mofr(vi_lo))/1000.0)/((vi_hi.time - vi_lo.time)/(1000.0*60*60))
				if log_: printerr('\t\tSpeed: %.1f.  Interpolated time at this mofr: %s' % (speed_kmph, em_to_str_hms(interp_t)))
				# TODO: fix buggy negative speeds a better way, maybe.
				mofr_to_rawtraffics[interp_mofr].append({'speed_kmph': speed_kmph, 'time':interp_t, 'vid': vid})
			else:
				if log_: printerr('\t\tNo bounding vis found for this mofr step / vid.')
	return (mofr_to_rawtraffics if singlemofr_ is None else mofr_to_rawtraffics.values()[0])

# return a tuple - (headway in millis, time of earlier passing vehicle, time of later passing vehicle)
# 	or None if no headway could be found from the vehicles that passed the stop in the given window-minutes.
def get_observed_headway(froute_, stoptag_, time_, window_minutes_, usewidemofr_=False, log_=False):
	stop = routes.routeinfo(froute_).get_stop(stoptag_)
	mofr = stop.mofr
	rawtraffics = get_traffic_rawspeeds(froute_, stop.direction, time_+(window_minutes_*60*1000/2), window_minutes_, usewidemofr_=False,
			singlemofr_=mofr, log_=log_)
	if not rawtraffics:
		return None
	earlier_rawtraffics = [rawtraffic for rawtraffic in rawtraffics if rawtraffic['time'] <= time_]
	later_rawtraffics = [rawtraffic for rawtraffic in rawtraffics if rawtraffic['time'] >= time_]
	if earlier_rawtraffics and later_rawtraffics:
		lo_time = max(earlier_rawtraffics, key=lambda rawtraffic: rawtraffic['time'])['time']
		hi_time = min(later_rawtraffics,   key=lambda rawtraffic: rawtraffic['time'])['time']
		return (hi_time - lo_time, lo_time, hi_time)
	else:
		return None


# [1] Here I am trying to implement the following judgement call:
# It is better to show no traffic at all (white) than a misleading orange
# that is derived from one or more vehicles that never traversed that stretch of road,
# but detoured around it.   This will happen in the case of major incidents involving detours eg.
# dundas westbound 2012-09-24 13:35 (preceeding half-hour thereof).  See how vid 4087 detours around
# ossington and college, how no vehicles traverse westbound dundas between ossington and lansdowne
# between 13:05 and 13:35, and how this could result in vid 4087 single-handedly causing a
# decent-looking traffic report for that stretch of road.  I would rather show white (or whatever
# I'm showing to signify 'no traffic data' now) and thus encourage the user to look for the detour.
def get_bounding_mofr_vis(mofr_, vis_, usewidemofr_):
	assert isinstance(mofr_, int) and isinstance(vis_, Sequence) and isinstance(usewidemofr_, bool)
	assert all(vi1.vehicle_id == vi2.vehicle_id for vi1, vi2 in hopscotch(vis_))

	get_mofr = lambda vi: (vi.widemofr if usewidemofr_ else vi.mofr)

	prev_step_vis = filter(lambda vi: mofr_ - MOFR_STEP < get_mofr(vi) < mofr_, vis_)
	if prev_step_vis:
		vi_lo = min(prev_step_vis, key=get_mofr)
	else:
		lesser_vis = filter(lambda vi: get_mofr(vi) < mofr_, vis_)
		if lesser_vis:
			vi_lo = max(lesser_vis, key=get_mofr)
		else:
			vi_lo = None

	greater_vis = filter(lambda vi: get_mofr(vi) > mofr_, vis_)
	if greater_vis:
		vi_hi = min(greater_vis, key=get_mofr)
	else:
		vi_hi = None

	if vi_lo and vi_hi:
		assert get_mofr(vi_lo) < get_mofr(vi_hi)

	if vi_lo and vi_hi and (abs(vi_hi.time - vi_lo.time) > 1000*60*8): # see [1] above.
		return (None, None)
	else:
		return (vi_lo, vi_hi)

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

def test(a_, b_):
	return 'test func got: %s and %s' % (a_, b_)

# return -1 if one or more parts of the route have no traffic data. 
def get_est_riding_time_secs(froute_, start_mofr_, dest_mofr_, current_, time_):
	assert all(0 <= mofr <= routes.routeinfo(froute_).max_mofr() for mofr in (start_mofr_, dest_mofr_))
	if mofrs_to_dir(start_mofr_, dest_mofr_) == 0:
		startmofr = start_mofr_
		destmofr = dest_mofr_
	else:
		startmofr = dest_mofr_
		destmofr = start_mofr_
	mofr_to_kmph = get_mofr_to_kmph(froute_, mofrs_to_dir(startmofr, destmofr), current_, time_)
	r_secs = 0
	if startmofr != round_up_off_step(startmofr, MOFR_STEP):
		dist_m = round_up_off_step(startmofr, MOFR_STEP) - startmofr
		speed_kmph = mofr_to_kmph[round(startmofr, MOFR_STEP)]
		if speed_kmph == None:
			return -1
		speed_mps = kmph_to_mps(speed_kmph)
		#alert('adding distance '+dist_m+', speed '+speed_mps+', makes for '+(dist_m/speed_mps))
		r_secs += dist_m/speed_mps
	cur_offstep_mofr = round_up_off_step(startmofr, MOFR_STEP)
	while cur_offstep_mofr < round_down_off_step(destmofr, MOFR_STEP):
		mofr_with_ref_speed = round_up(cur_offstep_mofr, MOFR_STEP)
		speed_kmph = mofr_to_kmph[mofr_with_ref_speed]
		if speed_kmph == -1:
			return -1
		speed_mps = kmph_to_mps(speed_kmph)
		#alert('adding distance '+MOFR_STEP+', speed '+speed_mps+', makes for '+(MOFR_STEP/speed_mps))
		r_secs += MOFR_STEP/speed_mps
		cur_offstep_mofr += MOFR_STEP
	if destmofr != round_down_off_step(destmofr, MOFR_STEP):
		dist_m = destmofr - round_down_off_step(destmofr, MOFR_STEP)
		speed_kmph = mofr_to_kmph[round(destmofr, MOFR_STEP)]
		if speed_kmph == -1:
			return -1
		speed_mps = kmph_to_mps(speed_kmph)
		#alert('adding distance '+dist_m+', speed '+speed_mps+', makes for '+(dist_m/speed_mps))
		r_secs += dist_m/speed_mps
	return r_secs


if __name__ == '__main__':

	pass 
