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


