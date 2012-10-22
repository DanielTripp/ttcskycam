#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math, numbers, json
from math import *
from collections import defaultdict
import vinfo, db, routes
from misc import *

# 'fe' means 'flat earth' - an imaginary coordinate system.

REF_LON_TO_FEX_POINT1 = (-79.4646, 2000)
REF_LON_TO_FEX_POINT2 = (-79.3627, 13840)
REF_LAT_TO_FEY_POINT1 = (43.6515, 4770)
REF_LAT_TO_FEY_POINT2 = (43.6653, 7000)

REF_FEX_TO_BMPX_POINT1 = (2000, 153)
REF_FEX_TO_BMPX_POINT2 = (13840, 1337)
REF_FEY_TO_BMPY_POINT1 = (7000, 261)
REF_FEY_TO_BMPY_POINT2 = (4770, 484)

class XY:

	@classmethod
	def from_latlon(cls_, latlon_):
		assert type(latlon_[0]) == float and type(latlon_[1]) == float 
		#assert (43 < latlon_[0] < 44) and (-80 < latlon_[1] < -79)
		fex = int(get_range_val(REF_LON_TO_FEX_POINT1, REF_LON_TO_FEX_POINT2, latlon_[1]))
		fey = int(get_range_val(REF_LAT_TO_FEY_POINT1, REF_LAT_TO_FEY_POINT2, latlon_[0]))
		r = cls_((fex, fey))
		return r

	def __init__(self, x_, y_=None):
		if type(x_) == int:
			xy = (x_, y_)
		else:
			assert y_==None
			xy = x_
		assert len(xy) == 2 and type(xy[0]) == int and type(xy[1]) == int
		self.x = xy[0]
		self.y = xy[1]

	def clone(self):
		return XY(self.x, self.y)

	def fe(self):
		return (self.x, self.y)

	def latlon(self):
		lon = get_range_val(REF_LON_TO_FEX_POINT1[::-1], REF_LON_TO_FEX_POINT2[::-1], self.x)
		lat = get_range_val(REF_LAT_TO_FEY_POINT1[::-1], REF_LAT_TO_FEY_POINT2[::-1], self.y)
		r = (lat, lon)
		return r
	
	def dist_m(self, other_):
		return dist_latlon(LatLon(self), LatLon(other_))

	def bmp(self):
		bmpx = get_range_val(REF_FEX_TO_BMPX_POINT1, REF_FEX_TO_BMPX_POINT2, self.x)
		bmpy = get_range_val(REF_FEY_TO_BMPY_POINT1, REF_FEY_TO_BMPY_POINT2, self.y)
		r = (bmpx, bmpy)
		return r

	def __eq__(self, other_):
		return self.x == other_.x and self.y == other_.y

	def __str__(self):
		return '(%d, %d)' % (self.x, self.y)


def get_range_val(p1_, p2_, domain_val_):
	x1 = float(p1_[0]); y1 = float(p1_[1])
	x2 = float(p2_[0]); y2 = float(p2_[1])
	r = (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1
	if any(type(x) == float for x in p1_ + p2_ + (domain_val_,)):
		return r
	else:
		return int(r)

def avg(lo_, hi_, ratio_):
	r = lo_ + (hi_ - lo_)*ratio_
	if type(lo_) == int and type(hi_) == int:
		return int(r)
	elif type(lo_) == long or type(hi_) == long:
		return long(r)
	else:
		return r

def round_down_by_minute(t_em_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute)
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def get_nearest_time_vis(vilist_, vid_, t_):
	assert type(t_) == long
	lo_vi = None; hi_vi = None
	for vi in (vi for vi in vilist_ if vi.vehicle_id == vid_):
		if vi.time < t_:
			if lo_vi==None or lo_vi.time < vi.time:
				lo_vi = vi
		elif vi.time > t_:
			if hi_vi==None or hi_vi.time > vi.time:
				hi_vi = vi
	return (lo_vi, hi_vi)

# Takes a flat list of VehicleInfo objects.  Returns a list of lists of Vehicleinfo objects, interpolated. 
# Also, with a date/time string# as element 0 in each list. 
def interp_by_time(vilist_, try_for_mofr_based_loc_interp_, current_conditions_, dir_=None, end_time_=None):
	if len(vilist_) == 0:
		return []
	starttime = round_down_by_minute(min(vi.time for vi in vilist_))
	endtime = end_time_ if end_time_!=None else max(vi.time for vi in vilist_)
	vids = set(vi.vehicle_id for vi in vilist_)
	time_to_vis = {}
	for interptime in lrange(starttime, endtime+1, 60*1000):
		interped_timeslice = []
		for vid in vids:
			lo_vi, hi_vi = get_nearest_time_vis(vilist_, vid, interptime)
			i_vi = None
			if lo_vi and hi_vi:
				if (min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int) \
						or (lo_vi.route_tag != hi_vi.route_tag):
					continue
				ratio = (interptime - lo_vi.time)/float(hi_vi.time - lo_vi.time)
				i_latlon, i_heading = interp_latlonnheading(lo_vi, hi_vi, ratio, try_for_mofr_based_loc_interp_)
				i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, i_heading, vid, i_latlon[0], i_latlon[1],
					lo_vi.predictable and hi_vi.predictable,
					lo_vi.route_tag, 0, interptime, interptime)
			elif lo_vi and not hi_vi:
				if current_conditions_:
					if (interptime - lo_vi.time > 3*60*1000) or dirs_disagree(dir_, lo_vi.dir_tag_int):
						continue
					i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, lo_vi.heading, vid, lo_vi.lat, lo_vi.lon, 
						lo_vi.predictable, lo_vi.route_tag, 0, interptime, interptime)

			if i_vi:
				interped_timeslice.append(i_vi)
				
		time_to_vis[interptime] = interped_timeslice
	fill_in_blank_headings(time_to_vis)
	return massage_to_list(time_to_vis)

def fill_in_blank_headings(r_time_to_vis_):
	times = sorted(r_time_to_vis_.keys())
	for timei, time in enumerate(times):
		if timei==0:
			continue
		for target_vi in r_time_to_vis_[time]:
			if target_vi.heading == -4: # -4 means blank, or at least that's what nextbus seems to mean by it. 
				# Now look back in time for a previous appearance of this vid which indicates a direction by change of by mofr, then 
				# get a heading from our static route info based on that direction. 
				if target_vi.mofr != -1:
					prev_vi = None
					for timej in range(timei-1, -1, -1):
						if prev_vi != None:
							break
						for older_vi in r_time_to_vis_[times[timej]]:
							if (older_vi.vehicle_id == target_vi.vehicle_id) and (older_vi.mofr != -1) \
									and (older_vi.fudgeroute == target_vi.fudgeroute) \
									and (abs(target_vi.mofr - older_vi.mofr) >= 5):
								prev_vi = older_vi
								break
					if prev_vi != None:
						dir = (0 if prev_vi.mofr < target_vi.mofr else 1)
						target_vi.heading = routes.get_routeinfo(target_vi.route_tag).mofr_to_heading(target_vi.mofr, dir)
			if target_vi.heading == -4: # If the above didn't work out then try again using lat/lons instead of mofrs. 
				prev_vi = None
				for timej in range(timei-1, -1, -1):
					if prev_vi != None:
						break
					for older_vi in r_time_to_vis_[times[timej]]:
						if (older_vi.vehicle_id == target_vi.vehicle_id) and (older_vi.xy.dist_m(target_vi.xy) >= 10):
							prev_vi = older_vi
							break
				if prev_vi != None:
					target_vi.heading = heading(prev_vi.xy, target_vi.xy)

def massage_to_list(time_to_vis_):
	time_to_vis = time_to_vis_.copy()

	# Deleting all empty timeslices at the end of the time frame.  
	# doing this because the last timeslice is the current vehicle locations of course, and that is an important
	# timeslice and will be rendered differently in the GUI.
	for time in sorted(time_to_vis.keys(), reverse=True):
		if len(time_to_vis[time]) == 0:
			del time_to_vis[time]
		else:
			break

	r = []
	for time in sorted(time_to_vis.keys()):
		vis = time_to_vis[time]
		r.append([em_to_str(time)] + vis)
	for i in range(len(r)-1, -1, -1):
		if len(r[i]) == 1: # Delete all empty (empty except for the date/time string) timeslices at the end.
			del r[i] # doing this because the last timeslice is the current vehicle locations of course, and that is an important
		else: # timeslice and will be rendered differently in the GUI.
			break
	return r

# Either arg could be None (i.e. blank dir_tag).  For this we consider None to 'agree' with 0 or 1. 
def dirs_disagree(dir1_, dir2_):
	return (dir1_ == 0 and dir2_ == 1) or (dir1_ == 1 and dir2_ == 0)

def interp_latlonnheading(vi1_, vi2_, ratio_, try_for_mofr_based_loc_interp_):
	r = None
	vi1latlon = vi1_.xy.latlon(); vi2latlon = vi2_.xy.latlon()
	if try_for_mofr_based_loc_interp_ and vi1_.dir_tag and vi2_.dir_tag:
		if routes.CONFIGROUTE_TO_FUDGEROUTE[vi1_.route_tag] == routes.CONFIGROUTE_TO_FUDGEROUTE[vi2_.route_tag]:
			config_route = vi1_.route_tag
			vi1mofr = routes.latlon_to_mofr(vi1latlon, config_route)
			vi2mofr = routes.latlon_to_mofr(vi2latlon, config_route)
			if vi1mofr!=-1 and vi2mofr!=-1:
				interp_mofr = avg(vi1mofr, vi2mofr, ratio_)
				dir_tag_int = vi2_.dir_tag_int
				if dir_tag_int == None:
					raise Exception('Could not determine dir_tag_int of %s' % (str(vi2_)))
				r = routes.mofr_to_latlonnheading(interp_mofr, config_route, dir_tag_int)
	if r==None:
		r = ((avg(vi1latlon[0], vi2latlon[0], ratio_), avg(vi1latlon[1], vi2latlon[1], ratio_)), 
				avg_headings(vi1_.heading, vi2_.heading, ratio_))
	return r

def avg_headings(heading1_, heading2_, ratio_):
	if heading1_==-4 or heading2_==-4:
		return -4
	else:
		return avg(heading1_, heading2_, ratio_)

def angle(arm1_, origin_, arm2_):
	assert all(isinstance(e, XY) for e in (arm1_, origin_, arm2_))
	abs_ang1 = math.atan2(arm1_.y - origin_.y, arm1_.x - origin_.x)
	abs_ang2 = math.atan2(arm2_.y - origin_.y, arm2_.x - origin_.x)
	r = abs(abs_ang2 - abs_ang1)
	if r > math.pi:
		r = abs(r - 2*math.pi)
	elif r < -math.pi:
		r = r + 2*math.pi
	return r

def angle1(arm1lat_, arm1lon_, originlat_, originlon_, arm2lat_, arm2lon_):
	return math.degrees(angle(*(XY.from_latlon(x) for x in ((arm1lat_, arm1lon_), (originlat_, originlon_), (arm2lat_, arm2lon_)))))

def angle2(arm1lat_, arm1lon_, originlat_, originlon_, arm2lat_, arm2lon_):
	#printerr(math.degrees(angle2_half(originlat_, originlon_, arm1lat_, arm1lon_)), \
	#		math.degrees(angle2_half(originlat_, originlon_, arm2lat_, arm2lon_)))
	abs_ang1 = angle2_half(originlat_, originlon_, arm1lat_, arm1lon_)
	abs_ang2 = angle2_half(originlat_, originlon_, arm2lat_, arm2lon_)
	r = abs(abs_ang2 - abs_ang1)
	if r > math.pi:
		r = abs(r - 2*math.pi)
	elif r < -math.pi:
		r = r + 2*math.pi
	return r

def angle2_half(originlat_, originlon_, armlat_, armlon_):
	opposite = dist_latlon(LatLon(originlat_, armlon_), LatLon(armlat_, armlon_))
	adjacent = dist_latlon(LatLon(originlat_, armlon_), LatLon(originlat_, originlon_))
	r = math.atan2(opposite, adjacent)
	latdiff = armlat_ - originlat_; londiff = armlon_ - originlon_
	if londiff > 0 and latdiff > 0: # first quadrant 
		pass
	elif londiff <= 0 and latdiff > 0: # second quadrant 
		r = math.pi - r
	elif londiff <= 0 and latdiff <= 0: # third quadrant 
		r = -math.pi + r
	else: # fourth quadrant 
		r = -r
	return r

def passes(standpt_, forept_, post_, tolerance_=0):
	assert all(isinstance(x, XY) for x in (standpt_, forept_, post_))

	if standpt_ == forept_:
		return False
	ang1 = angle(forept_, standpt_, post_)
	ang2 = angle(standpt_, forept_, post_)
	r = all(x < math.pi/2 for x in (ang1, ang2))
	if r:
		passpt = get_pass_point(standpt_, forept_, post_)
		r = (dist(passpt, post_) < {0:50, 1:250, 2:600}[tolerance_])
	return r

def get_pass_point(standpt_, forept_, post_):
	ratio = get_pass_ratio(standpt_, forept_, post_)
	r = add(standpt_, scale(ratio, diff(forept_, standpt_)))
	return r

def get_pass_ratio(standpt_, forept_, post_):
	assert all(isinstance(e, XY) for e in (standpt_, forept_, post_))
	ang = angle(post_, standpt_, forept_)
	hypot = dist(standpt_, post_)
	adjacent = hypot*math.cos(ang)
	return adjacent/dist(forept_, standpt_)

def get_passing_vehicles(vilist_, dest_):
	r = []
	vids = set(vi.vehicle_id for vi in vilist_)
	for vid in vids:
		vid_visublist = sorted([vi for vi in vilist_ if vi.vehicle_id == vid], key=lambda vi: vi.time)
		for vis in hopscotch(vid_visublist):
			vpt0 = (vis[0].lat, vis[0].lon)
			vpt1 = (vis[1].lat, vis[1].lon)
			if passes(vpt0, vpt1, dest_):
				r.append(vis)
	return r

def dist(pt1_, pt2_):
	return math.hypot(pt2_.x - pt1_.x, pt2_.y - pt1_.y)

def diff(forepoint_, standpoint_):
	return XY((forepoint_.x - standpoint_.x, forepoint_.y - standpoint_.y))

def add(pt1_, pt2_):
	return XY((pt1_.x + pt2_.x, pt1_.y + pt2_.y))

def scale(factor_, pt_):
	assert type(factor_) in [int, long, float] and isinstance(pt_, XY)
	return XY((int(pt_.x*factor_), int(pt_.y*factor_)))

def heading(pt1_, pt2_):
	assert all(isinstance(x, XY) for x in (pt1_, pt2_))
	ang = math.degrees(math.atan2(pt2_.y - pt1_.y, pt2_.x - pt1_.x))
	if ang > 90:
		heading = get_range_val((90, 360), (180, 270), ang)
	else:
		heading = get_range_val((0, 90), (90, 0), ang)
	return int(heading)

def normalize_heading(heading_):
	r = heading_
	while r < 0:
		r += 360
	while r >= 360:
		r -= 360
	return r

def diff_headings(h1_, h2_):
	if h1_ > h2_:
		r = h1_ - h2_
	else:
		r = h2_ - h1_
	return normalize_heading(r)

def heading_from_latlons(pt1_, pt2_):
	assert all(isinstance(x, LatLon) for x in (pt1_, pt2_))
	return heading(XY.from_latlon(pt1_.tup()), XY.from_latlon(pt2_.tup()))

class LatLon:
	def __init__(self, arg1_, arg2_=None):
		if arg2_==None:
			assert isinstance(arg1_, XY)
			self.lat, self.lon = arg1_.latlon()
		else:
			assert type(arg1_) == float and type(arg2_) == float
			self.lat, self.lon = arg1_, arg2_

	def tup(self):
		return (self.lat, self.lon)

# returns: meters. int.  
def dist_latlon(pt1_, pt2_):
	assert all(isinstance(x, LatLon) for x in (pt1_, pt2_))
	# 'haversine formula' from http://en.wikipedia.org/wiki/Great-circle_distance 
	lat1 = radians(pt1_.lat); lon1 = radians(pt1_.lon)
	lat2 = radians(pt2_.lat); lon2 = radians(pt2_.lon)
	dlat = lat2 - lat1
	dlon = lon2 - lon1
	central_angle = 2*asin(sqrt(sin(dlat/2)**2 + cos(lat1)*cos(lat2)*(sin(dlon/2)**2)))
	RADIUS_OF_EARTH = 6367.44465
	return int(central_angle*RADIUS_OF_EARTH*1000)

# This is for removing buggy GPS readings (example: vehicle 4116 2012-06-15 13:30 to 14:00.)
def remove_bad_gps_readings(vis_):
	if not vis_:
		return
	assert isinstance(vis_[0], vinfo.VehicleInfo)
	r = []
	for vid in set(vi.vehicle_id for vi in vis_):
		vis_single_vid = [vi for vi in vis_ if vi.vehicle_id == vid]
		vis_single_vid.sort(key=lambda vi: vi.time, reverse=True)
		remove_bad_gps_readings_single_vid(vis_single_vid)
		r += vis_single_vid
	r.sort(key=lambda vi: vi.time, reverse=True)
	vis_[:] = r

def remove_consecutive_duplicates(list_, key=None):
	def get_key(val_):
		return (val_ if key==None else key(val_))
	curkey = get_key(list_[0]); prevkey = None
	i = 1
	while i < len(list_):
		prevkey = curkey
		curkey = get_key(list_[i])
		if prevkey == curkey:
			del list_[i]
			i -= 1
			curkey = prevkey
		i += 1

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

def mps_to_kmph(mps_):
	return mps_*60.0*60/1000;

def is_plausible(dist_m_, speed_kmph_):
	if dist_m_ < 1000:
		return speed_kmph_ < 60
	elif dist_m_ < 5000:
		return speed_kmph_ < 40
	else:
		return speed_kmph_ < 30

def remove_bad_gps_readings_single_vid(vis_):
	assert len(set(vi.vehicle_id for vi in vis_)) == 1
	if not vis_:
		return []
	vis = vis_[:]
	remove_consecutive_duplicates(vis, key=lambda vi: vi.time)
	vigroups = [[vis[0]]]
	for cur_vi in vis[1:]:
		def get_dist_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = dist_latlon(LatLon(cur_vi.xy), LatLon(groups_last_vi.xy))
			return groups_last_vi_to_cur_vi_metres

		def get_mps_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = dist_latlon(LatLon(cur_vi.xy), LatLon(groups_last_vi.xy))
			groups_last_vi_to_cur_vi_secs = abs((cur_vi.time - groups_last_vi.time)/1000.0)
			return groups_last_vi_to_cur_vi_metres/groups_last_vi_to_cur_vi_secs

		def is_plausible_vigroup(vigroup_):
			return is_plausible(get_dist_from_vigroup(vigroup_), mps_to_kmph(get_mps_from_vigroup(vigroup_)))

		vigroup = min(vigroups, key=get_dist_from_vigroup)
		if is_plausible_vigroup(vigroup):
			vigroup.append(cur_vi)
		else:
			vigroups.append([cur_vi])
	vis_[:] = max(vigroups, key=len)

def inside_polygon(latlon_, poly_):
	assert all(len(x) == 2 and isinstance(x[0], float) and isinstance(x[1], float) for x in [latlon_] + poly_)
	pt = XY.from_latlon(latlon_)
	poly = [XY.from_latlon(x) for x in poly_]
	sum_angles = 0
	for polypt1, polypt2 in hopscotch(poly + [poly[0]]):
		sum_angles += angle(polypt1, pt, polypt2)
	return (2*math.pi - sum_angles) < 0.0001

if __name__ == '__main__':

	with open('yards.json') as fin:
		print inside_polygon((43.6393901, -79.4484408), json.load(fin)[0])


