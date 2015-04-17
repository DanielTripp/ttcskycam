#!/usr/bin/python2.6

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

