#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random
import xml.etree.ElementTree as ET
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph, geom
from misc import *

if __name__ == '__main__':

	filename = sys.argv[1]
	#xmldoc = xml.dom.minidom.parse(filename)
	#print xmldoc.toprettyxml(newl='\n')

	plines = []
	et = ET.parse(filename)
	for path_elem in et.findall('./route/path'):
		pline = []
		plines.append(pline)
		for point_elem in path_elem.findall('./point'):
			lat = float(point_elem.attrib['lat'])
			lng = float(point_elem.attrib['lon'])
			pline.append(geom.LatLng(lat, lng))
	print util.to_json_str(plines)


