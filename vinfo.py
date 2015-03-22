#!/usr/bin/python2.6

import re, copy
import geom, routes, snapgraph, tracks, streets, c
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
			froute = min(froutes, key=lambda x: routes.latlon_to_mofrndist(x, geom.LatLng(lat, lng), tolerance_=2)[1])
		r = cls_(\
			str(elem_.getAttribute('dirTag')),
			int(elem_.getAttribute('heading')),
			str(elem_.getAttribute('id')),
			lat, lng, 
			(True if elem_.getAttribute('predictable').lower() == 'true' else False),
			froute, croute, 
			int(elem_.getAttribute('secsSinceReport')),  
			0L, 0L, None, None, None, None)
		return r

	@classmethod
	def from_db(cls_, dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, \
			time_retrieved_, time_, mofr_, widemofr_, graph_locs_str_, graph_version_):
		r = cls_(dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, time_retrieved_, time_,
				 (None if DONT_USE_WRITTEN_MOFRS else mofr_), (None if DONT_USE_WRITTEN_MOFRS else widemofr_), 
				 graph_locs_str_, graph_version_)
		return r

	def __init__(self, dir_tag_, heading_, vehicle_id_, lat_, lon_, predictable_, fudgeroute_, route_tag_, secs_since_report_, \
				time_retrieved_, time_, mofr_, widemofr_, graph_locs_str_, graph_version_):
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
		self.secs_since_report = max(secs_since_report_, 0) # -1 values are pretty common.  
				# A few per day according to a brief survey in march 2015. 
		self.time_retrieved = time_retrieved_
		self.time = time_
		self._mofr = mofr_
		self._widemofr = widemofr_
		self.is_dir_tag_corrected = False
		self.is_fudgeroute_corrected = False
		assert (graph_locs_str_ is None) == (graph_version_ is None)
		if graph_version_ == self.get_cur_graph_version():
			self._graph_locs_str = graph_locs_str_
		else:
			self._graph_locs_str = None
		self._graph_locs = None

	def get_snapgraph(self):
		if self.is_a_streetcar():
			return tracks.get_snapgraph()
		else:
			return streets.get_snapgraph()

	def get_cur_graph_version(self):
		if self.is_a_streetcar():
			return c.TRACKS_GRAPH_VERSION
		else:
			return c.STREETS_GRAPH_VERSION

	# This is a list where each element is either a PosAddr or a Vertex of the appropriate graph (tracks or streets). 
	# This list will be sorted in increasing order of distance to the reported location of this object i.e. self.latlng. 
	# (Assuming that SnapGraph.multisnap() still returns lists in this order.) 
	# If this is empty, then that means that self.latlng must not be anywhere near the appropriate graph.
	@property
	def graph_locs(self):
		if self._graph_locs is None:
			if self._graph_locs_str is None:
				self._graph_locs = self.get_snapgraph().multisnap(self.latlng, c.GRAPH_SNAP_RADIUS)
			else:
				self._graph_locs = snapgraph.parse_graph_locs_json_str(self._graph_locs_str, self.get_snapgraph())
		return self._graph_locs

	def get_graph_locs_json_str(self):
		return snapgraph.graph_locs_to_json_str(self.graph_locs)

	def __hash__(self):
		return hash(self.latlng.lat)

	def _key(self):
		return (self.dir_tag, self.heading, self.vehicle_id, self.latlng, self.predictable, self.fudgeroute, 
				self.route_tag, self.secs_since_report, self.time_retrieved, self.time, self._mofr, self._widemofr, 
				self.is_dir_tag_corrected, self.is_fudgeroute_corrected)

	EQ_ATTRS = ['time_retrieved', 'dir_tag', 'latlng', 'vehicle_id', 'mofr', 'widemofr', 'fudgeroute',
			'predictable', 'route_tag', 'time', 'heading', 'secs_since_report']

	def __eq__(self, other_):
		if self is other_:
			return True
		elif type(self) is not type(other_):
			return False
		else:
			for attr in self.__class__.EQ_ATTRS:
				if getattr(self, attr) != getattr(other_, attr):
					return False
			return True

	def __ne__(self, other_):
		return not self.__eq__(other_)

	FAST_PARTIAL_EQ_ATTRS = ['time', 'dir_tag', 'latlng', 'fudgeroute', 'route_tag']

	def fast_partial_eq(self, other_):
		if self is other_:
			return True
		else:
			for attr in self.__class__.FAST_PARTIAL_EQ_ATTRS:
				if getattr(self, attr) != getattr(other_, attr):
					return False
			return True

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

	def correct_fudgeroute(self, froute_):
		assert self.fudgeroute == '' and froute_ != '' # Just because that's all I had in mind when I wrote this.
				# Maybe this is useful for other cases too.  I don't know.
		self.fudgeroute = froute_
		self.route_tag = routes.FUDGEROUTE_TO_CONFIGROUTES[froute_][0]
		self.is_fudgeroute_corrected = True
		# mofr and widemofr are based on the route, so if we're changing the route, we had better cause these 
		# to be recalculated.
		self._mofr = self._widemofr = None

	def __str__(self):
		if self.fudgeroute in routes.SUBWAY_FUDGEROUTES:
			assert False # Not a big deal for this function, but since when do we have vehicle locations for subways? 
			routestr = self.fudgeroute
		else:
			routestr = '%s%3s%-3s' % ('*' if self.is_fudgeroute_corrected else ' ', self.fudgeroute[:3], self.route_tag)
			assert len(routestr) == 7 # Not that it's a big deal if it's greater than 7.  It's just that I would like to know, 
				# and probably rewrite this function, to make sure that the values it returns are always the same length, 
				# so that when I print out a list of them, every field lines up in the same columns. 
		mofrs_are_ok = (self.mofr == self.widemofr) or (self.mofr == -1 and self.widemofr != -1)
		time_retrieved_str = (em_to_str_millis(self.time_retrieved)[-9:] if self.time_retrieved - self.time < 1000*60 else '!'*9)
		return '%s (%s)  r=%-6s, vid=%s, dir: %s%-12s, (%.7f,%.7f), h=%3d, mofr=%5d%s%5d%s' \
			% (self.timestr, time_retrieved_str, routestr, self.vehicle_id, 
					('*' if self.is_dir_tag_corrected else ' '), self.dir_tag,
			   self.latlng.lat, self.latlng.lng, self.heading, self.mofr, (' ' if mofrs_are_ok else ' '), self.widemofr,
			   ('  ' if self.predictable else ' U'))

	def str_long(self):
		return self.__str__() + (' %s %d' % (self.get_graph_locs_json_str(), self.get_cur_graph_version()))

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
				'fudgeroute': self.fudgeroute, 
				'route_tag': self.route_tag, 
				'time': self.time, 
				'timestr': self.timestr, 
				'mofr': self.mofr, 
				'widemofr': self.widemofr
			}

	@property
	def timestr(self):
		return em_to_str_millis(self.time)

	@property
	def mofr(self):
		if self._mofr is None:
			self._mofr = routes.latlon_to_mofr(self.fudgeroute, self.latlng)
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
				self._widemofr = routes.latlon_to_mofr(self.fudgeroute, self.latlng, tolerance_=2)
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
		return is_a_streetcar(self.vehicle_id)

	# Be careful using this anywhere performance is important, because we nullify _graph_locs. 
	def copy(self):
		r = copy.copy(self)
		r.latlng = r.latlng.copy()
		r._graph_locs = None # Setting to None so that these will be recalculated on next use of the property. 
		return r

	def mofrchunk(self, mofrstep_):
		return int(self.widemofr)/mofrstep_

	def copy_pos_info(self, other_):
		self.latlng = other_.latlng.copy()
		# We could just copy the latlng and nullify the others, so that they are 
		# recalculated from the latlng on first use.  But copying these too will 
		# avoid that recalculation, and is a significant overall optimization.  
		self._graph_locs = other_.graph_locs[:] # Each element is either a PosAddr or a Vertex.  
				# The former is immutable and only a lunatic would modify the latter. 
		self._graph_locs_str = other_._graph_locs_str
		self._mofr = other_.mofr
		self._widemofr = other_.widemofr

def is_a_streetcar(vid_):
	# At least, I think that starting w/ 4 means streetcar.  This logic is also implemented in traffic.php. 
	return vid_.startswith('4') 

def makevi1(**kwargs):
	r = VehicleInfo('', -4, '9999', 43.0, -79.0, True, 'king', '504', 0, 0L, 0L, None, None, None, None)
	for key, val in kwargs.iteritems():
		setattr(r, key, val)
	r.calc_time()
	return r

def makevi(pos_, timestr_, *args_):
	yyyymmdd = '2020-01-01'
	if re.match(r'\d\d:\d\d', timestr_) or re.match(r'\d\d:\d\d:\d\d', timestr_):
		time_em = str_to_em('%s %s' % (yyyymmdd, timestr_))
	elif re.match(r'\d\d\d\d-\d\d-\d\d \d\d:\d\d.*', timestr_):
		time_em = str_to_em(timestr_)
	else:
		raise ValueError()

	r = VehicleInfo('', -4, '9999', 43.0, -79.0, True, 'dundas', '', 0, time_em, time_em, None, None, None, None)
	dir_int = 0
	for arg in args_:
		if isinstance(arg, str) and re.match(r'\d\d\d\d', arg):
			r.vehicle_id = arg
		elif isinstance(arg, str) and arg in routes.NON_SUBWAY_FUDGEROUTES:
			r.fudgeroute = arg
		elif arg in (0, 1):
			dir_int = arg
		else:
			raise ValueError()
	r.route_tag = routes.FUDGEROUTE_TO_CONFIGROUTES[r.fudgeroute][0]
	r.dir_tag = '%s_%d_%s' % (r.route_tag, dir_int, r.route_tag)

	if isinstance(pos_, Sequence):
		r.latlng = geom.LatLng(pos_[0], pos_[1])
	elif isinstance(pos_, int):
		r.latlng = routes.routeinfo(r.fudgeroute).mofr_to_latlon(pos_, dir_int)
		r.mofr = r.widemofr = pos_
		
	return r 

def same_vid(vis_):
	assert all(isinstance(vi, VehicleInfo) for vi in vis_)
	return len(set(vi.vehicle_id for vi in vis_)) <= 1

def same_dir(vis_):
	assert all(isinstance(vi, VehicleInfo) for vi in vis_)
	return len(set(vi.dir_tag_int for vi in vis_)) <= 1

def is_sorted_by_time(vis_):
	return is_sorted(vis_, key=lambda vi: vi.time)

if __name__ == '__main__':

	vi = make_vi(mofr=1000)
	print vi



