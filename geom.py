#!/usr/bin/python2.6

import datetime, calendar, math, time
from math import *
from lru_cache import lru_cache
import vinfo, routes
from misc import *

RADIUS_OF_EARTH = 6367.44465

class LineSegSnapResult(object):

	# "pals" is for "Percent Along Line Segment".  Between 0.0 and 1.0, inclusive. 
	def __init__(self, latlng_, pals_, dist_):
		assert isinstance(latlng_, LatLng) and isinstance(pals_, float) and isinstance(dist_, float)
		assert 0.0 <= pals_ <= 1.0
		self.latlng = latlng_
		self.pals = pals_
		self.dist = dist_

	def __str__(self):
		return 'LineSegSnapResult( (%.8f,%.8f) pals:%.2f dist:%.2f )' % (self.latlng.lat, self.latlng.lng, self.pals, self.dist)

	def __repr__(self):
		return self.__str__()

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

	def copy(self):
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
		r = central_angle*RADIUS_OF_EARTH*1000
		return r

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
		opposite = LatLng(self.lat, fore_.lng).dist_m(fore_)
		adjacent = LatLng(self.lat, fore_.lng).dist_m(self)
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
		ang_degrees = math.degrees(self.abs_angle(fore_))
		return degrees_to_heading(ang_degrees)

	def avg(self, other_, ratio_=0.5):
		assert isinstance(other_, LatLng)
		return LatLng(avg(self.lat, other_.lat, ratio_), avg(self.lng, other_.lng, ratio_))

	# This only works for concave polygons.  TODO: handle all polygons. 
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
		# We're assuming that self is a vector i.e. diff of two positions, not a real lat/lng position itself. 
		dist_m = LatLng(0.0, 0.0).dist_m(self)
		if dist_m < 0.00001:
			raise Exception("Can't normalize a vector with length of zero.")
		return self.scale(1.0/dist_m)

	def _key(self):
		return (self.lat, self.lng)

	def __eq__(self, other_):
		assert isinstance(other_, LatLng)
		return self._key() == other_._key()

	def __ne__(self, other_):
		assert isinstance(other_, LatLng)
		return self._key() != other_._key()

	def __cmp__(self, other_):
		return cmp(self._key(), other_._key())

	def __hash__(self):
		return int(self.lat*100000 + self.lng*100000)

	def __str__(self):
		return '(%.7f,%.7f)' % (self.lat, self.lng) # Avoiding spaces in case one of these ends up in a memcache key.
			 # memcache doesn't handle spaces in keys.  We prevent memcache from seeing spaces in keys by replacing spaces with
			 # a big ugly string.  So really we're avoiding spaces here in order to minimize use of that big ugly string.

	def ls(self):
		return [self.lat, self.lng]

	def __repr__(self):
		return self.__str__()

	def copy(self):
		return LatLng(self.lat, self.lng)

	# returns a LineSegSnapResult.  Never None. 
	def snap_to_lineseg(self, lineseg_):
		assert isinstance(lineseg_, LineSeg)
		snappedpt, passratio = get_pass_point_and_ratio(lineseg_.start, lineseg_.end, self)
		if 0.0 <= passratio <= 1.0:
			return LineSegSnapResult(snappedpt, passratio, self.dist_m(snappedpt))
		elif passratio < 0.0:
			return LineSegSnapResult(lineseg_.start, 0.0, self.dist_m(lineseg_.start))
		else:
			return LineSegSnapResult(lineseg_.end, 1.0, self.dist_m(lineseg_.end))

	# returns (snapped_pt, dist_from_self_to_snapped_pt), or (None, None) if the snap fails. 
	# Unlike snap_to_lineseg(), this only works for points that are 'inside' the 
	# lineseg i.e. will snap to somewhere along it's length, rather than to the 
	# start or end point.   Also, this is faster than snap_to_lineseg(). 
	def snap_to_lineseg_opt(self, lineseg_, min_dist_from_ends_):
		assert isinstance(lineseg_, LineSeg)
		self_ang = angle(lineseg_.start, self, lineseg_.end)
		if self_ang > math.pi/2:
			start_ang = angle(self, lineseg_.start, lineseg_.end)
			hypot_len = lineseg_.start.dist_m(self)
			adjacent_len = hypot_len*math.cos(start_ang)
			lineseg_len = lineseg_.length_m()
			if min_dist_from_ends_ < adjacent_len < lineseg_len - min_dist_from_ends_:
				scale_factor = adjacent_len/lineseg_len
				snapped_pt = LatLng(avg(lineseg_.start.lat, lineseg_.end.lat, scale_factor), avg(lineseg_.start.lng, lineseg_.end.lng, scale_factor))
				opposite_len = hypot_len*math.sin(start_ang)
				return (snapped_pt, opposite_len)
		return (None, None)

	def dist_to_lineseg(self, lineseg_):
		return self.snap_to_lineseg(lineseg_).dist

	def is_close(self, other_, tolerance_=None):
		if tolerance_ is None:
			epsilon = 0.000001
			return abs(self.lat - other_.lat) < epsilon and abs(self.lng - other_.lng) < epsilon
		else:
			return self.dist_m(other_) <= tolerance_

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
	return get_pass_point_and_ratio(standpt_, forept_, post_)[0]

def get_pass_point_and_ratio(standpt_, forept_, post_):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)
	ratio = get_pass_ratio(standpt_, forept_, post_)
	pt = standpt_.add(forept_.subtract(standpt_).scale(ratio))
	return (pt, ratio)

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

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

def mps_to_kmph(mps_):
	return mps_*60.0*60/1000;

# Note [1]: This is to account for the small gps inaccuracies that nearly all readings seem to have.
# One can see this by drawing many vehicle locations on a google map with satellite view on.  Otherwise
# reasonable vehicles routinely appear in impossible places like on top of buildings.
# I don't know if there is any pattern to these inaccuracies.  I will assume that they are random and can
# change completely from one reading to the next.
# The large GPS errors (which are the entire reason for the 'remove bad gps' functions) have no limit to their
# magnitude that I can see.  The small GPS errors do, and it seems to be about 50 metres.  (That's 50 metres from one
# extreme to the other - i.e. 25 metres on either side of the road.  Note that we don't use mofrs here, only
# distance between latlngs.)
# (newer comment - 50 metres may not be enough.  eg. 2013-01-16 00:02:00.000 route: 505, vehicle: 4040, dir: '505_0_505' , ( 43.65366, -79.44915 ) , mofr: -1, heading: 140 
# These small GPS errors, combined with scenarios where a given reading in our database has a logged time very soon
# after the previous one (eg. 1 second or even less - as can happen in certain NextBus fluke scenarios I think, as well as
# the couple of times when I've mistakenly been polling for vehicle locations with two processes at the same time)
# can result in what looks like a very high speed.  This code treats a very high speed as a new 'vigroup'.  That is
# undesirable and in a bad case previously caused this code to create some erroneous vigroups, and then at the end when it
# picks the one containing the most vis, to throw out a lot of good vis.
# eg. vid 1660 between 2013-01-07 12:39:59 and 12:41:09, without the 'small GPS error if clause' below, would cause this code
# to create 2 new vigroups where it should have created no new ones.
def is_plausible(dist_m_, speed_kmph_):
	if dist_m_ < 50: # see note [1]
		return True
	elif dist_m_ < 1500:
		# The highest plausible speed that I've seen reported is 61.08 km/h.  This was on Queensway south of High Park, 
		# covering 1018 meters of track, over 60 seconds.   (vid 4119 around 2014-03-15 02:53.)
		return speed_kmph_ < 65 
	elif dist_m_ < 5000:
		return speed_kmph_ < 40
	else:
		return speed_kmph_ < 30

def remove_bad_gps_readings_single_vid(vis_, log_=False):
	assert is_sorted(vis_, reverse=True, key=lambda vi: vi.time)
	assert len(set(vi.vehicle_id for vi in vis_)) <= 1
	if not vis_:
		return []
	vis = vis_[::-1]
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

		closest_vigroup = min(vigroups, key=get_dist_from_vigroup)
		if is_plausible_vigroup(closest_vigroup):
			closest_vigroup.append(cur_vi)
		else:
			vigroups.append([cur_vi])
	r_vis = max(vigroups, key=len)
	if log_:
		vid = vis_[0].vehicle_id
		if len(vigroups) == 1:
			printerr('Bad GPS filtering - vid %s - there was only one group.' % vid)
		else:
			printerr('Bad GPS filtering - vid %s - chose group %d.' % (vid, vigroups.index(r_vis)))
			printerr('---')
			for vi in vis:
				groupidx = firstidx(vigroups, lambda vigroup: vi in vigroup)
				printerr('%d - %s' % (groupidx, vi))
			printerr('---')
			for groupidx, vigroup in enumerate(vigroups):
				for vi in vigroup:
					printerr('%d - %s' % (groupidx, vi))
			printerr('---')
		printerr('Bad GPS filtering - vid %s - groups as JSON:' % vid)
		printerr([[vi.latlng.ls() for vi in vigroup] for vigroup in vigroups])
	vis_[:] = r_vis[::-1]

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

def heading(pt1_, pt2_):
	return pt1_.heading(pt2_)

def degrees_to_heading(degrees_):
	if degrees_ > 90:
		r = get_range_val((90, 360), (180, 270), degrees_)
	else:
		r = get_range_val((0, 90), (90, 0), degrees_)
	return int(r)

def dist_m_polyline(pts_):
	assert all(isinstance(e, LatLng) for e in pts_)
	return sum(pt1.dist_m(pt2) for pt1, pt2 in hopscotch(pts_))

# I don't know if it's a coincidence or what, but the inverse of the 'degrees_to_heading' function is itself. 
def heading_to_degrees(heading_):
	return degrees_to_heading(heading_)

class BoundingBox:
	
	def __init__(self, polygon_pts_):
		assert all(isinstance(e, LatLng) for e in polygon_pts_)
		self.southwest = LatLng(min(pt.lat for pt in polygon_pts_), min(pt.lng for pt in polygon_pts_))
		self.northeast = LatLng(max(pt.lat for pt in polygon_pts_), max(pt.lng for pt in polygon_pts_))

	def __str__(self):
		return 'box:(%s, %s)' % (self.southwest, self.northeast)

	def __repr__(self):
		return self.__repr__()

class LineSeg(object):

	def __init__(self, start_, end_):
		assert isinstance(start_, LatLng) and isinstance(end_, LatLng)
		self.start = start_
		self.end = end_

	def __str__(self):
		return '[%s, %s]' % (self.start, self.end)

	def __repr__(self):
		return self.__str__()

	def __hash__(self):
		return hash(self.start) + hash(self.end)

	def __eq__(self, other_):
		return self.start == other_.start and self.end == other_.end

	def heading(self):
		return self.start.heading(self.end)

	def get_intersection(self, other_):
		return get_line_segment_intersection(self.start, self.end, other_.start, other_.end)

	def length_m(self):
		return self.start.dist_m(self.end)

	def ptlist(self):
		return [self.start, self.end]
		

def get_linesegs_in_polyline(polyline_):
	for startpt, endpt in hopscotch(polyline_):
		yield LineSeg(startpt, endpt)

# This function thanks to http://seewah.blogspot.ca/2009/11/gpolyline-decoding-in-python.html 
# Usage example: 
# latlngs = decode_line("grkyHhpc@B[[_IYiLiEgj@a@q@yEoAGi@bEyH_@aHj@m@^qAB{@IkHi@cHcAkPSiMJqEj@s@CkFp@sDfB}Ex@iBj@S_AyIkCcUWgAaA_JUyAFk@{D_]~KiLwAeCsHqJmBlAmFuXe@{DcByIZIYiBxBwAc@eCcAl@y@aEdCcBVJpHsEyAeE")
# for latlng in latlngs:
#     print str(latlng[0]) + "," + str(latlng[1])
def decode_line(encoded):

    """Decodes a polyline that was encoded using the Google Maps method.

    See http://code.google.com/apis/maps/documentation/polylinealgorithm.html
    
    This is a straightforward Python port of Mark McClure's JavaScript polyline decoder
    (http://facstaff.unca.edu/mcmcclur/GoogleMaps/EncodePolyline/decode.js)
    and Peter Chng's PHP polyline decode
    (http://unitstep.net/blog/2008/08/02/decoding-google-maps-encoded-polylines-using-php/)
    """

    encoded_len = len(encoded)
    index = 0
    array = []
    lat = 0
    lng = 0

    while index < encoded_len:

        b = 0
        shift = 0
        result = 0

        while True:
            b = ord(encoded[index]) - 63
            index = index + 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break

        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        shift = 0
        result = 0

        while True:
            b = ord(encoded[index]) - 63
            index = index + 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break

        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng

        array.append((lat * 1e-5, lng * 1e-5))

    return array

def latlng_avg(latlngs_):
	assert isinstance(latlngs_, Sequence) and all(isinstance(latlng, LatLng) for latlng in latlngs_)
	assert len(latlngs_) > 0
	lat_tally = 0.0; lng_tally = 0.0
	for latlng in latlngs_:
		lat_tally += latlng.lat
		lng_tally += latlng.lng
	avg_lat = lat_tally/len(latlngs_)
	avg_lng = lng_tally/len(latlngs_)
	return LatLng(avg_lat, avg_lng)

if __name__ == '__main__':


	rng = sorted(range(45, 360, 90) + range(0, 361, 90) + range(1, 361, 90) + range(89, 361, 90))
	rng = sorted(range(45, 360, 90))
	for h1 in rng:
		for h2 in rng:
			if diff_headings(h1, h2) != diff_headings_orig(h1, h2):
				print 'diff(%d,%d) - original: %d   new: %d' % (h1, h2, diff_headings_orig(h1, h2), diff_headings(h1, h2))

		


