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

import sys, xml.dom, xml.dom.minidom, json
from collections import defaultdict

def child_elems(node_, elemname_=None):
	return [node for node in node_.childNodes if isinstance(node, xml.dom.minidom.Element) and (node.nodeName==elemname_ if elemname_ else True)]

def get_stoptag_to_latlon(dom_):
	r = {}
	for elem in child_elems(child_elems(dom_.documentElement)[0], 'stop'):
		stoptag = elem.getAttribute('tag')
		lat = float(elem.getAttribute('lat'))
		lon = float(elem.getAttribute('lon'))
		r[stoptag] = (lat, lon)
	return r

def get_stoptags_for_direction(dom_, direction_):
	assert direction_ in (0, 1) or isinstance(direction_, basestring)
	r = set()
	for direction_elem in child_elems(child_elems(dom_.documentElement)[0], 'direction'):
		cur_direction_tag = direction_elem.getAttribute('tag')
		if direction in (0, 1):
			match = (cur_direction_tag.find('_%d_' % (direction_)) != -1)
		else:
			match = (cur_direction_tag == direction_)
		if match:
			for stop_elem in child_elems(direction_elem, 'stop'):
				r.add(stop_elem.getAttribute('tag'))
	return r

def get_stoptag_to_dirtags_serviced(dom_):
	r = defaultdict(lambda: [])
	for dir_elem in dom_.documentElement.getElementsByTagName('direction'):
		dirtag = dir_elem.getAttribute('tag')
		for stop_elem in (x for x in dir_elem.childNodes if x.nodeName == 'stop'):
			r[stop_elem.getAttribute('tag')].append(dirtag)
	return r

def get_stoptag_to_stop_details(dom_, direction_):
	r = {}
	stoptag_to_latlon = get_stoptag_to_latlon(dom_)
	stoptag_to_dirtags_serviced = get_stoptag_to_dirtags_serviced(dom_)
	for stoptag in get_stoptags_for_direction(dom_, direction_):
		latlon = stoptag_to_latlon[stoptag]
		dirtags_serviced = stoptag_to_dirtags_serviced[stoptag]
		if len(dirtags_serviced) > 0:
			r[stoptag] = {'lat': latlon[0], 'lon': latlon[1], 'dirtags_serviced': dirtags_serviced}
	return r

if len(sys.argv) < 2:
	sys.exit('Need at least one argument: one or more filenames containing routeConfig output from NextBus.')
routeconfig_filenames = sys.argv[1:]
r = defaultdict(lambda: {})
for routeconfig_filename in routeconfig_filenames:
	dom = xml.dom.minidom.parse(routeconfig_filename)
	for direction in (0, 1):
		for stoptag, stop_details in get_stoptag_to_stop_details(dom, direction).iteritems():
			if stoptag in r[direction]:
				r[direction][stoptag]['dirtags_serviced'] += stop_details['dirtags_serviced']
			else:
				r[direction][stoptag] = stop_details

json.dump(r, sys.stdout, indent=1)
print


