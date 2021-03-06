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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	log = False

	do_print = 1 

	t = round_down_by_minute(now_em())

	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		for direction in (0, 1):
			print froute, direction, 'traffic:'
			r = reports.calc_report_obj('traffic', froute, direction, c.MIN_DATAZOOM, t, log_=log)
			if do_print:
				print util.to_json_str(r, indent=1)
			print froute, direction, 'locations:'
			r = reports.calc_report_obj('locations', froute, direction, c.MIN_DATAZOOM, t, log_=log)
			if do_print:
				print util.to_json_str(r, indent=1)


