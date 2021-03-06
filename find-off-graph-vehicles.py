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

import sys, re, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, c, reports, streetlabels, snapgraph, yards

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	log = False

	assert sys.argv[1] in ('tracks', 'streets')
	tracks_aot_streets = (sys.argv[1] == 'tracks')

	date = sys.argv[2]
	assert re.match(r'^\d\d\d\d-\d\d-\d\d$', date)

	error_lats = set([43.62060200, 43.62061700])

	start_time = str_to_em('%s 00:00' % date)
	end_time = start_time + 1000*60*60*24
	for froute in routes.NON_SUBWAY_FUDGEROUTES + ['']: 
		printerr(froute)
		for vi in db.vi_select_generator(froute, end_time, start_time, dir_=None, include_unpredictables_=True, include_blank_fudgeroute_=False):
			if (vi.is_a_streetcar() == tracks_aot_streets) and (not yards.in_a_yard_latlng(vi.latlng)) and \
					vi.latlng.lat not in error_lats:
				sg = vi.get_snapgraph()
				if sg.si_gridsquaresys.is_in_boundingbox(vi.latlng):
					if len(vi.graph_locs) == 0 or sg.get_latlng(vi.graph_locs[0]).dist_m(vi.latlng) > 100:
						print vi


