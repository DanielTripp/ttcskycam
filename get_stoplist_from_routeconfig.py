#!/usr/bin/env python

import sys, xml.dom, xml.dom.minidom, json

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

def get_stoptag_and_latlon_list(dom_, direction_):
	r = []
	stoptag_to_latlon = get_stoptag_to_latlon(dom_)
	for stoptag in get_stoptags_for_direction(dom_, direction_):
		latlon = stoptag_to_latlon[stoptag]
		r.append({'stoptag': stoptag, 'lat': latlon[0], 'lon': latlon[1]})
	r.sort(key=lambda x: x['stoptag'])
	return r

if len(sys.argv) < 3:
	sys.exit('Need two arguments: 1) a filename containing routeConfig output from NextBus, and 2) a direction (eg. "0" or "1").')
routeconfig_filename = sys.argv[1]
direction = sys.argv[2]
if direction in ('0', '1'):
	direction = int(direction)
dom = xml.dom.minidom.parse(routeconfig_filename)
json.dump(get_stoptag_and_latlon_list(dom, direction), sys.stdout, indent=0)
print

