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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	def latlng_from_arg(str_):
		r = str_.strip()
		r = r.replace('(', '[').replace(')', ']')
		if not (r.startswith('[') and r.endswith(']')):
			r = '[%s]' % r
		r = json.loads(r)
		return geom.LatLng(r)

	if len(sys.argv) != 4:
		printerr("Need args: orig_latlng dest_latlng PACKED")
	else:
		orig = latlng_from_arg(sys.argv[1])
		dest = latlng_from_arg(sys.argv[2])

		if sys.argv[3] == '--packed':
			print system.get_packed_ways(orig, dest)
		elif sys.argv[3] == '--nopacked':
			sg = system.get_snapgraph()
			result = sg.get_ways(orig, dest)
			for i, froutesndirs in enumerate(result):
				print i, froutesndirs
		else:
			raise Exception()

