#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys, json, os.path, bisect, xml.dom, xml.dom.minidom
import vinfo, geom, mc, c, snapgraph, picklestore, util
from misc import *
from lru_cache import lru_cache

FUDGEROUTE_TO_CONFIGROUTES = {'dundas': ['505'], 'queen': ['501', '301', '502', '503', '508'], 'king': ['504', '508', '503'], 
'spadina': ['510'], 
'bathurst': ['511', '310', '7'], 'dufferin': ['29', '329'], 'lansdowne': ['47'], 'ossington': ['63', '316'], 'carlton': ['506', '306'], 
'dupont': ['26'], 'stclair': ['512', '312'], 'keele': ['41'], 
'harbourfront': ['509'], 'wellesley': ['94'], 'sherbourne': ['75'], 'parliament': ['65'], 'symington': ['168'], 
'davenport': ['127'], 'junction': ['40'], 'pape': ['72'], 'jones': ['83'], 'greenwood': ['31'], 'coxwell': ['22', '322'], 
'woodbinesouth': ['92'], 'main': ['64'], 
}

CONFIGROUTE_TO_FUDGEROUTES = defaultdict(lambda: [])
for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
	for configroute in configroutes:
		CONFIGROUTE_TO_FUDGEROUTES[configroute].append(fudgeroute)

SUBWAY_FUDGEROUTES = sorted(['bloor_danforth', 'yonge_university_spadina'])
NON_SUBWAY_FUDGEROUTES = sorted(FUDGEROUTE_TO_CONFIGROUTES.keys())
FUDGEROUTES = NON_SUBWAY_FUDGEROUTES + SUBWAY_FUDGEROUTES
CONFIGROUTES = set(reduce(lambda x, y: x + y, FUDGEROUTE_TO_CONFIGROUTES.values(), []))

SPLIT_ROUTE_LEN_DIFF_TOLERANCE = 0.1

# In some places we use a 3-character prefix of fudgeroutes and assume that it will identify them uniqiuely. 
# That code is for testing only but it's still important. 
# So here let's assert that no two fudgeroutes have the same 3-character prefix.
if len(FUDGEROUTES) != len(set(froute[:3] for froute in FUDGEROUTES)):
	raise Exception()

def is_subway(froute_):
	assert froute_ in FUDGEROUTES
	return froute_ in SUBWAY_FUDGEROUTES

class Schedule(object):

	def __init__(self, froute_, schedule_nextbus_xml_filename_):
		dom = xml.dom.minidom.parse(schedule_nextbus_xml_filename_)
		self.froute = froute_
		self.init_dir_to_serviceclass_to_fblockid_to_stoptag_to_time(dom)
		self.init_dir_to_serviceclass_to_stoptag_to_time_to_fblockid()
		self.init_header_dir_to_serviceclass_to_stoptag_to_name(dom)

	def init_header_dir_to_serviceclass_to_stoptag_to_name(self, dom_):
		m = {0: {}, 1: {}}
		for route_elem in [x for x in dom_.documentElement.childNodes if x.nodeName == 'route']:
			serviceclass = str(route_elem.getAttribute('serviceClass'))
			direction_str = str(route_elem.getAttribute('direction'))
			direction_int = compassdir_string_to_dir_int(self.froute, direction_str)
			m[direction_int][serviceclass] = {}
			header_elem = [x for x in route_elem.childNodes if x.nodeName == 'header'][0]
			for stop_elem in [x for x in header_elem.childNodes if x.nodeName == 'stop']:
				stoptag = str(stop_elem.getAttribute('tag')) # cast to str() gets rid of unicode.
				name = str(stop_elem.firstChild.nodeValue)
				m[direction_int][serviceclass][stoptag] = name
		self.header_dir_to_serviceclass_to_stoptag_to_name = m


	# 'fblockid' AKA fudgeblockid is our invention.  It is a way of making a unique id out of blockids.
	# As returned by NextBus they are not unique within a schedule's service day.  eg. 505 Dundas -
	# blockid 505_1_10 appears once mentioning scheduled stops between 05:12 and 05:20, then again from 06:05 to 06:51,
	# then again from 07:44 to 08:31, and so on.
	# For our purposes we turn the first appearance into an fblockid of 505_1_10-0, the second into 505_1_10-1, etc.
	def init_dir_to_serviceclass_to_fblockid_to_stoptag_to_time(self, dom_):
		m = {0: {}, 1: {}}
		for route_elem in [x for x in dom_.documentElement.childNodes if x.nodeName == 'route']:
			serviceclass = str(route_elem.getAttribute('serviceClass'))
			direction_str = str(route_elem.getAttribute('direction'))
			direction_int = compassdir_string_to_dir_int(self.froute, direction_str)
			if serviceclass in m[direction_int]: raise Exception()
			m[direction_int][serviceclass] = {}
			for block_elem in [x for x in route_elem.childNodes if x.nodeName == 'tr']:
				blockid = str(block_elem.getAttribute('blockID'))
				fblockidnum = len([x for x in m[direction_int][serviceclass].keys() if x.startswith(blockid)])
				fblockid = '%s-%d' % (blockid, fblockidnum)
				assert fblockid not in m[direction_int][serviceclass]
				m[direction_int][serviceclass][fblockid] = {}
				for stop_elem in [x for x in block_elem.childNodes if x.nodeName == 'stop']:
					stoptag = str(stop_elem.getAttribute('tag'))
					epoch_time = long(stop_elem.getAttribute('epochTime'))
					if stoptag in m[direction_int][serviceclass][fblockid]: raise Exception()
					if routeinfo(self.froute).get_stop(stoptag) is None:
						continue # this will be the case eg. stop 5520 on 47C Lansdowne - Orfus road branch - we can't deal with that yet
							# so we can't add this scheduled stop to our schedule.  But we still want the rest of this block's schedule,
							# because most of the branch is probably on our fudgeroute.
					m[direction_int][serviceclass][fblockid][stoptag] = epoch_time
		self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time = m
		self.verify_dir_to_serviceclass_to_fblockid_to_stoptag_to_time()

	def verify_dir_to_serviceclass_to_fblockid_to_stoptag_to_time(self):
		ri = routeinfo(self.froute)
		def fail(): raise Exception()
		m = self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time
		def get_serviceclasses(dir_):
			return set(m[dir_].keys())
		if get_serviceclasses(0) != get_serviceclasses(1): # ensure same set of serviceclasses for both directions
			fail()
		for direction in (0, 1):
			for fblockid_to_stoptag_to_time in m[direction].itervalues():
				all_blocks_stoptags = [stoptag_to_time.keys() for stoptag_to_time in fblockid_to_stoptag_to_time.itervalues()]
				# ensure each block mentions the same list of stoptags, and in same order:
				for block1_stoptags, block2_stoptags in hopscotch(all_blocks_stoptags):
					if block1_stoptags != block2_stoptags:
						fail()

	def init_dir_to_serviceclass_to_stoptag_to_time_to_fblockid(self):
		m = {0: {}, 1: {}}
		for dir, serviceclass_to_fblockid_to_stoptag_to_time in self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time.iteritems():
			m[dir] = {}
			for serviceclass, fblockid_to_stoptag_to_time in serviceclass_to_fblockid_to_stoptag_to_time.iteritems():
				m[dir][serviceclass] = defaultdict(lambda: sorteddict())
				for fblockid, stoptag_to_time in fblockid_to_stoptag_to_time.iteritems():
					for stoptag, tyme in stoptag_to_time.iteritems():
						if tyme != -1:
							m[dir][serviceclass][stoptag][tyme] = fblockid
				m[dir][serviceclass] = dict(m[dir][serviceclass]) # making this not a defaultdict, because defaultdict can't be pickled.
		self.dir_to_serviceclass_to_stoptag_to_time_to_fblockid = m

	def time(self, dir_, serviceclass_, fblockid_, stoptag_):
		return self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time[dir_][serviceclass_][fblockid_][stoptag_]

	def stoptag_to_time(self, dir_, serviceclass_, fblockid_):
		return self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time[dir_][serviceclass_][fblockid_]

	def has_stoptag(self, dir_, serviceclass_, stoptag_):
		return stoptag_ in self.dir_to_serviceclass_to_stoptag_to_time_to_fblockid[dir_][serviceclass_]

	def time_to_fblockid(self, dir_, serviceclass_, stoptag_):
		return self.dir_to_serviceclass_to_stoptag_to_time_to_fblockid[dir_][serviceclass_][stoptag_]

	def get_caught_and_arrival_time_within_day(self, startstoptag_, deststoptag_, start_time_):
		ri = routeinfo(self.froute)
		serviceclass = time_to_serviceclass(start_time_)
		direction = ri.get_stop(startstoptag_).direction
		assert ri.get_stop(startstoptag_).direction == ri.get_stop(deststoptag_).direction
		start_time_within_day = get_time_millis_within_day(start_time_)
		startstop_time_to_fblockid = self.get_expanded_time_to_fblockid(direction, serviceclass, startstoptag_)
		caught_time_within_day, caught_fblockid = startstop_time_to_fblockid.ceilitem(start_time_within_day)
		arrival_time_within_day = self.get_expanded_fblockid_to_time(direction, serviceclass, deststoptag_)[caught_fblockid]
		assert arrival_time_within_day != -1 # TODO: be sure to catch the right block by seeing if it services deststop.
		return (caught_time_within_day, arrival_time_within_day)

	# time in epoch millis.
	def get_arrival_time(self, startstoptag_, deststoptag_, start_time_):
		caught_time_within_day, arrival_time_within_day = self.get_caught_and_arrival_time_within_day(startstoptag_, deststoptag_, start_time_)
		arrival_time = round_down_to_midnight(start_time_) + arrival_time_within_day
		return arrival_time

	# return millis.
	def get_ride_time(self, startstoptag_, deststoptag_, start_time_):
		caught_time_within_day, arrival_time_within_day = self.get_caught_and_arrival_time_within_day(startstoptag_, deststoptag_, start_time_)
		return (arrival_time_within_day - caught_time_within_day)

	# Doing the same thing as get_expanded_stoptag_to_time() but for different values.
	# return a sorteddict.
	def get_expanded_time_to_fblockid(self, dir_, serviceclass_, stoptag_):
		ri = routeinfo(self.froute)
		stop = ri.get_stop(stoptag_)
		assert stop.direction == dir_
		r = {}
		for fblockid in self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time[dir_][serviceclass_].iterkeys():
			scheduled_stoptag_to_time = self.stoptag_to_time(dir_, serviceclass_, fblockid)
			if stoptag_ in scheduled_stoptag_to_time and scheduled_stoptag_to_time[stoptag_] != -1:
				r[scheduled_stoptag_to_time[stoptag_]] = fblockid
			else:
				scheduled_mofr_to_stoptag = self.get_scheduled_mofr_to_stoptag(dir_, serviceclass_, fblockid)
				lesser_stoptag, greater_stoptag = scheduled_mofr_to_stoptag.boundingvalues(stop.mofr,
						lambda mofr, stoptag: scheduled_stoptag_to_time[stoptag] != -1)
				if lesser_stoptag is not None and greater_stoptag is not None:
					def get_scheduled_mofrntime(scheduled_stoptag_):
						return (ri.get_stop(scheduled_stoptag_).mofr, scheduled_stoptag_to_time[scheduled_stoptag_])
					lesser_mofrntime = get_scheduled_mofrntime(lesser_stoptag)
					greater_mofrntime = get_scheduled_mofrntime(greater_stoptag)
					assert lesser_mofrntime[1] != -1 and greater_mofrntime[1] != -1
					interp_time = get_range_val(lesser_mofrntime, greater_mofrntime, stop.mofr)
					r[interp_time] = fblockid
		return sorteddict(r)

	def get_expanded_fblockid_to_time(self, dir_, serviceclass_, stoptag_):
		return invert_dict(self.get_expanded_time_to_fblockid(dir_, serviceclass_, stoptag_))

	# NextBus schedules only mention a handful of stops, but it's straightforward to infer a schedule for all stops by
	# interpolating by mofr between the scheduled stops.  That's what this does.
	# note [1]: There are some odd cases to deal with eg. King / wkd / east - block 504_25_430 (and many others) -
	# the NextBus schedule mentions stoptag 3443 in all blocks but not very many have a time other than -1.  Same with stoptag 7672.
	# So here we use the scheduled time if it's not -1, otherwise we search in either direction for the nearest stops w/ time != -1.
	def get_expanded_stoptag_to_time(self, dir_, serviceclass_, fblockid_):
		ri = routeinfo(self.froute)
		scheduled_stoptag_to_time = self.stoptag_to_time(dir_, serviceclass_, fblockid_)
		scheduled_mofr_to_stoptag = self.get_scheduled_mofr_to_stoptag(dir_, serviceclass_, fblockid_)
		r = {}
		for stoptag, stop in ri.dir_to_stoptag_to_stop[dir_].iteritems():
			if stoptag in scheduled_stoptag_to_time and scheduled_stoptag_to_time[stoptag] != -1: # note [1]
				r[stoptag] = scheduled_stoptag_to_time[stoptag]
			else:
				lesser_stoptag, greater_stoptag = scheduled_mofr_to_stoptag.boundingvalues(stop.mofr,
						lambda mofr, stoptag: scheduled_stoptag_to_time[stoptag] != -1)
				if lesser_stoptag is None or greater_stoptag is None:
					r[stoptag] = -1
				else:
					def get_scheduled_mofrntime(scheduled_stoptag_):
						return (ri.get_stop(scheduled_stoptag_).mofr, scheduled_stoptag_to_time[scheduled_stoptag_])
					lesser_mofrntime = get_scheduled_mofrntime(lesser_stoptag)
					greater_mofrntime = get_scheduled_mofrntime(greater_stoptag)
					assert lesser_mofrntime[1] != -1 and greater_mofrntime[1] != -1
					r[stoptag] = get_range_val(lesser_mofrntime, greater_mofrntime, stop.mofr)
		return r

	def get_scheduled_mofr_to_stoptag(self, dir_, serviceclass_, fblockid_):
		ri = routeinfo(self.froute)
		scheduled_stoptag_to_time = self.stoptag_to_time(dir_, serviceclass_, fblockid_)
		r = sorteddict()
		for scheduled_stoptag in scheduled_stoptag_to_time.keys():
			r[ri.get_stop(scheduled_stoptag).mofr] = scheduled_stoptag
		return r

	def get_header_name(self, dir_, serviceclass_, stoptag_):
		return self.header_dir_to_serviceclass_to_stoptag_to_name[dir_][serviceclass_][stoptag_]

	def pprint(self):
		ri = routeinfo(self.froute)
		for direction in (0, 1):
			for serviceclass in sorted(self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time[direction].keys(),
					key=lambda x: defaultdict(lambda x: x, {'wkd':0, 'sat':1, 'sun':2})[x]):
				fblockid_to_stoptag_to_time = self.dir_to_serviceclass_to_fblockid_to_stoptag_to_time[direction][serviceclass]
				def get_block_start_time(fblockid__):
					return max(fblockid_to_stoptag_to_time[fblockid__].values())
				for fblockid in sorted(fblockid_to_stoptag_to_time.keys(), key=get_block_start_time):
					stoptag_to_time = fblockid_to_stoptag_to_time[fblockid]
					for stoptag in sorted(stoptag_to_time.keys(), key=lambda x: ri.get_stop(x).mofr, reverse=(direction==1)):
						tyme = stoptag_to_time[stoptag]
						header_stop_name = self.get_header_name(direction, serviceclass, stoptag)
						print '%d %s %s %8s %8s (%s)' \
							  % (direction, serviceclass, fblockid, stoptag, millis_within_day_to_str(tyme), header_stop_name)
					print '---'


@lru_cache(20)
@mc.decorate
def schedule(froute_):
	if froute_ in ('king', 'dundas', 'lansdowne'):
		return Schedule(froute_, '%s-schedule.xml' % froute_)
	else:
		raise Exception('not yet implemented')

class Stop:
	def __init__(self, stoptag_, latlng_, direction_, mofr_, dirtags_serviced_):
		assert isinstance(stoptag_, basestring) and isinstance(latlng_, geom.LatLng) and isinstance(mofr_, int)
		self.latlng = latlng_
		self.stoptag = stoptag_
		self.direction = direction_
		self.mofr = mofr_
		self.dirtags_serviced = dirtags_serviced_

	@property 
	def is_sunday_only(self):
		if len(self.dirtags_serviced) == 0: # route must be a subway 
			return False
		for dirtag in self.dirtags_serviced:
			if not dirtag[-3:].lower() == 'sun':
				return False
		return True 

	def __str__(self):
		return 'Stop %10s mofr=%d ( %f, %f )' % ('"'+self.stoptag+'"', self.mofr, self.latlng.lat, self.latlng.lng)

	def __repr__(self):
		return self.__str__()

class RouteInfo:
	def __init__(self, routename_):
		self.name = routename_
		self.init_version()
		self.init_routepts()
		# Note from August 2014: 
		# I think that I was using stops when I polled predictions as an experiment and/or with old pre-graph 
		# 'paths' code (now: system.py / SystemSnapGraph).  Regardless of what I used to use stops for, 
		# I don't use them now, so I don't feel like getting these files as I add new routes. 
		# So I'm commenting this call to init_stops() out. 
		#self.init_stops()

	def init_version(self):
		with open(os.path.join('routes', self.name, 'version.txt')) as fin:
			self.version = int(fin.read().strip())

	def init_routepts(self):
		def read_pts_file(filename_):
			with open(filename_) as fin:
				r = []
				for raw_routept in json.load(fin):
					r.append(geom.LatLng(raw_routept[0], raw_routept[1]))
				return r

		routepts_both_dirs_filename = os.path.join('routes', self.name, 'points.json')
		if os.path.exists(routepts_both_dirs_filename):
			routepts = [read_pts_file(routepts_both_dirs_filename)]
			self.is_split_by_dir = False
		else:
			routepts = [read_pts_file(os.path.join('routes', self.name, 'points-dir%d.json' % direction)) for direction in (0, 1)]
			if (routepts[0][0] != routepts[1][0]) or (routepts[0][-1] != routepts[1][-1]):
				raise Exception('one or both split route endpoints are not equal')
			stretch_splits_if_necessary(routepts[0], routepts[1], self.name)
			self.is_split_by_dir = True

		self.snapgraph = snapgraph.SnapGraph(routepts, forpaths=False)
		self.init_datazoom_to_dir_maps()
		if self.is_split_by_dir:
			len_dir_0 = geom.dist_m_polyline(self.routepts(0)); len_dir_1 = geom.dist_m_polyline(self.routepts(1))
			if abs(len_dir_0 - len_dir_1) > SPLIT_ROUTE_LEN_DIFF_TOLERANCE:
				raise Exception('route %s: lengths are too different.  dir 0 length: %0.4f.  dir 1 length: %0.4f.' % (self.name, len_dir_0, len_dir_1))

	def init_datazoom_to_dir_maps(self):
		# The key sets for both of these will be [None] + c.VALID_DATAZOOMS.  None is for the source routepts, unsimplified. 
		self.datazoom_to_dir_to_routepts = {}
		self.datazoom_to_dir_to_routeptaddr_to_mofr = {}

		self.datazoom_to_dir_to_routepts[None] = {}
		if self.is_split_by_dir:
			self.datazoom_to_dir_to_routepts[None][0] = self.snapgraph.plinename2pts['0']
			self.datazoom_to_dir_to_routepts[None][1] = self.snapgraph.plinename2pts['1']
		else:
			self.datazoom_to_dir_to_routepts[None][0] = self.datazoom_to_dir_to_routepts[None][1] = self.snapgraph.plinename2pts['0']
		self.datazoom_to_dir_to_routeptaddr_to_mofr[None] = self.calc_dir_to_routeptaddr_to_mofr(None)

		for datazoom in c.VALID_DATAZOOMS:
			dir_to_routepts = self.datazoom_to_dir_to_routepts[datazoom] = {}
			for direction in (0, 1):
				if direction == 1 and not self.is_split_by_dir:
					dir_to_routepts[1] = dir_to_routepts[0]
				else:
					dir_to_routepts[direction] = self.calc_simplified_routepts(direction, datazoom)
			self.datazoom_to_dir_to_routeptaddr_to_mofr[datazoom] = self.calc_dir_to_routeptaddr_to_mofr(datazoom)

	# Modifies nothing.  Returns list of points. 
	def calc_simplified_routepts(self, direction_, datazoom_):
		raw_routepts = self.routepts(direction_, None)
		epsilon = c.DATAZOOM_TO_RDP_EPSILON[datazoom_]
		return  geom.get_simplified_polyline_via_rdp_algo(raw_routepts, epsilon)

	# We could almost use snapgraph's function for doing this sort of thing, and have a snapgraph for each datazoom, but 
	# that wouldn't work because at each higher datazoom, the route becomes shorter. 
	def calc_dir_to_routeptaddr_to_mofr(self, datazoom_):
		dir_to_routeptaddr_to_mofr = [[], []]
		for direction in (0, 1):
			if direction == 1 and not self.is_split_by_dir:
				dir_to_routeptaddr_to_mofr[1] = dir_to_routeptaddr_to_mofr[0]
			else:
				routeptaddr_to_mofr = dir_to_routeptaddr_to_mofr[direction]
				routepts = self.routepts(direction, datazoom_)
				if datazoom_ is None: # got to be careful w.r.t. bootstrapping.  can't use latlon_to_mofr for this one b/c it uses this very structure. 
					for i in range(len(routepts)):
						if i==0:
							routeptaddr_to_mofr.append(0)
						else:
							prevpt = routepts[i-1]; curpt = routepts[i]
							routeptaddr_to_mofr.append(routeptaddr_to_mofr[i-1] + prevpt.dist_m(curpt))
				else:
					for routept in routepts:
						routeptaddr_to_mofr.append(self.latlon_to_mofr(routept, tolerance_=2))
				assert all(mofr1 <= mofr2 for mofr1, mofr2 in hopscotch(routeptaddr_to_mofr))
			assert len(routeptaddr_to_mofr) == len(routepts)
		return dir_to_routeptaddr_to_mofr

	def init_stops(self):
		self.init_stops_dir_to_stoptag_to_stop()
		self.init_stops_dir_to_mofr_to_stop()

	# Casting some things to str() because they come from the file in unicode, and when I'm debugging 
	# I don't want to see u'...' everywhere. 
	def init_stops_dir_to_stoptag_to_stop(self):
		self.dir_to_stoptag_to_stop = {}
		with open('stops_%s.json' % self.name, 'r') as fin:
			stops_file_content_json = json.load(fin)
		if self.is_subway():
			self.init_stops_dir_to_stoptag_to_stop_subway(stops_file_content_json)
		else:
			self.init_stops_dir_to_stoptag_to_stop_surface_route(stops_file_content_json)
		assert set(self.dir_to_stoptag_to_stop[0].keys()).isdisjoint(self.dir_to_stoptag_to_stop[1].keys())

	def init_stops_dir_to_stoptag_to_stop_surface_route(self, stops_file_content_json_):
		assert sorted(int(x) for x in stops_file_content_json_.keys()) == [0, 1] # The direction signifiers in the file, 0 and 1, 
				# will be strings because JSON doesn't allow ints as keys. 
		for direction_str in stops_file_content_json_.keys():
			direction_int = int(direction_str)
			self.dir_to_stoptag_to_stop[direction_int] = {}
			for stoptag, stopdetails in stops_file_content_json_[direction_str].iteritems():
				assert set(stopdetails.keys()) == set(['lat', 'lon', 'dirtags_serviced'])
				stoptag = str(stoptag)
				stopdetails['dirtags_serviced'] = [str(x) for x in stopdetails['dirtags_serviced']]
				latlng = geom.LatLng(stopdetails['lat'], stopdetails['lon']); dirtags_serviced = stopdetails['dirtags_serviced']
				new_stop = Stop(stoptag, latlng, direction_int, self.latlon_to_mofr(latlng), dirtags_serviced)
				if new_stop.mofr != -1 and not new_stop.is_sunday_only:
					self.dir_to_stoptag_to_stop[direction_int][stoptag] = new_stop

	def init_stops_dir_to_stoptag_to_stop_subway(self, stops_file_content_json_):
		for direction in (0, 1):
			self.dir_to_stoptag_to_stop[direction] = {}
			for stopname, raw_latlng in stops_file_content_json_.iteritems():
				stoptag = '%s %d' % (str(stopname), direction)
				latlng = geom.LatLng(raw_latlng[0], raw_latlng[1])
				new_stop = Stop(stoptag, latlng, direction, self.latlon_to_mofr(latlng, tolerance_=1), [])
				assert new_stop.mofr != -1
				self.dir_to_stoptag_to_stop[direction][stoptag] = new_stop

	def init_stops_dir_to_mofr_to_stop(self):
		self.dir_to_mofr_to_stop = {} # This is a redundant data structure for fast lookups.
		for direction in (0, 1):
			all_stops = self.dir_to_stoptag_to_stop[direction].values()
			mofr_to_stop = file_under_key(all_stops, lambda stop: stop.mofr, True)
			self.dir_to_mofr_to_stop[direction] = sorteddict(mofr_to_stop)

	def mofr_to_stop(self, dir_, mofr_):
		assert dir_ in (0, 1) and isinstance(mofr_, int)
		if not (0 <= mofr_ < self.max_mofr()):
			return None
		mofr_to_stop = self.dir_to_mofr_to_stop[dir_]
		bisect_idx = bisect.bisect_left(mofr_to_stop.sortedkeys(), mofr_)

		# So either the stop at bisect_idx or bisect_idx-1 is the closest stop that we're looking for:
		possible_stops = []
		def add_possible_stop_maybe(idx__):
			if 0 <= idx__ < len(mofr_to_stop.sortedkeys()):
				possible_stops.append(mofr_to_stop[mofr_to_stop.sortedkeys()[idx__]])
		add_possible_stop_maybe(bisect_idx)
		add_possible_stop_maybe(bisect_idx-1)
		return min(possible_stops, key=lambda stop: abs(stop.mofr - mofr_))

	def get_stop(self, stoptag_):
		for direction in (0, 1):
			if stoptag_ in self.dir_to_stoptag_to_stop[direction]:
				return self.dir_to_stoptag_to_stop[direction][stoptag_]
		return None

	def is_subway(self):
		return is_subway(self.name)

	def latlon_to_mofr(self, post_, tolerance_=0):
		return self.latlon_to_mofrndist(post_, tolerance_=tolerance_)[0]

	@lru_cache(5000)
	def latlon_to_mofrndist(self, post_, tolerance_=0):
		assert isinstance(post_, geom.LatLng) and (tolerance_ in (0, 1, 1.5, 2))
		# Please make sure that this continues to support something greater than the greatest possible rdp epsilon, 
		# and that the code that builds the routeptidx -> mofr map for each epsilon, and presumably calls this function, 
		# uses a tolerance argument to this function that is higher than the greatest epsilon. 
		# Otherwise a lot of things will be broken. 
		posaddr, dist = self.snapgraph.snap_with_dist(post_, {0:50, 1:300, 1.5:600, 2:2000}[tolerance_])
		if posaddr is None:
			return (-1, None)
		else:
			mofr = int(self.snapgraph.get_mapl(posaddr))
			return (mofr, dist)

	def snaptest(self, pt_, tolerance_=0):
		assert isinstance(pt_, geom.LatLng) and (tolerance_ in (0, 1, 2))
		posaddr = self.snapgraph.snap(pt_, {0:50, 1:300, 2:750}[tolerance_])
		snapped_pt = (self.snapgraph.get_latlng(posaddr) if posaddr is not None else None)
		mofr = self.latlon_to_mofr(pt_, tolerance_)
		resnapped_pts = [self.mofr_to_latlon(mofr, 0), self.mofr_to_latlon(mofr, 1)]
		return (snapped_pt, mofr, resnapped_pts)

	def max_mofr(self):
		return int(math.ceil(self.datazoom_to_dir_to_routeptaddr_to_mofr[None][0][-1]))

	def mofr_to_latlon(self, mofr_, dir_, datazoom_=None):
		r = self.mofr_to_latlonnheading(mofr_, dir_, datazoom_)
		return (r[0] if r != None else None)

	def mofr_to_heading(self, mofr_, dir_, datazoom_=None):
		r = self.mofr_to_latlonnheading(mofr_, dir_, datazoom_)
		return (r[1] if r != None else None)

	@lru_cache(5000)
	def mofr_to_latlonnheading(self, mofr_, dir_, datazoom_=None):
		assert dir_ in (0, 1)
		if mofr_ < 0:
			return None
		routeptaddr_to_mofr = self.datazoom_to_dir_to_routeptaddr_to_mofr[datazoom_][dir_]
		# Writing this code this way because we might need to handle a mofr_ that 
		# is a little greater than the max mofr of this route.  Hopefully not too 
		# much - maybe a couple of meters?  I'm not sure.
		for i in range(1, len(routeptaddr_to_mofr)):
			if routeptaddr_to_mofr[i] >= mofr_:
				break
		prevpt = self.routepts(dir_, datazoom_)[i-1]; curpt = self.routepts(dir_, datazoom_)[i]
		prevmofr = routeptaddr_to_mofr[i-1]; curmofr = routeptaddr_to_mofr[i]
		pt = curpt.subtract(prevpt).scale((mofr_-prevmofr)/float(curmofr-prevmofr)).add(prevpt)
		return (pt, prevpt.heading(curpt) if dir_==0 else curpt.heading(prevpt))

	# For datazoom of None only. 
	def mofr_to_lorouteptaddr(self, mofr_, dir_):
		assert dir_ in (0, 1)
		if mofr_ < 0:
			return -1
		for i, mofr in enumerate(self.datazoom_to_dir_to_routeptaddr_to_mofr[None][dir_]):
			if mofr > mofr_:
				return i-1
		return -1

	def stoptag_to_mofr(self, dir_, stoptag_):
		return self.dir_to_stoptag_to_stop[dir_][stoptag_].mofr

	def general_heading(self, dir_):
		assert dir_ in (0, 1)
		startpt, endpt = self.routepts(dir_)[0], self.routepts(dir_)[-1]
		if dir_:
			startpt, endpt = endpt, startpt
		return startpt.heading(endpt)

	def routepts(self, dir_, datazoom_=None):
		assert dir_ in (0, 1)
		return self.datazoom_to_dir_to_routepts[datazoom_][dir_]

	def dir_from_latlngs(self, latlng1_, latlng2_):
		mofr1 = self.latlon_to_mofr(latlng1_, tolerance_=2)
		mofr2 = self.latlon_to_mofr(latlng2_, tolerance_=2)
		if mofr1 != -1 and mofr2 != -1:
			return (0 if mofr2 > mofr1 else 1)
		else:
			latlngs_heading = latlng1_.heading(latlng2_)
			dir0_heading = self.general_heading(0)
			dir1_heading = self.general_heading(1)
			if geom.diff_headings(latlngs_heading, dir0_heading) < geom.diff_headings(latlngs_heading, dir1_heading):
				return 0
			else:
				return 1

	def dir_of_stoptag(self, stoptag_):
		for direction in (0, 1):
			if stoptag_ in self.dir_to_stoptag_to_stop[direction]:
				return direction
		raise Exception('Couldn\'t find dir of stoptag %s in route %s' % (stoptag_, self.name))

	def get_next_downstream_stop_with_predictions_recorded(self, stoptag_):
		direction = self.dir_of_stoptag(stoptag_)
		stop_mofrs = self.dir_to_mofr_to_stop[direction].sortedkeys()
		if direction == 1:
			stop_mofrs = stop_mofrs[::-1]
		begin_stoptag_mofr = self.dir_to_stoptag_to_stop[direction][stoptag_].mofr
		begin_stoptag_idx_in_stop_mofrs = stop_mofrs.index(begin_stoptag_mofr)
		for stop in [self.dir_to_mofr_to_stop[direction][mofr] for mofr in stop_mofrs[begin_stoptag_idx_in_stop_mofrs:]]:
			if self.are_predictions_recorded(stop.stoptag):
				return stop
		raise Exception('failed to find next downstream predictions-recorded stop for route %s stoptag %s' % (self.name, stoptag_))

	# 'recorded' currently means 'at an intersection or at the last stop on a route (in a certain direction)'.
	def are_predictions_recorded(self, stoptag_):
		assert self.get_stop(stoptag_) is not None
		try:
			get_recorded_froutenstoptags().index((self.name, stoptag_))
			return True
		except ValueError:
			return False

	def routeptmofrs(self, dir_, datazoom_):
		assert dir_ in (0, 1) and datazoom_ in c.VALID_DATAZOOMS 
		return self.datazoom_to_dir_to_routeptaddr_to_mofr[datazoom_][dir_][:]

def max_mofr(route_):
	return routeinfo(route_).max_mofr()

def routeinfo(routename_):
	return routeinfo_impl(massage_to_fudgeroute(routename_))

@lru_cache(1000)
@mc.decorate
@picklestore.decorate
def routeinfo_impl(froute_):
	return RouteInfo(froute_)
	
def massage_to_fudgeroute(route_):
	if route_ in FUDGEROUTES:
		return route_
	else:
		return configroute_to_fudgeroute(route_)

def get_all_routes_latlons():
	r = []
	for fudgeroute in FUDGEROUTES:
		r_l = []
		r.append(r_l)
		for routept in routeinfo(fudgeroute).routepts(0):
			r_l.append([routept.lat, routept.lng])
	return r

def latlon_to_mofr(route_, latlon_, tolerance_=0):
	return latlon_to_mofrndist(route_, latlon_, tolerance_=tolerance_)[0]

def latlon_to_mofrndist(route_, latlon_, tolerance_=0):
	assert isinstance(latlon_, geom.LatLng)
	if route_ not in CONFIGROUTES and route_ not in FUDGEROUTES:
		return (-1, 0.0)
	else:
		return routeinfo(route_).latlon_to_mofrndist(latlon_, tolerance_)

def mofr_to_latlon(route_, mofr_, dir_, datazoom_=None):
	return routeinfo(route_).mofr_to_latlon(mofr_, dir_, datazoom_)

def mofr_to_latlonnheading(route_, mofr_, dir_, datazoom_=None):
	return routeinfo(route_).mofr_to_latlonnheading(mofr_, dir_, datazoom_)

def fudgeroute_to_configroutes(fudgeroute_name_):
	if fudgeroute_name_ not in FUDGEROUTE_TO_CONFIGROUTES:
		raise Exception('fudgeroute %s is unknown' % (fudgeroute_name_))
	return FUDGEROUTE_TO_CONFIGROUTES[fudgeroute_name_]

def configroute_to_fudgeroute(configroute_):
	for fudgeroute, configroutes in FUDGEROUTE_TO_CONFIGROUTES.items():
		if configroute_ in configroutes:
			return fudgeroute
	raise Exception('configroute %s is unknown' % (configroute_))

def get_trip_endpoint_info(orig_, dest_, visible_fudgeroutendirs_):
	assert isinstance(orig_, geom.LatLng) and isinstance(dest_, geom.LatLng)
	assert len(set(x[0] for x in visible_fudgeroutendirs_)) == len(visible_fudgeroutendirs_) # no duplicates 
	orig_route_to_mofr = get_route_to_mofr(orig_)
	dest_route_to_mofr = get_route_to_mofr(dest_)
	common_routes = set(orig_route_to_mofr.keys()).intersection(set(dest_route_to_mofr))
	common_routes = common_routes.intersection(set([x[0] for x in visible_fudgeroutendirs_]))
	if not common_routes:
		return None
	else:
		for route in common_routes:
			direction = (0 if orig_route_to_mofr[route] < dest_route_to_mofr[route] else 1)
			routes_dir_in_visible_list = [x for x in visible_fudgeroutendirs_ if x[0] == route][0][1]
			if direction == routes_dir_in_visible_list:
				ri = routeinfo(route)
				orig_stop = ri.mofr_to_stop(direction, orig_route_to_mofr[route])
				dest_stop = ri.mofr_to_stop(direction, dest_route_to_mofr[route])
				orig_latlng = ri.mofr_to_latlon(orig_stop.mofr, direction)
				dest_latlng = ri.mofr_to_latlon(dest_stop.mofr, direction)
				return {'route': route, 'direction': direction, 
						'origstoptag': orig_stop.stoptag, 'origlatlng': orig_latlng, 'origmofr': orig_stop.mofr, 
						'deststoptag': dest_stop.stoptag, 'destlatlng': dest_latlng, 'destmofr': dest_stop.mofr}
		return None

def get_route_to_mofr(latlon_):
	r = {}
	for route in FUDGEROUTES:
		mofr = latlon_to_mofr(route, latlon_, tolerance_=1)
		if mofr != -1:
			r[route] = mofr
	return r

def get_configroute_to_fudgeroute_map():
	return CONFIGROUTE_TO_FUDGEROUTE

def get_heading_from_compassdir(compassdir_):
	assert compassdir_ in ('n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw')
	r = {'n':0, 'e':90, 's':180, 'w':270, 'ne':45, 'se':135, 'sw':225, 'nw':315}[compassdir_]
	CONSIDER_NORTH_TO_BE_THIS_HEADING = 343 # Toronto's street grid is tilted this much from north. 
	r += CONSIDER_NORTH_TO_BE_THIS_HEADING
	r = geom.normalize_heading(r)
	return r

class FactoredSampleScorer(object):
	
	def __init__(self, factor_definitions_min_max_inverse_list_):
		self.min_max_inverse = factor_definitions_min_max_inverse_list_[:]

	def get_score(self, sample_):
		assert (len(sample_) == self.num_factors)
		r = 1.0
		for factoridx, factorval in enumerate(sample_):
			min, max, inverse = self.min_max_inverse[factoridx]
			if inverse:
				r *= (max - factorval)/float(max - min)
			else:
				r *= (factorval - min)/float(max - min)
		return r

	@property 
	def num_factors(self):
		return len(self.min_max_inverse)

def get_fudgeroutes_for_map_bounds(southwest_, northeast_, compassdir_or_heading_, maxroutes_):
	assert isinstance(southwest_, geom.LatLng) and isinstance(northeast_, geom.LatLng) and isinstance(maxroutes_, int)
	assert isinstance(compassdir_or_heading_, str) or isinstance(compassdir_or_heading_, int)
	heading = (get_heading_from_compassdir(compassdir_or_heading_) if isinstance(compassdir_or_heading_, str) else compassdir_or_heading_)
	bounds_midpt = southwest_.avg(northeast_)
	scorer = FactoredSampleScorer([[0, southwest_.dist_m(northeast_), False], [0, 90, True], [0, bounds_midpt.dist_m(northeast_), True]])
	fudgeroute_n_dir_to_score = {}
	for fudgeroute in NON_SUBWAY_FUDGEROUTES:
		for dir in (0, 1):
			fudgeroute_n_dir_to_score[(fudgeroute, dir)] = 0.0
			for routelineseg_pt1, routelineseg_pt2 in hopscotch(routeinfo(fudgeroute).routepts(dir)):
				if dir == 1:
					routelineseg_pt1, routelineseg_pt2 = routelineseg_pt2, routelineseg_pt1
				if geom.does_line_segment_overlap_box(routelineseg_pt1, routelineseg_pt2, southwest_, northeast_):
					routelineseg_pt1, routelineseg_pt2 = geom.constrain_line_segment_to_box(
							routelineseg_pt1, routelineseg_pt2, southwest_, northeast_)
					routelineseg_heading = routelineseg_pt1.heading(routelineseg_pt2)
					routelineseg_midpt = routelineseg_pt1.avg(routelineseg_pt2)
					headings_diff = geom.diff_headings(routelineseg_heading, heading)
					if headings_diff < 80:
						routelineseg_len_m = routelineseg_pt1.dist_m(routelineseg_pt2)
						routelineseg_midpt_dist_from_bounds_centre = bounds_midpt.dist_m(routelineseg_midpt)
						scoresample = (routelineseg_len_m, headings_diff, routelineseg_midpt_dist_from_bounds_centre)
						fudgeroute_n_dir_to_score[(fudgeroute, dir)] += scorer.get_score(scoresample)
						if 0: 
							printerr('fudgeroute_n_dir_to_score(%20s) - line at ( %.5f, %.5f ) - %4.0f, %2d, %4.0f ==> %.3f' % ((fudgeroute, dir), \
									#routelineseg_midpt.lat, routelineseg_midpt.lng,  \
									routelineseg_pt1.lat, routelineseg_pt2.lng, \
									scoresample[0], scoresample[1], scoresample[2], scorer.get_score(scoresample)))
			#printerr('score for '+fudgeroute+' dir '+str(dir)+' = '+str(fudgeroute_n_dir_to_score[(fudgeroute, dir)]))
	
	# If a single fudgeroute is represented in both 0 and 1 directions, then here remove the lower-scored direction.  
	# Because I don't know how to show both directions of a route on a map at the same time. 
	if 0:
		printerr([x for x in sorted(fudgeroute_n_dir_to_score.items(), key=lambda x: x[1], reverse=True)])
	#printerr([x for x in sorted(fudgeroute_n_dir_to_score.items(), key=lambda x: x[1], reverse=True)])
	top_fudgeroute_n_dirs = [x[0] for x in sorted(fudgeroute_n_dir_to_score.items(), key=lambda x: x[1], reverse=True) if x[1] > 0.15]
	for i in range(len(top_fudgeroute_n_dirs)-1, -1, -1):
		fudgeroute, dir = top_fudgeroute_n_dirs[i]
		opposite_dir = int(not dir)
		if (fudgeroute, opposite_dir) in top_fudgeroute_n_dirs[:i]:
			top_fudgeroute_n_dirs.pop(i)

	top_fudgeroute_n_dirs = top_fudgeroute_n_dirs[:maxroutes_]

	return top_fudgeroute_n_dirs

# For each non-subway route, gives us an english description of which way dir 0 points (eg. East or North) 
# and which way dir 1 points (West or South). 
# For all routes that I've looked at, our dir 0 (which corresponds to NextBus's _0_ in a dirtag) is east for a
# route that goes east-west, and south for one that goes north-south.  (1 for the other direction, of course.)
# But I know of no guarantee for this.
@mc.decorate
def get_fudgeroute_to_intdir_to_englishdesc_json_str():
	return util.to_json_str(get_fudgeroute_to_intdir_to_englishdesc())

@mc.decorate
def get_fudgeroute_to_intdir_to_englishdesc():
	r = {}
	for fudgeroute in NON_SUBWAY_FUDGEROUTES:
		r[fudgeroute] = {}
		for intdir in (0, 1):
			routepts = routeinfo(fudgeroute).routepts(intdir)
			if intdir == 0:
				heading = routepts[0].heading(routepts[-1])
			else:
				heading = routepts[-1].heading(routepts[0])
			r[fudgeroute][intdir] = heading_to_englishdesc(heading)
	return r

def heading_to_englishdesc(heading_):
	assert isinstance(heading_, int) and (0 <= heading_  < 360)
	if heading_ <= 45 or heading_ >= 315:
		return 'North'
	elif heading_ <= 135:
		return 'East'
	elif heading_ <= 225:
		return 'South'
	else:
		return 'West'

@lru_cache(1)
def get_froute_to_english():
	# These need to fit in a dialog so we make them short.  
	r = {'yonge_university_spadina': 'Yonge/Uni Subway', 'bloor_danforth': 'Bloor Subway'}
	# Hoping that the other ones aren't too long. 
	for froute in NON_SUBWAY_FUDGEROUTES:
		if froute == 'stclair':
			english = 'St. Clair'
		elif froute == 'woodbinesouth':
			english = 'Woodbine South'
		else:
			english = froute[0].upper() + froute[1:]
		r[froute] = english
	assert len(r) == len(FUDGEROUTES)
	return r

def snaptest(fudgeroutename_, pt_, tolerance_=0):
	return routeinfo(fudgeroutename_).snaptest(pt_, tolerance_)

class Intersection:

	def __init__(self, froute1_, froute1mofr_, froute2_, froute2mofr_, 
			froute1_dir0_stoptag_, froute1_dir1_stoptag_, froute2_dir0_stoptag_, froute2_dir1_stoptag_, 
			latlng_):
		assert isinstance(latlng_, geom.LatLng)
		self.froute1 = froute1_
		self.froute1mofr = froute1mofr_
		self.froute2 = froute2_
		self.froute2mofr = froute2mofr_
		self.froute1_dir0_stoptag = froute1_dir0_stoptag_
		self.froute1_dir1_stoptag = froute1_dir1_stoptag_
		self.froute2_dir0_stoptag = froute2_dir0_stoptag_
		self.froute2_dir1_stoptag = froute2_dir1_stoptag_
		self.latlng = latlng_

	def __str__(self):
		return 'Intersection(%s, %d, %s, %d, %s)' % (self.froute1, self.froute1mofr, self.froute2, self.froute2mofr, str(self.latlng))

	def __repr__(self):
		return self.__str__()

class HalfIntersection:

	def __init__(self, froute_, mofr_, dir0_stoptag_, dir1_stoptag_, latlng_):
		self.froute = froute_
		self.mofr = mofr_
		self.dir0_stoptag = dir0_stoptag_
		self.dir1_stoptag = dir1_stoptag_
		self.latlng = latlng_

	def __str__(self):
		return 'HalfIntersection(%s, %d, %s, %s, %s)' % (self.froute, self.mofr, self.dir0_stoptag, self.dir1_stoptag, str(self.latlng))

	def __repr__(self):
		return self.__str__()


@lru_cache(1)
@mc.decorate
def get_intersections():
	r = []
	for routei, route1 in enumerate(FUDGEROUTES[:]):
		for route2 in FUDGEROUTES[:][routei+1:]:
			ri1 = routeinfo(route1); ri2 = routeinfo(route2)
			new_intersections = []
			for route1_pt1, route1_pt2 in hopscotch(ri1.routepts(0)):
				for route2_pt1, route2_pt2 in hopscotch(ri2.routepts(0)):
					intersect_latlng = geom.get_line_segment_intersection(route1_pt1, route1_pt2, route2_pt1, route2_pt2)
					if intersect_latlng is not None:
						route1mofr = ri1.latlon_to_mofr(intersect_latlng); route2mofr = ri2.latlon_to_mofr(intersect_latlng)
						route1_dir0_stoptag = ri1.mofr_to_stop(0, route1mofr).stoptag
						route1_dir1_stoptag = ri1.mofr_to_stop(1, route1mofr).stoptag
						route2_dir0_stoptag = ri2.mofr_to_stop(0, route2mofr).stoptag
						route2_dir1_stoptag = ri2.mofr_to_stop(1, route2mofr).stoptag
						new_intersection = Intersection(route1, route1mofr, route2, route2mofr, 
								route1_dir0_stoptag, route1_dir1_stoptag, route2_dir0_stoptag, route2_dir1_stoptag, 
								intersect_latlng)
						if not new_intersections:
							new_intersections.append(new_intersection)
						else:
							nearest_old_intersection = min(new_intersections, key=lambda x: x.latlng.dist_m(new_intersection.latlng))
							dist_to_nearest_old_intersection = nearest_old_intersection.latlng.dist_m(new_intersection.latlng)
							if dist_to_nearest_old_intersection > 2000:
								new_intersections.append(new_intersection)
			r += new_intersections
	return r

# Recorded stops are intersections plus the last stop on each route, in each direction. 
@lru_cache(1)
@mc.decorate
def get_recorded_froutenstoptags():
	r = []
	for i in get_intersections():
		if not is_subway(i.froute1):
			r.append((i.froute1, i.froute1_dir0_stoptag))
			r.append((i.froute1, i.froute1_dir1_stoptag))
		if not is_subway(i.froute2):
			r.append((i.froute2, i.froute2_dir0_stoptag))
			r.append((i.froute2, i.froute2_dir1_stoptag))
	for ri in [routeinfo(froute) for froute in NON_SUBWAY_FUDGEROUTES]:
		dir0_last_stop = ri.dir_to_mofr_to_stop[0][ri.dir_to_mofr_to_stop[0].sortedkeys()[-1]]
		dir1_last_stop = ri.dir_to_mofr_to_stop[1][ri.dir_to_mofr_to_stop[1].sortedkeys()[0]]
		r.append((ri.name, dir0_last_stop.stoptag))
		r.append((ri.name, dir1_last_stop.stoptag))
	return r

def get_mofrndirnstoptag_to_halfintersection(froute_, mofr_):
	r = {}
	for i in get_intersections():
		if i.froute1 == froute_:
			direction = mofrs_to_dir(mofr_, i.froute1mofr)
			stoptag = (i.froute1_dir0_stoptag if direction == 0 else i.froute1_dir1_stoptag)
			r[(i.froute1mofr,direction,stoptag)] = HalfIntersection(i.froute2, i.froute2mofr, i.froute2_dir0_stoptag, i.froute2_dir1_stoptag, i.latlng)
		elif i.froute2 == froute_:
			direction = mofrs_to_dir(mofr_, i.froute2mofr)
			stoptag = (i.froute2_dir0_stoptag if direction == 0 else i.froute2_dir1_stoptag)
			r[(i.froute2mofr,direction,stoptag)] = HalfIntersection(i.froute1, i.froute1mofr, i.froute1_dir0_stoptag, i.froute1_dir1_stoptag, i.latlng)
	return r

# This converts a string from a NextBus schedule (eg. 'East') to a direction int that we use (eg. 0).
# For all routes that I've looked at, our dir 0 (which corresponds to NextBus's _0_ in a dirtag) is east for a
# route that goes east-west, and south for one that goes north-south.  (1 for the other direction, of course.)
# But I know of no guarantee for this.
def compassdir_string_to_dir_int(froute_, compassdir_str_):
	compassdir_str = compassdir_str_.lower()
	assert compassdir_str in ('north', 'south', 'east', 'west')
	heading_indicated_by_compassdir_str = {'north':0, 'south':180, 'east':90, 'west':270}[compassdir_str]
	ri = routeinfo(froute_)
	dir0_heading = ri.routepts(0)[0].heading(ri.routepts(0)[-1])
	dir1_heading = ri.routepts(1)[-1].heading(ri.routepts(1)[0])
	if geom.diff_headings(heading_indicated_by_compassdir_str, dir0_heading) < 90:
		return 0
	elif geom.diff_headings(heading_indicated_by_compassdir_str, dir1_heading) < 90:
		return 1
	else:
		raise Exception('Could not determine direction int for froute %s, schedule direction "%s"' % (froute_, compassdir_str_))

def get_stops_dir_to_stoptag_to_latlng(froute_):
	ri = routeinfo(froute_)
	r = {}
	for direction in (0, 1):
		r[direction] = {}
		for stoptag, stop in ri.dir_to_stoptag_to_stop[direction].iteritems():
			r[direction][stoptag] = (stop.latlng.lat, stop.latlng.lng)
	return r

def routepts(froute_, dir_, datazoom_):
	return routeinfo(froute_).routepts(dir_, datazoom_)

@lru_cache(1)
@mc.decorate
def get_froute_to_routepts_min_datazoom_json_str():
	return util.to_json_str(get_froute_to_routepts_min_datazoom())

def get_froute_to_routepts_min_datazoom():
	r = {}
	for froute in FUDGEROUTES:
		ri = routeinfo(froute)
		r[froute] = []
		r[froute].append(routeinfo(froute).routepts(0, c.MIN_DATAZOOM))
		if ri.is_split_by_dir:
			r[froute].append(routeinfo(froute).routepts(1, c.MIN_DATAZOOM))
	return r
	
def dir_from_latlngs(froute_, latlng1_, latlng2_):
	return routeinfo(froute_).dir_from_latlngs(latlng1_, latlng2_)

@lru_cache(1)
@mc.decorate
def get_subway_froute_to_datazoom_to_routepts():
	r = {}
	for froute in SUBWAY_FUDGEROUTES:
		r[froute] = {}
		for datazoom in c.VALID_DATAZOOMS:
			ri = routeinfo(froute)
			assert not ri.is_split_by_dir
			r[froute][datazoom] = ri.routepts(0, datazoom)
	return util.to_json_str(r)

# Don't call this function from this module as a main.  It will write some unusable pickle files. 
# They will refer to the RouteInfo class as '__main__.RouteInfo' and then when unpickled, when this module 
# is likely imported from another file as "import routes" (because that's how most of the code is written right now) 
# and knows about RouteInfo as "routes.RouteInfo", 
# the unpickling will still try to resolve __main__.RouteInfo and will fail with a message like this: 
# "AttributeError: 'module' object has no attribute 'RouteInfo'". 
# You can see the difference in the generated pickle files yourself (if you call this function from this module as a main 
# vs. from another module when imported as "import routes" and examine the pickled output.  You might try text mode 
# i.e. protocol=0 to pickle.dump()).
def prime_routeinfos(log=False):
	for froute in sorted(FUDGEROUTES):
		if log:
			print 'Priming route %s...' % froute
		routeinfo(froute)

# Will modify arguments. 
def stretch_splits_if_necessary(dir0pts_, dir1pts_, log_froute_):
	dir0_stretch_idxes = get_maximal_sublists3(dir0pts_, lambda pt: pt in dir1pts_, returnidxes=True)
	dir1_stretch_idxes = get_maximal_sublists3(dir1pts_, lambda pt: pt in dir0pts_, returnidxes=True)
	if len(dir0_stretch_idxes) != len(dir1_stretch_idxes):
		raise Exception('faulty logic?')
	stretch_is_a_split = dir0pts_[dir0_stretch_idxes[0][0]] not in dir1pts_
	for dir0stretch_idxes, dir1stretch_idxes in zip(dir0_stretch_idxes, dir1_stretch_idxes)[::-1]:
		if stretch_is_a_split:
			dir0stretch = [dir0pts_[i] for i in [dir0stretch_idxes[0]-1] + dir0stretch_idxes + [dir0stretch_idxes[-1]+1]]
			dir1stretch = [dir1pts_[i] for i in [dir1stretch_idxes[0]-1] + dir1stretch_idxes + [dir1stretch_idxes[-1]+1]]
			dir0stretch_len = geom.dist_m_polyline(dir0stretch)
			dir1stretch_len = geom.dist_m_polyline(dir1stretch)
			if not (0.5 < dir0stretch_len/dir1stretch_len < 2.0):
				raise Exception('won\'t stretch - lengths are too different - %f and %f' % (dir0stretch_len, dir1stretch_len))
			if abs(dir0stretch_len - dir1stretch_len) < SPLIT_ROUTE_LEN_DIFF_TOLERANCE/100:
				pass
			elif dir0stretch_len < dir1stretch_len:
				stretched_pline = get_pline_stretched_with_triangle_waves(dir0stretch, dir1stretch_len)
				dir0pts_[dir0stretch_idxes[0]-1:dir0stretch_idxes[-1]+2] = stretched_pline
			else:
				stretched_pline = get_pline_stretched_with_triangle_waves(dir1stretch, dir0stretch_len)
				dir1pts_[dir1stretch_idxes[0]-1:dir1stretch_idxes[-1]+2] = stretched_pline

		stretch_is_a_split = not stretch_is_a_split

LOG_SPLIT_STRETCHING = False

def get_pline_stretched_with_triangle_waves(pline_, goal_len_):
	if LOG_SPLIT_STRETCHING:
		len1 = geom.dist_m_polyline(pline_); len2 = goal_len_
		printerr('stretching %.2f to %.2f (factor of %.2f)' % (len1, len2, len2/len1))

	initial_wave_height = c.DATAZOOM_TO_RDP_EPSILON[c.MAX_DATAZOOM]*0.75

	def get_wave_pline_len_by_wave_period(wave_period__):
		wave_pline = get_triangle_wave_pline(pline_, wave_period__, initial_wave_height)
		r = geom.dist_m_polyline(wave_pline)
		if LOG_SPLIT_STRETCHING:
			printerr('period (binary) %.2f = %.2f' % (wave_period__, r))
		return r

	epsilon_x = 0.001
	epsilon_y = SPLIT_ROUTE_LEN_DIFF_TOLERANCE/100
	period, found_period_is_exact = binary_search(get_wave_pline_len_by_wave_period, 0.1, 999999, 
			goal_len_, epsilon_x, epsilon_y)
	if not found_period_is_exact:
		while get_wave_pline_len_by_wave_period(period) < goal_len_:
			if LOG_SPLIT_STRETCHING:
				printerr('period (linear) %.2f...' % period)
			period -= epsilon_x
		def get_wave_pline_len_by_wave_height(wave_height__):
			wave_pline = get_triangle_wave_pline(pline_, period, wave_height__)
			r = geom.dist_m_polyline(wave_pline)
			if LOG_SPLIT_STRETCHING:
				printerr('height (binary) %.6f = %.2f' % (wave_height__, r))
			return r
		height, found_height_is_exact = binary_search(get_wave_pline_len_by_wave_height, 0.0, initial_wave_height, 
				goal_len_, epsilon_x/1000, epsilon_y)
		r = get_triangle_wave_pline(pline_, period, height)
	else:
		r = get_triangle_wave_pline(pline_, period, initial_wave_height)
	if LOG_SPLIT_STRETCHING:
		printerr('stretching done.  original: %d pts, stretched: %d pts.' % (len(pline_), len(r)))
		printerr('original:')
		printerr(pline_)
		printerr('stretched:')
		printerr(r)
	return r

def get_split_lineseg(pt1_, pt2_, min_piece_len_):
	assert isinstance(pt1_, geom.LatLng) and isinstance(pt2_, geom.LatLng)
	lineseg_len = pt1_.dist_m(pt2_)
	num_pieces = int(math.floor(lineseg_len/min_piece_len_))
	if num_pieces <= 1:
		return [pt1_, pt2_]
	else:
		r = [pt1_]
		for step in xrange(1, num_pieces):
			ratio = float(step)/num_pieces
			r.append(geom.LatLng(avg(pt1_.lat, pt2_.lat, ratio), avg(pt1_.lng, pt2_.lng, ratio)))
		r.append(pt2_)
		return r

def get_triangle_wave_lineseg(pt1_, pt2_, wave_period_meters_, wave_height_meters_):
	assert isinstance(pt1_, geom.LatLng) and isinstance(pt2_, geom.LatLng)

	split_orig_lineseg = get_split_lineseg(pt1_, pt2_, wave_period_meters_/2.0)
	perpendicular_heading = geom.normalize_heading(pt1_.heading(pt2_) + 90)
	r = []
	for i, pt, isfirst, islast in enumerate2(split_orig_lineseg):
		if (i % 2 == 0) or (len(split_orig_lineseg) % 2 == 0 and islast):
			r.append(pt)
		else:
			r.append(pt.offset(perpendicular_heading, wave_height_meters_))
	return r
			
def get_triangle_wave_pline(pline_, wave_period_meters_, wave_height_meters_):
	r = []
	for i, (pt1, pt2), isfirst, islast in enumerate2(hopscotch(pline_)):
		r += get_triangle_wave_lineseg(pt1, pt2, wave_period_meters_, wave_height_meters_)
		if not islast:
			del r[-1]
	return r

def binary_search(f, init_x1, init_x2, goal_y, epsilon_x, epsilon_y):
	init_y1 = f(init_x1)
	init_y2 = f(init_x2)
	if init_y1 <= goal_y <= init_y2:
		lo_x = init_x1
		hi_x = init_x2
	elif init_y1 >= goal_y >= init_y2:
		lo_x = init_x2
		hi_x = init_x1
	while True:
		cur_x = (lo_x + hi_x)/2.0
		cur_y = f(cur_x)
		if abs(cur_y - goal_y) < epsilon_y:
			return (cur_x, True)
		elif abs(cur_x - lo_x) < epsilon_x:
			return (cur_x, False)
		#elif last_y is not None and abs(last_y - cur_y) < epsilon_y:
		#	return (cur_x, False)
		elif cur_y > goal_y:
			hi_x = cur_x
		else:
			assert cur_y < goal_y
			lo_x = cur_x

if __name__ == '__main__':

	pass


