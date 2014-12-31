#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, c, reports, streetlabels, snapgraph, streets

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	log = False

	printerr('Starting up...')
	streets.get_snapgraph()
	tracks.get_snapgraph()
	routes.prime_routeinfos()
	printerr('... done.')

	do_all = 0
	do_print = 0

	for day in ['2014-09-12']:
		for hour in (range(24) if do_all else (10,)):
			for minute in ((0, 30) if do_all else range(10)):
				minute_t0 = time.time()
				tstr = '%s %02d:%02d' % (day, hour, minute)
				t = str_to_em(tstr)
				traffic_secs = 0; locations_secs = 0
				for froute in (routes.NON_SUBWAY_FUDGEROUTES if do_all else ['queen', 'king', 'dufferin']):
					for direction in ((0, 1) if do_all else (0, 1)):
						printerr(tstr, froute, direction, '...')

						db.get_vid_to_vis_bothdirs(froute, 30, t)

						for reporttype in (['locations', 'traffic'] if do_all else ['traffic', 'locations']):
							reporttype_t0 = time.time()
							print tstr, froute, direction, ('%s:' % reporttype)
							r = reports.calc_report_obj(reporttype, froute, direction, c.MIN_DATAZOOM, t, log_=log)
							if do_print:
								print util.to_json_str(r, indent=1)
							otherzooms_t0 = time.time()
							for datazoom in range(c.MIN_DATAZOOM+1, c.MAX_DATAZOOM+1):
								r = reports.calc_report_obj(reporttype, froute, direction, datazoom, t, log_=log)
								if do_print:
									print util.to_json_str(r, indent=1)
							otherzooms_t1 = time.time()
							#print 'seconds for other zooms: %.1f' % (otherzooms_t1 - otherzooms_t0)
							reporttype_t1 = time.time()
							if reporttype == 'traffic':
								traffic_secs += (reporttype_t1 - reporttype_t0)
							else:
								locations_secs += (reporttype_t1 - reporttype_t0)
				minute_t1 = time.time()
				print 'Seconds spent calculating: %.1f.  (%.1f traffic, %.1f locations.)' % \
						(minute_t1 - minute_t0, traffic_secs, locations_secs)



