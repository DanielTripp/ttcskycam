#!/usr/bin/python2.6

import sys, re, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, yards

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	log = False

	assert sys.argv[1] in ('tracks', 'streets')
	tracks_aot_streets = (sys.argv[1] == 'tracks')

	date = sys.argv[2]
	assert re.match(r'^\d\d\d\d-\d\d-\d\d$', date)

	start_time = str_to_em('%s 00:00' % date)
	end_time = start_time + 1000*60*60*24
	for froute in routes.NON_SUBWAY_FUDGEROUTES + ['']:
		printerr(froute)
		for vi in db.vi_select_generator(froute, end_time, start_time, dir_=None, include_unpredictables_=True, include_blank_fudgeroute_=False):
			printerr(vi)
			if (vi.is_a_streetcar() == tracks_aot_streets) and (not yards.in_a_yard_latlng(vi.latlng)):
				sg = vi.get_snapgraph()
				if len(vi.graph_locs) == 0 or sg.get_latlng(vi.graph_locs[0]).dist_m(vi.latlng) > 100:
					print vi

