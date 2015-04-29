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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random
import xml.etree.ElementTree as ET
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph, geom
from misc import *

if __name__ == '__main__':

	filename = sys.argv[1]

	show_which_arg = sys.argv[2]
	if show_which_arg not in ('all', 'useforui', 'notuseforui'):
		raise Exception()
	show_useforui = show_which_arg in ('all', 'useforui')
	show_notuseforui = show_which_arg in ('all', 'notuseforui')
	#xmldoc = xml.dom.minidom.parse(filename)
	#print xmldoc.toprettyxml(newl='\n')

	stoptag_to_pt = {}
	et = ET.parse(filename)
	for stop_elem in et.findall('./route/stop'):
		stoptag = stop_elem.attrib['tag']
		lat = float(stop_elem.attrib['lat'])
		lng = float(stop_elem.attrib['lon'])
		stoptag_to_pt[stoptag] = geom.LatLng(lat, lng)

	direction_plines = []
	for direction_elem in et.findall('./route/direction'):
		directions_useforui = {'true': True, 'false': False}[direction_elem.attrib['useForUI']]
		use = (directions_useforui and show_useforui) or (not directions_useforui and show_notuseforui)
		printerr('%5s: %s / %s' % (use, direction_elem.attrib['tag'], direction_elem.attrib['title']))
		if use:
			direction_pline = []
			direction_plines.append(direction_pline)
			for stop_elem in direction_elem.findall('./stop'):
				stoptag = stop_elem.attrib['tag']
				direction_pline.append(stoptag_to_pt[stoptag])

	print util.to_json_str(direction_plines)

