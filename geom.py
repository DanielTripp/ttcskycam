#!/usr/bin/python2.6

import datetime, calendar, math
from math import *
import vinfo, routes
from misc import *

class LatLng:

	def __init__(self, lat_, lng_=None):
		if type(lat_) == float:
			latlng = (lat_, lng_)
		else:
			assert lng_==None
			latlng = lat_
		assert len(latlng) == 2 and type(latlng[0]) == float and type(latlng[1]) == float
		self.lat = latlng[0]
		self.lng = latlng[1]

	def clone(self):
		return LatLng(self.lat, self.lng)

	# returns: meters. float.
	def dist_m(self, other_):
		assert isinstance(other_, LatLng)
		# 'Haversine formula' from http://en.wikipedia.org/wiki/Great-circle_distance
		lat1 = radians(self.lat); lng1 = radians(self.lng)
		lat2 = radians(other_.lat); lng2 = radians(other_.lng)
		dlat = lat2 - lat1
		dlng = lng2 - lng1
		central_angle = 2*asin(sqrt(sin(dlat/2)**2 + cos(lat1)*cos(lat2)*(sin(dlng/2)**2)))
		RADIUS_OF_EARTH = 6367.44465
		return central_angle*RADIUS_OF_EARTH*1000

	def add(self, other_):
		assert isinstance(other_, LatLng)
		return LatLng(self.lat+other_.lat, self.lng+other_.lng)

	def subtract(self, other_):
		return LatLng(self.lat - other_.lat, self.lng - other_.lng)

	def scale(self, factor_):
		assert isinstance(factor_, float)
		return LatLng(self.lat*factor_, self.lng*factor_)

	# Returns 'absolute angle' between two points (measured counter-clockwise from the positive X axis)
	# Returns between -pi and +pi.
	def abs_angle(self, fore_):
		assert isinstance(fore_, LatLng)
		opposite = LatLng(self.lat, fore_.lng).dist_m(LatLng(fore_.lat, fore_.lng))
		adjacent = LatLng(self.lat, fore_.lng).dist_m(LatLng(self.lat, self.lng))
		r = math.atan2(opposite, adjacent)
		latdiff = fore_.lat - self.lat; londiff = fore_.lng - self.lng
		if londiff > 0 and latdiff > 0: # first quadrant 
			pass
		elif londiff <= 0 and latdiff > 0: # second quadrant 
			r = math.pi - r
		elif londiff <= 0 and latdiff <= 0: # third quadrant 
			r = -math.pi + r
		else: # fourth quadrant 
			r = -r
		return r

	def heading(self, fore_):
		ang = math.degrees(self.abs_angle(fore_))
		if ang > 90:
			heading = get_range_val((90, 360), (180, 270), ang)
		else:
			heading = get_range_val((0, 90), (90, 0), ang)
		return int(heading)

	def avg(self, other_, ratio_=0.5):
		assert isinstance(other_, LatLng)
		return LatLng(avg(self.lat, other_.lat, ratio_), avg(self.lng, other_.lng, ratio_))

	def inside_polygon(self, poly_):
		assert all(isinstance(x, LatLng) for x in poly_)
		sum_angles = 0
		for polypt1, polypt2 in hopscotch(poly_ + [poly_[0]]):
			sum_angles += angle(polypt1, self, polypt2)
		return (2*math.pi - sum_angles) < 0.0001

	def is_within_box(self, southwest_, northeast_):
		assert isinstance(southwest_, LatLng) and isinstance(northeast_, LatLng)
		assert (southwest_.lat < northeast_.lat) and (southwest_.lng < northeast_.lng)
		return (southwest_.lat <= self.lat <= northeast_.lat) and (southwest_.lng <= self.lng <= northeast_.lng)

	def get_normalized_vector(self):
		# Assuming that self is a vector i.e. diff of  two positions, not a real lat/lng position itself. 
		dist_m = LatLng(0, 0).dist_m(self)
		if dist_m < 0.00001:
			raise Exception("Can't normalize a vector with length of zero.")
		return self.scale(1.0/dist_m)

	def __eq__(self, other_):
		assert isinstance(other_, LatLng)
		return self.lat == other_.lat and self.lng == other_.lng

	def __hash__(self):
		return int(self.lat*1000 + self.lng*1000)

	def __str__(self):
		return '(%.6f, %.6f)' % (self.lat, self.lng)

	def __repr__(self):
		return self.__str__()

def angle(arm1_, origin_, arm2_):
	assert isinstance(arm1_, LatLng) and isinstance(origin_, LatLng) and isinstance(arm2_, LatLng)
	abs_ang1 = origin_.abs_angle(arm1_)
	abs_ang2 = origin_.abs_angle(arm2_)
	r = abs(abs_ang2 - abs_ang1)
	if r > math.pi:
		r = abs(r - 2*math.pi)
	elif r < -math.pi:
		r = r + 2*math.pi
	return r

def passes(standpt_, forept_, post_, tolerance_=0):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)

	if standpt_ == forept_:
		return False
	ang1 = angle(forept_, standpt_, post_)
	ang2 = angle(standpt_, forept_, post_)
	r = all(x < math.pi/2 for x in (ang1, ang2))
	if r:
		passpt = get_pass_point(standpt_, forept_, post_)
		# There is no precise meaning behind the numbers below.
		r = (passpt.dist_m(post_) < {0:35, 1:175, 2:415}[tolerance_])
	return r

def get_pass_point(standpt_, forept_, post_):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)
	ratio = get_pass_ratio(standpt_, forept_, post_)
	r = standpt_.add(forept_.subtract(standpt_).scale(ratio))
	return r

def get_pass_ratio(standpt_, forept_, post_):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)
	ang = angle(post_, standpt_, forept_)
	hypot = standpt_.dist_m(post_)
	adjacent = hypot*math.cos(ang)
	return adjacent/forept_.dist_m(standpt_)

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

def normalize_heading(heading_):
	r = heading_
	while r < 0:
		r += 360
	while r >= 360:
		r -= 360
	return r

def diff_headings(h1_, h2_):
	return min(normalize_heading(h1_ - h2_), normalize_heading(h2_ - h1_))

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
	assert len(set(vi.vehicle_id for vi in vis_)) <= 1
	if not vis_:
		return []
	vis = vis_[:]
	remove_consecutive_duplicates(vis, key=lambda vi: vi.time)
	vigroups = [[vis[0]]]
	for cur_vi in vis[1:]:
		def get_dist_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = cur_vi.latlng.dist_m(groups_last_vi.latlng)
			return groups_last_vi_to_cur_vi_metres

		def get_mps_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = cur_vi.latlng.dist_m(groups_last_vi.latlng)
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


# Finds intersection of the line segments pt1->pt2 and pt3->pt4. 
# returns None if they don't intersect, a LatLng otherwise. 
def get_line_segment_intersection(pt1, pt2, pt3, pt4):
	assert isinstance(pt1, LatLng) and isinstance(pt2, LatLng) and isinstance(pt3, LatLng) and isinstance(pt4, LatLng) 
	determinant = (pt1.lng - pt2.lng)*(pt3.lat - pt4.lat) - (pt1.lat - pt2.lat)*(pt3.lng - pt4.lng)
	# Lines don't intersect if determinant is 0. 
	if abs(determinant) < 0.000000001:
		return None
	else:
		lng_numerator = (pt1.lng*pt2.lat - pt1.lat*pt2.lng)*(pt3.lng - pt4.lng) - (pt1.lng - pt2.lng)*(pt3.lng*pt4.lat - pt3.lat*pt4.lng)
		lat_numerator = (pt1.lng*pt2.lat - pt1.lat*pt2.lng)*(pt3.lat - pt4.lat) - (pt1.lat - pt2.lat)*(pt3.lng*pt4.lat - pt3.lat*pt4.lng)
		intersectpt = LatLng(lat_numerator/determinant, lng_numerator/determinant)
		# Now think of these two lines (line 1->2 and line 3->4) expressed parametrically i.e. 
		# (x,y) = ((1 - u)*pt1.x + u*pt2.x, (1 - u)*pt1.y + u*pt2.y)   (replace y with lat and x with lng.  And likewise 
		# for line 3->4 - and a different 'u' of course). 
		# If we're here, we already know that the lines intersect.  But the line /segments/ intersect only if 
		# the 'u' values for both lines are between 0 and 1.  So let's find them: 
		#find the parameter 'u', for each line, of the intersection point - when 
		if abs(pt2.lng - pt1.lng) > 0.000001:
			line_1_2_u = (intersectpt.lng - pt1.lng)/(pt2.lng - pt1.lng)
		else:
			line_1_2_u = (intersectpt.lat - pt1.lat)/(pt2.lat - pt1.lat)
		if abs(pt4.lng - pt3.lng) > 0.000001:
			line_3_4_u = (intersectpt.lng - pt3.lng)/(pt4.lng - pt3.lng)
		else:
			line_3_4_u = (intersectpt.lat - pt3.lat)/(pt4.lat - pt3.lat)
		if (0 <= line_1_2_u <= 1.0) and (0 <= line_3_4_u <= 1.0):
			return intersectpt
		else:
			return None


def does_line_segment_overlap_box(linesegpt1_, linesegpt2_, box_sw_, box_ne_):
	assert isinstance(linesegpt1_, LatLng) and isinstance(linesegpt2_, LatLng)
	assert isinstance(box_sw_, LatLng) and isinstance(box_ne_, LatLng)
	if linesegpt1_.is_within_box(box_sw_, box_ne_) or linesegpt2_.is_within_box(box_sw_, box_ne_):
		return True
	else:
		box_corners = [box_ne_, LatLng(box_sw_.lat, box_ne_.lng), box_sw_, LatLng(box_ne_.lat, box_sw_.lng)]
		for box_edge_pt1, box_edge_pt2 in hopscotch(box_corners + [box_corners[-1]]):
			if get_line_segment_intersection(box_edge_pt1, box_edge_pt2, linesegpt1_, linesegpt2_) is not None:
				return True
		return False

def constrain_line_segment_to_box(linesegpt1_, linesegpt2_, box_sw_, box_ne_):
	assert isinstance(linesegpt1_, LatLng) and isinstance(linesegpt2_, LatLng)
	assert isinstance(box_sw_, LatLng) and isinstance(box_ne_, LatLng)
	nw = LatLng(box_ne_.lat, box_sw_.lng)
	se = LatLng(box_sw_.lat, box_ne_.lng)
	box_sides = ((box_sw_, nw), (nw, box_ne_), (box_ne_, se), (se, box_sw_))
	line = [linesegpt1_, linesegpt2_]
	for i, linept in enumerate(line):
		if linept.is_within_box(box_sw_, box_ne_):
			continue
		box_side_intersections = []
		for box_side in box_sides:
			box_side_intersection = get_line_segment_intersection(line[0], line[1], box_side[0], box_side[1])
			if box_side_intersection is not None:
				box_side_intersections.append(box_side_intersection)
		if len(box_side_intersections) > 0:
			line[i] = min(box_side_intersections, key=lambda pt: pt.dist_m(linept))
	return tuple(line)

if __name__ == '__main__':


	rng = sorted(range(45, 360, 90) + range(0, 361, 90) + range(1, 361, 90) + range(89, 361, 90))
	rng = sorted(range(45, 360, 90))
	for h1 in rng:
		for h2 in rng:
			if diff_headings(h1, h2) != diff_headings_orig(h1, h2):
				print 'diff(%d,%d) - original: %d   new: %d' % (h1, h2, diff_headings_orig(h1, h2), diff_headings(h1, h2))

		


