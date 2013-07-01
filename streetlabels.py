#!/usr/bin/python2.6

import sys, json, os.path, bisect, xml.dom, xml.dom.minidom, yaml
import geom, mc, c, routes 
from misc import *

# We don't do streetlabels for all zoom levels.  (These are google maps zoom levels by the way.) 
# For low zoom (i.e. zoomed out), we draw our traffic coloured lines thin enough that google maps' 
# own street labels are still visible.   Mostly visible.  Visible enough.
ZOOMS_WITH_STREETLABELS = range(13, 21+1)

g_froute_to_dir_to_startmofr_to_text = None


# SVG uses rotation in degrees, clockwise from +ve X axis (AKA heading 90).
def heading_to_svg_rotation(heading_):
	assert 0 <= heading_ < 360
	heading = heading_
	while heading >= 180:
		heading -= 180
	return get_range_val((0, -90), (180, 90), heading) 

def is_route_straight_enough_here(ri_, dir_, start_mofr_, end_mofr_):
	start_heading = ri_.mofr_to_heading(start_mofr_, dir_)
	step = max(1, (end_mofr_-start_mofr_)/10)
	for mofr in range(start_mofr_, end_mofr_, step)[1:]:
		sample_heading = ri_.mofr_to_heading(mofr, dir_)
		if geom.diff_headings(start_heading, sample_heading) > 20:
			return False
	return True

# The startmofr_to_text parts are sorteddicts. 
@mc.decorate
def get_froute_to_dir_to_startmofr_to_text():
	global g_froute_to_dir_to_startmofr_to_text
	if g_froute_to_dir_to_startmofr_to_text is None:
		with open('streetlabels.yaml') as fin:
			raw_map = yaml.load(fin)
			g_froute_to_dir_to_startmofr_to_text = {}
			for froute, frouteval in raw_map.iteritems():
				# frouteval could be a 'start mofr -> text' dict or a 'dir -> start mofr -> text' dict, 
				# depending on whether froute has different labels for each direction. 
				labels_are_split_by_dir = set(frouteval.keys()) == set((0, 1))
				g_froute_to_dir_to_startmofr_to_text[froute] = {}
				if labels_are_split_by_dir:
					for direction in (0, 1):
						g_froute_to_dir_to_startmofr_to_text[froute][direction] = sorteddict(frouteval[direction])
				else:
					g_froute_to_dir_to_startmofr_to_text[froute][0] = sorteddict(frouteval)
					g_froute_to_dir_to_startmofr_to_text[froute][1] =  g_froute_to_dir_to_startmofr_to_text[froute][0]
			assert set(g_froute_to_dir_to_startmofr_to_text.keys()) == set(routes.NON_SUBWAY_FUDGEROUTES)
			for froute, startmofr_to_text in g_froute_to_dir_to_startmofr_to_text.iteritems():
				assert 0 in startmofr_to_text
	return g_froute_to_dir_to_startmofr_to_text

def get_text(froute_, dir_, mofr_):
	return get_froute_to_dir_to_startmofr_to_text()[froute_][dir_].flooritem(mofr_)[1]

# arg dir_ could be (0, 1) or a latlng pair. 
def get_labels(froute_, dir_, zoom_, box_sw_, box_ne_):
	assert isinstance(zoom_, int) and isinstance(box_sw_, geom.LatLng) and isinstance(box_ne_, geom.LatLng)
	assert box_sw_.lat < box_ne_.lat and box_sw_.lng < box_ne_.lng
	if dir_ in (0, 1):
		direction = dir_
	else:
		direction = routes.routeinfo(froute_).dir_from_latlngs(dir_[0], dir_[1])
	def is_within_box(label__):
		start_latlng = label__['latlng']; end_latlng = label__['end_latlng']
		return start_latlng.is_within_box(box_sw_, box_ne_) or end_latlng.is_within_box(box_sw_, box_ne_)
	return [label for label in get_labels_for_zoom(froute_, direction, zoom_) if is_within_box(label)]

# return eg. [{'text': 'College St', 'latlng': geom.LatLng(43.0,-79.0), 'end_latlng': geom.LatLng(43.1,-79.1), 'rotation': 10}, ...]
@mc.decorate
def get_labels_for_zoom(froute_, dir_, zoom_):
	assert (dir_ in (0, 1)) and isinstance(zoom_, int)

	if zoom_ not in ZOOMS_WITH_STREETLABELS: 
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
		text = get_text(froute_, dir_, start_mofr)
		if (text != get_text(froute_, dir_, end_mofr)) or (not text) or (not is_route_straight_enough_here(ri, dir_, start_mofr, end_mofr)):
			start_mofr += max(1, mofrstep/10)
		else:
			start_latlng = ri.mofr_to_latlon(start_mofr, dir_)
			end_latlng = ri.mofr_to_latlon(end_mofr, dir_)
			heading = start_latlng.heading(end_latlng)
			svg_rotation = heading_to_svg_rotation(heading)
			if 180 <= heading < 360:
				start_latlng = end_latlng
			r.append({'text': text, 'latlng': start_latlng, 'end_latlng': end_latlng, 'rotation': svg_rotation})
			start_mofr += mofrstep
	return r

def get_streetlabel_svg(text_, rotation_, zoom_):
	assert zoom_ in ZOOMS_WITH_STREETLABELS
	fontsize = {13:3.5, 14:4, 15:4, 16:4.5, 17:5, 18:5, 19:5, 20:5, 21:5}[zoom_]
	# In SVG the y location of text seems to be the baseline i.e. bottom of upper-case letters.  So if we set that baseline 
	# to be the vertical middle of the graphic, and also use that vertical middle to coincide with the middle of the 
	# google maps polyline (which we do) then to get the text to sit in the middle of the polyline, we'll have to shift the 
	# text down.  I don't know why shifting it down by 1/3 of the font size does what we want, but it does. 
	textshift = fontsize/3.0 
	# SVG transforms are evaluated right to left.  So below we're translating, then rotating. 
	svgstr = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 100 100" version="1.1">
<g transform="rotate(%(rotation)d 50 50) translate(0 %(textshift)f)" >
<text x="49.7" y="49.7" fill="rgb(255,255,255)" font-family="sans-serif" font-size="%(fontsize)f">%(text)s</text>
<text x="50" y="50" fill="rgb(80,50,20)" font-family="sans-serif" font-size="%(fontsize)f">%(text)s</text>
</g>
</svg>''' % {'text': text_, 'rotation': rotation_, 'fontsize': fontsize, 'textshift': textshift}
	return svgstr

# Calculating all street labels for all routes and zoom levels takes about 30 seconds.  
# Some of the routes take about 1 second each on max zoom.  
# We might as well try to do that in advance, like when updating the live sandbox.  
# (That's where this is intended to be called from.  From the script that updates.) 
# - rather than make various first users wait a second here and a second there 
# for their street labels. 
def prime_memcache():
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		for direction in (0, 1):
			for zoom in ZOOMS_WITH_STREETLABELS:
				get_labels_for_zoom(froute, direction, zoom)

if __name__ == '__main__':

	import pprint
	pprint.pprint(get_labels_for_zoom('keele', 1, 21))


