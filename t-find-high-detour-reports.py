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

	for day in range(1, 3):
		for hour in range(0, 24, 3):
			for minute in (0,):
				tstr = "2014-03-%02d %02d:%02d" % (day, hour, minute)
				t = str_to_em(tstr)
				for froute in routes.NON_SUBWAY_FUDGEROUTES:
					for direction in (0, 1):
						num_on_route = 0; num_off_route = 0
						r = reports.calc_report_obj('locations', froute, direction, c.MIN_DATAZOOM, t, log_=log)
						for timeslice in r:
							for vi in timeslice[1:]:
								if vi.mofr != -1:
									num_on_route += 1
								else:
									num_off_route += 1

						if num_off_route+num_on_route > 0:
							print ('%.2f' % (float(num_off_route)/(num_off_route+num_on_route))), tstr, froute, direction




