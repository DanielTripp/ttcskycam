#!/usr/bin/python2.6

import copy
import geom, routes
from misc import *

DONT_USE_WRITTEN_MOFRS = os.path.exists('DONT_USE_WRITTEN_MOFRS')

class VehicleInfo:
	
	@classmethod 
	def from_xml_elem(cls_, elem_):
		croute = str(elem_.getAttribute('routeTag'))
		lat = float(elem_.getAttribute('lat'))
		lng = float(elem_.getAttribute('lon'))
		froutes = routes.CONFIGROUTE_TO_FUDGEROUTES[croute]
		if len(froutes) == 0:
			froute = ''
		elif len(froutes) == 1:
			froute = froutes[0]
		else:
			for froute_candidate in froutes:
				if routes.latlon_to_mofr(froute_candidate, geom.LatLng(lat, lng)) != -1:
					froute = froute_candidate
					break
			else:
				froute = froutes[0]
		r = cls_(\
			str(elem_.getAttribute('dirTag')),
			int(elem_.getAttribute('heading')),
			str(elem_.getAttribute('id')),
			lat, lng, 
			(True if elem_.getAttribute('predictable').lower() == 'true' else False),
			froute, croute, 
			int(elem_.getAttribute('secsSinceReport')),  
			0L, 0L, None, None)
		return r

	@classmethod
	def from_db(cls_, dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, \
			time_retrieved_, time_, mofr_, widemofr_):
		r = cls_(dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, time_retrieved_, time_,
				 (None if DONT_USE_WRITTEN_MOFRS else mofr_), (None if DONT_USE_WRITTEN_MOFRS else widemofr_))
		return r

	def __init__(self, dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, \
				time_retrieved_, time_, mofr_, widemofr_):
		assert type(dir_tag_) == str and type(heading_) == int and type(vehicle_id_) == str \
			and type(lat_) == float and type(lon_) == float \
			and type(predictable_) == bool and type(route_tag_) == str \
			and type(secs_since_report_) == int and type(time_retrieved_) == long and type(time_) == long
		self.dir_tag = dir_tag_
		self.heading = heading_
		self.vehicle_id = vehicle_id_
		self.latlng = geom.LatLng(lat_, lon_)
		self.predictable = predictable_
		self.fudgeroute = fudgeroute_
		self.route_tag = route_tag_
		self.secs_since_report = secs_since_report_
		self.time_retrieved = time_retrieved_
		self.time = time_
		self._mofr = mofr_
		self._widemofr = widemofr_
		self.is_dir_tag_corrected = False

	def calc_time(self):
		self.time = self.time_retrieved - self.secs_since_report*1000

	# self.latlng represents the stand point.
	# arg post_ can be a LatLng, or an int representing a mofr.
	def get_pass_time_interp(self, forevi_, post_):
		assert (self.time < forevi_.time) and (isinstance(post_, geom.LatLng) or isinstance(post_, int))
		if isinstance(post_, geom.LatLng):
			assert geom.passes(self.latlng, forevi_.latlng, post_, tolerance_=2)
		else:
			if not (all(x != -1 for x in (self.mofr, forevi_.mofr, post_)) and betweenii(self.mofr, post_, forevi_.mofr)):
				raise Exception('This function, when passed a mofr int (%d) as a post_, needs vis with valid mofrs.  %s %s' % (post_, self, forevi_))
		if isinstance(post_, geom.LatLng):
			if self.latlng.dist_m(forevi_.latlng) < 0.001:
				if self.latlng.dist_m(post_) < 0.001:
					ratio = 0.0
				else:
					raise Exception('ratio (denominator) would have been zero.')
			ratio = geom.get_pass_ratio(self.latlng, forevi_.latlng, post_)
		else: # i.e. int
			if self.mofr == forevi_.mofr:
				if self.mofr == post_:
					ratio = 0.0
				else:
					raise Exception('ratio (denominator) would have been zero.')
			else:
				ratio = (post_ - self.mofr)/float(forevi_.mofr - self.mofr)
		return long(self.time + ratio*(forevi_.time - self.time))

	def __str__(self):
		if self.fudgeroute in routes.SUBWAY_FUDGEROUTES:
			assert False # Not a big deal for this function, but since when do we have vehicle locations for subways? 
			routestr = self.fudgeroute
		else:
			routestr = '%3s%-3s' % (self.fudgeroute[:3], self.route_tag)
			assert len(routestr) == 6 # Not that it's a big deal if it's greater than 6.  It's just that I would like to know, 
				# and probably rewrite this function, to make sure that the values it returns are always the same length, 
				# so that when I print out a list of them, every field lines up in the same columns. 
		return '%s  r=%-6s, vid=%s, dir: %s%-12s, (%.8f,%.8f), h=%3d, mofr=%5d%s%5d%s' \
			% (self.timestr, routestr, self.vehicle_id, ('*' if self.is_dir_tag_corrected else ' '), self.dir_tag,
			   self.latlng.lat, self.latlng.lng, self.heading, self.mofr, ('!' if self.mofr!=self.widemofr else ' '), self.widemofr,
			   ('' if self.predictable else ' UNPREDICTABLE'))

	def __repr__(self):
		return self.__str__()

	def to_json_dict(self):
		return {
				'dir_tag': self.dir_tag, 
				'heading': self.heading, 
				'vehicle_id': self.vehicle_id, 
				'lat': self.latlng.lat,
				'lon': self.latlng.lng,
				'predictable': self.predictable, 
				'route_tag': self.route_tag, 
				'time': self.time, 
				'timestr': self.timestr, 
				'mofr': self.mofr
			}

	@property
	def timestr(self):
		return em_to_str_millis(self.time)

	@property
	def mofr(self):
		if self._mofr is None:
			self._mofr = routes.latlon_to_mofr(self.route_tag, self.latlng)
		return self._mofr

	# widemofr is a higher-tolerance mofr than the regular mofr.  That is, it will indicate a mofr not just when
	# the latlng is close to the fudgeroute line, but up to 2 km away from it.
	# The main point of widemofr is to enable the fixing of dirtags even when the vehicle is taking a detour.
	# With widemofr we can check if widemofr is increasing or decreasing over time, and from that straightforwardly
	# determine whether the direction int of the dirtag should be 0 or 1.
	@property
	def widemofr(self):
		if self.mofr != -1:
			return self.mofr
		else:
			if self._widemofr is None:
				self._widemofr = routes.latlon_to_mofr(self.route_tag, self.latlng, tolerance_=2)
			return self._widemofr

	@property
	def dir_tag_int(self):
		return get_dir_tag_int(self.dir_tag)

	@property
	def lat(self):
		return self.latlng.lat

	@property 
	def lng(self):
		return self.latlng.lng

	def is_a_streetcar(self):
		# At least, I think that starting w/ 4 means streetcar.  This logic is also implemented in traffic.php. 
		return self.vehicle_id.startswith('4') 

	def copy(self):
		r = copy.copy(self)
		r.latlng = r.latlng.copy()
		return r

	def mofrchunk(self, mofrstep_):
		return int(self.widemofr)/mofrstep_

def make_vi(**kwargs):
	r = VehicleInfo('', -4, '9999', 43.0, -79.0, True, '', '', 0, 0L, 0L,
		None, None)
	for key, val in kwargs.iteritems():
		setattr(r, key, val)
	return r

if __name__ == '__main__':

	vi = make_vi(mofr=1000)
	print vi



