#!/usr/bin/python2.6

import datetime, calendar, math, time, random
from math import *
from lru_cache import lru_cache
from misc import *

RADIUS_OF_EARTH_KM = 6367.44465

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

	@classmethod
	def make(cls_, raw_):
		return (LatLng(raw_) if raw_ is not None else None)

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
		r = central_angle*RADIUS_OF_EARTH_KM*1000
		return r

	def add(self, other_):
		assert isinstance(other_, LatLng)
		return LatLng(self.lat+other_.lat, self.lng+other_.lng)

	def subtract(self, other_):
		return LatLng(self.lat - other_.lat, self.lng - other_.lng)

	def scale(self, factor_):
		assert isinstance(factor_, float) or isinstance(factor_, int)
		return LatLng(self.lat*factor_, self.lng*factor_)

	# Returns 'absolute angle' between two points (measured counter-clockwise from the positive X axis)
	# Returns between -pi and +pi.
	# If 'self' and 'fore_' are equal, then this will return something meaningless (180?) but it won't 
	# raise an exception.
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

	# If 'self' and 'fore_' are equal, then this will return something meaningless (270?) but it won't 
	# raise an exception.
	def heading(self, fore_):
		ang_degrees = math.degrees(self.abs_angle(fore_))
		r = degrees_to_heading(ang_degrees)
		return r

	def avg(self, other_, ratio_=0.5):
		assert isinstance(other_, LatLng)
		return LatLng(avg(self.lat, other_.lat, ratio_), avg(self.lng, other_.lng, ratio_))

	# Only pass an 'open' polygon in here please.  i.e. last point of poly_ is not the same as the first point. 
	# Thanks to http://en.wikipedia.org/wiki/Point_in_polygon#Ray_casting_algorithm 
	def inside_polygon(self, poly_):
		assert is_seq_of(poly_, LatLng) and not poly_[0].is_close(poly_[-1], 5)
		# For the arbitrary direction of the ray required for this test, we'll use a horizontal eastward one.
		# Not really infinite, because I don't feel like coding that, but instead we'll use the lng value of 
		# the most-eastward point in the poly.   Plus 1.0 for safety. 
		ray_lineseg = LineSeg(self, LatLng(self.lat, max(pt.lng for pt in poly_)+1.0))
		num_intersections = 0
		for polypt1, polypt2 in hopscotch(poly_ + [poly_[0]]):
			intersect_pt = get_line_segment_intersection(polypt1, polypt2, ray_lineseg.start, ray_lineseg.end)
			if intersect_pt is not None:
				num_intersections += 1
		return (num_intersections % 2 == 1)

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
		if type(self) != type(other_):
			return False
		else:
			# Not using _key().  This way is a bit faster.  
			return (self.lat == other_.lat and self.lng == other_.lng)

	def __ne__(self, other_):
		if not isinstance(other_, LatLng):
			return True
		else:
			return self._key() != other_._key()

	def __cmp__(self, other_):
		assert isinstance(other_, LatLng)
		return cmp(self._key(), other_._key())

	def __hash__(self):
		return hash(self.lat + self.lng)

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

	def tuple(self):
		return (self.lat, self.lng)

	# Thanks to http://www.movable-type.co.uk/scripts/latlong.html 
	def offset(self, heading_, dist_):
		lat1 = math.radians(self.lat); lon1 = math.radians(self.lng)
		R = RADIUS_OF_EARTH_KM*1000
		d = dist_
		brng = math.radians(heading_)
		lat2 = math.asin(math.sin(lat1)*math.cos(d/R) + math.cos(lat1)*math.sin(d/R)*math.cos(brng))
		lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1), math.cos(d/R)-math.sin(lat1)*math.sin(lat2))
		return LatLng(math.degrees(lat2), math.degrees(lon2))

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
	standpt_forept_dist = standpt_.dist_m(forept_)
	if standpt_forept_dist < 0.0001:
		return 0.0
	else:
		ang = angle(post_, standpt_, forept_)
		hypot = standpt_.dist_m(post_)
		adjacent = hypot*math.cos(ang)
		return adjacent/standpt_forept_dist

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
	
	def __init__(self, pts_):
		assert all(isinstance(e, LatLng) for e in pts_)
		minlat = float('inf'); minlng = float('inf'); maxlat = float('-inf'); maxlng = float('-inf')
		for pt in pts_:
			minlat = min(minlat, pt.lat)
			minlng = min(minlng, pt.lng)
			maxlat = max(maxlat, pt.lat)
			maxlng = max(maxlng, pt.lng)
		self.southwest = LatLng(minlat, minlng)
		self.northeast = LatLng(maxlat, maxlng)

	@property
	def northwest(self):
		return LatLng(self.northeast.lat, self.southwest.lng)

	@property
	def southeast(self):
		return LatLng(self.southwest.lat, self.northeast.lng)

	@property
	def minlng(self):
		return self.southwest.lng

	@property
	def maxlng(self):
		return self.northeast.lng

	@property
	def minlat(self):
		return self.southwest.lat

	@property
	def maxlat(self):
		return self.northeast.lat

	def __str__(self):
		return 'box:(%s, %s)' % (self.southwest, self.northeast)

	def __repr__(self):
		return self.__str__()

	def get_enlarged(self, radius_):
		latheadroom = math.degrees(radius_/(RADIUS_OF_EARTH_KM*1000))
		latheadroom *= 1.1 # Giving it extra room, to make me feel feel safer. 
		r_maxlat = self.maxlat + latheadroom
		r_minlat = self.minlat - latheadroom

		r_minlng = self.minlng
		while True:
			r_nw = LatLng(self.maxlat, r_minlng)
			r_sw = LatLng(self.minlat, r_minlng)
			if r_nw.dist_m(self.northwest) > radius_ and r_sw.dist_m(self.southwest) > radius_:
				break
			r_minlng -= 0.005
		r_maxlng = self.maxlng + (self.minlng - r_minlng)

		r_sw = LatLng(r_minlat, r_minlng)
		r_ne = LatLng(r_maxlat, r_maxlng)
		return BoundingBox([r_sw, r_ne])

	def is_inside(self, latlng_):
		assert isinstance(latlng_, LatLng)
		return (self.southwest.lat < latlng_.lat < self.northeast.lat) and \
				(self.southwest.lng < latlng_.lng < self.northeast.lng)

	def rand_latlng(self):
		lat = avg(self.minlat, self.maxlat, random.random())
		lng = avg(self.minlng, self.maxlng, random.random())
		return LatLng(lat, lng)

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

def decode_line(encoded_):
	return [LatLng(lat/10.0, lng/10.0) for lat, lng in decode_line_raw(encoded_)]

# This function thanks to http://seewah.blogspot.ca/2009/11/gpolyline-decoding-in-python.html 
# This function returns lats and lngs 10 times too big eg. (436.82132,-794.33430).  I don't know why. 
def decode_line_raw(encoded):

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

# Does not modify argument. 
# Thanks to http://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm 
def get_simplified_polyline_via_rdp_algo(pline_, epsilon_):
	log = False
	if len(pline_) <= 2:
		return pline_
	dmax = 0
	index = 0
	if log:
		printerr('---')
		printerr('pline:', pline_)
	if pline_[0].is_close(pline_[-1]):
		# so pline_ is a loop, and the dist_to_lineseg() call below will fail if we try it.  
		# let's go straight to the recurse.  
		dmax = epsilon_*2
		index = len(pline_)/2
		if log: printerr('loop')
	else:
		for i in range(1, len(pline_)-1):
			d = pline_[i].dist_to_lineseg(LineSeg(pline_[0], pline_[-1]))
			if d > dmax:
				index = i
				dmax = d

	# If max distance is greater than epsilon, recursively simplify
	if dmax > epsilon_:
		recResults1 = get_simplified_polyline_via_rdp_algo(pline_[0:index+1], epsilon_)
		recResults2 = get_simplified_polyline_via_rdp_algo(pline_[index:], epsilon_)
		r = recResults1[:-1] + recResults2
		if log:
			printerr('pline again:', pline_)
			printerr('epsilon was exceeded by pt %d (%s).  recursed.' % (index, pline_[index]))
			printerr('recursive results:')
			printerr(recResults1)
			printerr(recResults2)
			printerr('combining into:')
			printerr(r)
			printerr('---')
		return r
	else:
		if log: 
			printerr('epsilon not exceeded.')
			printerr('---')
		return [pline_[0], pline_[-1]]

def get_split_pline(pt1_, pt2_, n_):
	assert isinstance(pt1_, LatLng) and isinstance(pt2_, LatLng) and isinstance(n_, int)
	r = [pt1_]
	for step in xrange(1, n_):
		ratio = float(step)/n_
		r.append(LatLng(avg(pt1_.lat, pt2_.lat, ratio), avg(pt1_.lng, pt2_.lng, ratio)))
	r.append(pt2_)
	return r
		
if __name__ == '__main__':


	rng = sorted(range(45, 360, 90) + range(0, 361, 90) + range(1, 361, 90) + range(89, 361, 90))
	rng = sorted(range(45, 360, 90))
	for h1 in rng:
		for h2 in rng:
			if diff_headings(h1, h2) != diff_headings_orig(h1, h2):
				print 'diff(%d,%d) - original: %d   new: %d' % (h1, h2, diff_headings_orig(h1, h2), diff_headings(h1, h2))

		


