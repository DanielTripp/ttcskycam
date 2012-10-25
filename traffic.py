#!/usr/bin/python2.6

from collections import defaultdict
import vinfo, db, routes, geom, mc, yards, c
from misc import *

with open('MOFR_STEP') as f:
	MOFR_STEP = int(f.read().strip())

TIME_WINDOW_MINUTES = 30

def get_recent_vehicle_locations(fudgeroute_, dir_, current_, time_, log_=False):
	time_ = massage_time_arg(time_, 15*1000)
	mckey = '%s-get_recent_vehicle_locations(%s,%d,%d,%d)' % (c.SITE_VERSION, fudgeroute_, dir_, current_, time_)
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
	r = []
	for timeslice in db.query2(fudgeroute_, TIME_WINDOW_MINUTES, dir_, current_, time_window_end_=time_, log_=log_):
		r_e = []
		r.append(r_e)
		r_e.append(timeslice[0])
		for vi in timeslice[1:]:
			r_e.append(vi.to_json_dict())
	return r

def get_vid_to_vis_from_db(fudgeroute_name_, dir_, time_, log_=False):
	vis = []
	for config_route in routes.fudgeroute_to_configroutes(fudgeroute_name_):
		vis += db.get_latest_vehicle_info_list(config_route, TIME_WINDOW_MINUTES, dir_=dir_, end_time_em_=time_, log_=log_)
	yards.remove_vehicles_in_yards(vis)
	vis.sort(key=lambda x: x.time, reverse=True) # got to sort these by time again b/c even though they come from the db 
		# call above sorted thusly, a fugderoute with more than one configroute (eg. queen) may have a vehicle that changes 
		# routes all of a sudden (eg. from 501 to 301, around 1:30 AM), and then that would mess up remove_doublebacks() below. 
	vid_to_vis = defaultdict(lambda: [])
	for vi in vis:
		if vi.mofr != -1: # b/c we can't use vis that are not on the route.  
			vid_to_vis[vi.vehicle_id].append(vi)
		else:
			if log_: printerr('Not on route (i.e. mofr==-1), discarding: %s' % (str(vi)))
	for vid, vis in vid_to_vis.items():
		vis[:] = remove_doublebacks(vis, dir_, log_=log_)
	return dict(vid_to_vis) # b/c a defaultdict can't be pickled i.e. memcached 

def remove_doublebacks(vis_, dir_, log_=False):
	if len(vis_) < 2:
		return vis_
	assert all(vi1.time > vi2.time for vi1, vi2 in hopscotch(vis_)) # b/c that's the order we get these in, apparently 
	assert all(vi.mofr >= 0 for vi in vis_)
	r = [vis_[0]]
	for vi in vis_[1:]:
		if r[-1].mofr <= vi.mofr if dir_ else r[-1].mofr >= vi.mofr:
			r.append(vi)
		else:
			if log_: printerr('Removing double-back: %s' % (str(vi)))
	return r

def between(bound1_, value_, bound2_):
	return (bound1_ < value_ < bound2_) or (bound1_ > value_ > bound2_) 

# time_ - 0 for now 
# 
# returns elem 0: visuals list - [[timestamp, vi dict, vi dict, ...], ...] 
#         elem 1: speed map - {mofr1: {'kmph': kmph, 'weight': weight}, ...} 
def get_traffics(fudgeroute_name_, dir_, current_, time_, log_=False):
	time_ = massage_time_arg(time_, 60*1000)
	mckey = '%s-get_traffics(%s,%d,%d)' % (c.SITE_VERSION, fudgeroute_name_, dir_, time_)
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
	return [get_traffics_visuals(mofr_to_avgspeedandweight, fudgeroute_name_), \
			get_traffics__mofr2speed(mofr_to_avgspeedandweight)]

def get_traffics__mofr2speed(mofr_to_avgspeedandweight_):
	r = {}
	for mofr, traf in mofr_to_avgspeedandweight_.items():
		if traf != None:
			r[mofr] = {'kmph': traf['kmph'], 'weight': traf['weight']}
		else:
			r[mofr] = None
	return r

def get_traffics_visuals(mofr_to_avgspeedandweight_, fudgeroute_name_):
	r = []
	routept1_mofr = 0
	for routept1, routept2 in hopscotch(routes.get_routeinfo(fudgeroute_name_).routepts):
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
			latlon, heading = routes.mofr_to_latlonnheading(mofr, fudgeroute_name_, dir_)
			r.append({'latlon': latlon, 'heading': heading, 'kmph': traf['kmph'], 'weight': traf['weight']})
	return r

def get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, time_, current_, log_=False):
	r = {}
	mofr_to_rawtraffics = get_traffic_rawspeeds(fudgeroute_name_, dir_, time_, log_=log_)
	for mofr, rawtraffics in mofr_to_rawtraffics.items():
		if not rawtraffics:
			r[mofr] = None
		else:
			for rawtraffic in rawtraffics:
				rawtraffic['weight'] = (time_to_weight(rawtraffic['time'], time_) if current_ else 1.0)
			weights_total = sum([x['weight'] for x in rawtraffics])
			if weights_total > 0:
				weighted_avg_speed = abs(sum([x['speed_kmph']*x['weight']/weights_total for x in rawtraffics]))
			else:
				weighted_avg_speed = 0.0
			r[mofr] = {'kmph': weighted_avg_speed, 'weight': weights_total}
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
	for vid, vis in get_vid_to_vis_from_db(fudgeroute_name_, dir_, time_=time_, log_=log_).items():
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
				if log_: printerr('\t\tSpeed: %.1f' % (speed_kmph))
				# TODO: fix buggy negative speeds a better way, maybe. 
				mofr_to_rawtraffics[interp_mofr].append({'speed_kmph': speed_kmph, 'time':interp_t, 'vid': vid})
			else:
				if log_: printerr('\t\tNo bounding vis found for this mofr step / vid.')
	return mofr_to_rawtraffics

def get_bounding_mofr_vis(mofr_, vis_):
	assert all(vi1.vehicle_id == vi2.vehicle_id for vi1, vi2 in hopscotch(vis_))

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
	if vi_lo and vi_hi and vis_bridge_significant_detour(vi_lo, vi_hi):
		return (None, None)
	else:
		return (vi_lo, vi_hi)

# This method implements this judgement call: 
# It is better to show no traffic at all (white) than a misleading orange 
# that is derived from one or more vehicles that never traversed that stretch of road, 
# but detoured around it.   This will happen in the case of major incidents involving detours eg. 
# dundas westbound 2012-09-24 13:35 (preceeding half-hour thereof).  See how vid 4087 detours around 
# ossington and college, how no vehicles traverse westbound dundas between ossington and lansdowne 
# between 13:05 and 13:35, and how this coudl result in vid 4087 single-handedly causing a 
# decent-looking traffic report for that stretch of road.  I woudl rather show white (or however 
# I'm showing 'no traffic data' now) and thus encourage the user to find the detour.  
def vis_bridge_significant_detour(lo_, hi_):
	assert lo_.vehicle_id == hi_.vehicle_id and lo_.mofr != -1 and hi_.mofr != -1
	if hi_.mofr - lo_.mofr < 1000:
		return False
	else:
		return db.vis_bridge_detour(lo_, hi_)

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
