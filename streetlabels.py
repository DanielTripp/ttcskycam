#!/usr/bin/python2.6

import sys, json, os.path, bisect, xml.dom, xml.dom.minidom
import geom, mc, c, routes 
from misc import *


g_froute_to_startmofr_to_text = None


# SVG uses rotation in degrees, clockwise from +ve X axis (AKA heading 90).
def heading_to_svg_rotation(heading_):
	assert 0 <= heading_ < 360
	heading = heading_
	while heading >= 180:
		heading -= 180
	return get_range_val((0, -90), (180, 90), heading) 

def is_route_straight_enough_here(ri_, start_mofr_, end_mofr_):
	start_heading = ri_.mofr_to_heading(start_mofr_, 0)
	step = max(1, (end_mofr_-start_mofr_)/10)
	for mofr in range(start_mofr_, end_mofr_, step)[1:]:
		sample_heading = ri_.mofr_to_heading(mofr, 0)
		if geom.diff_headings(start_heading, sample_heading) > 20:
			return False
	return True

# startmofr_to_text is a sorteddict. 
@mc.decorate
def get_froute_to_startmofr_to_text():
	global g_froute_to_startmofr_to_text
	if g_froute_to_startmofr_to_text is None:
		with open('streetlabels.yaml') as fin:
			import yaml # yaml looks like a slow import.  0.06 seconds. 
			raw_map = yaml.load(fin)
			g_froute_to_startmofr_to_text = {}
			for froute, startmofr_to_text in raw_map.iteritems():
				g_froute_to_startmofr_to_text[froute] = sorteddict(startmofr_to_text)
			assert set(g_froute_to_startmofr_to_text.keys()) == set(routes.NON_SUBWAY_FUDGEROUTES)
			for froute, startmofr_to_text in g_froute_to_startmofr_to_text.iteritems():
				assert 0 in startmofr_to_text
	return g_froute_to_startmofr_to_text

def get_text(froute_, mofr_):
	return get_froute_to_startmofr_to_text()[froute_].flooritem(mofr_)[1]

def get_labels(froute_, zoom_, box_sw_, box_ne_):
	assert isinstance(zoom_, int) and isinstance(box_sw_, geom.LatLng) and isinstance(box_ne_, geom.LatLng)
	assert box_sw_.lat < box_ne_.lat and box_sw_.lng < box_ne_.lng
	def is_within_box(label__):
		start_latlng = label__['latlng']; end_latlng = label__['end_latlng']
		return start_latlng.is_within_box(box_sw_, box_ne_) or end_latlng.is_within_box(box_sw_, box_ne_)
	return [label for label in get_labels_for_zoom(froute_, zoom_) if is_within_box(label)]

@mc.decorate
def get_labels_for_zoom(froute_, zoom_):
	assert isinstance(zoom_, int)

	if not (13 <= zoom_ <= 21):
		return []
	ri = routes.routeinfo(froute_)
	MOFRSTEP_AT_ZOOM_21 = 12
	TEXT_LEN_METRES_AT_ZOOM_21 = 4
	mofrstep = MOFRSTEP_AT_ZOOM_21
	text_length_metres = TEXT_LEN_METRES_AT_ZOOM_21
	for i in range(21-zoom_):
		mofrstep *= 2
		text_length_metres *= 2
	r = []
	start_mofr = 0
	while start_mofr < ri.max_mofr() - text_length_metres:
		end_mofr = start_mofr + text_length_metres
		text = get_text(froute_, start_mofr)
		if (text != get_text(froute_, end_mofr)) or (not is_route_straight_enough_here(ri, start_mofr, end_mofr)):
			start_mofr += max(1, mofrstep/10)
		else:
			start_latlng = ri.mofr_to_latlon(start_mofr, 0)
			end_latlng = ri.mofr_to_latlon(end_mofr, 0)
			heading = start_latlng.heading(end_latlng)
			svg_rotation = heading_to_svg_rotation(heading)
			if 180 <= heading < 360:
				start_latlng = end_latlng
			r.append({'text': text, 'latlng': start_latlng, 'end_latlng': end_latlng, 'rotation': svg_rotation})
			start_mofr += mofrstep
	return r


if __name__ == '__main__':

	if 0:
		print get_froute_to_startmofr_to_text()
	else:
		import paths 
		for label in get_labels('carlton', 14, paths.get_city_sw(), paths.get_city_ne()):
			print '%s    %s    %s' % (label['latlng'], label['rotation'], label['text'])



