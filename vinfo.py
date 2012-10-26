#!/usr/bin/python2.6

import geom, routes
from misc import *

class VehicleInfo:
	
	@classmethod 
	def from_xml_elem(cls_, elem_):
		r = cls_(\
			str(elem_.getAttribute('dirTag')),
			int(elem_.getAttribute('heading')),
			str(elem_.getAttribute('id')),
			float(elem_.getAttribute('lat')), float(elem_.getAttribute('lon')),
			(True if elem_.getAttribute('predictable').lower() == 'true' else False),
			str(elem_.getAttribute('routeTag')),
			int(elem_.getAttribute('secsSinceReport')),  
			0L, 0L)
		return r

	def __init__(self, dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, route_tag_, secs_since_report_, time_epoch_, time_):
		assert type(dir_tag_) == str and type(heading_) == int and type(vehicle_id_) == str \
			and type(lat_) == float and type(lon_) == float \
			and type(predictable_) == bool and type(route_tag_) == str \
			and type(secs_since_report_) == int and type(time_epoch_) == long and type(time_) == long
		self.dir_tag = dir_tag_
		self.heading = heading_
		self.vehicle_id = vehicle_id_
		self.latlng = geom.LatLng(lat_, lon_)
		self.predictable = predictable_
		self.route_tag = route_tag_
		self.secs_since_report = secs_since_report_
		self.time_epoch = time_epoch_
		self.time = time_
		self._mofr = None

	def calc_time(self):
		self.time = self.time_epoch - self.secs_since_report*1000

	def get_pass_time_interp(self, forevi_, post_):
		assert self.time < forevi_.time
		assert geom.passes(self.latlng, forevi_.latlng, post_)
		ratio = geom.get_pass_ratio(self.latlng, forevi_.latlng, post_)
		r = long(self.time + ratio*(forevi_.time - self.time))
		return r

	def __str__(self):
		return 'route: %s, vehicle: %s, dir: %-12s, (  %f, %f  )  , mofr: %5d, heading: %3d, time: %s %s' \
			% (self.route_tag, self.vehicle_id, self.dir_tag, self.latlng.lat, self.latlng.lng, self.mofr, self.heading, \
				em_to_str(self.time), ('' if self.predictable else 'UNPREDICTABLE'))

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
		return em_to_str(self.time)

	@property
	def mofr(self):
		if self._mofr == None:
			self._mofr = routes.latlon_to_mofr(self.latlng, self.route_tag)
		return self._mofr

	# Returns None if we don't seem to have one.  
	@property
	def fudgeroute(self):
		return routes.CONFIGROUTE_TO_FUDGEROUTE.get(self.route_tag)

	@property
	def dir_tag_int(self):
		is0 = '_0_' in self.dir_tag
		is1 = '_1_' in self.dir_tag
		if is0 and is1:
			raise Exception('dir_tag seems to indicate both directions (0 and 1).  %s' % str(self))
		elif is0:
			return 0
		elif is1:
			return 1
		else:
			return None

	@property 
	def lat(self):
		return self.latlng.lat

	@property 
	def lng(self):
		return self.latlng.lng

if __name__ == '__main__':
	pass


