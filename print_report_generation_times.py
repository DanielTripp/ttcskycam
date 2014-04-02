#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore
#from routes import *

if __name__ == '__main__':

	froute_to_timetally = defaultdict(lambda: [0, 0])

	if len(sys.argv) == 2:
		yyyymmdd = sys.argv[1]
	else:
		if em_to_str_hm(now_em())[:2] in ('00', '01', '02', '03'):
			yyyymmdd = em_to_str_ymd(now_em() - 1000*60*60*24)
		else:
			yyyymmdd = em_to_str_ymd(now_em())
		print yyyymmdd

	for hour in range(7, 23+1):
	#for hour in [10]:
		for minute in range(0, 60, 5):
		#for minute in [30]:
			report_timestr = '%s %02d:%02d' % (yyyymmdd, hour, minute)
			report_time = str_to_em(report_timestr)
			curs = db.conn().cursor()
			sqlstr = 'select time_inserted_str from reports where time = %s order by time_inserted_str' 
			curs.execute(sqlstr, [report_time])
			time_inserted_strs = []
			for row in curs:
				time_inserted_str = row[0]
				time_inserted_strs.append(time_inserted_str)
			curs.close()

			out_report_timestr = report_timestr[11:]
			if len(time_inserted_strs) > 0:
				secs_span = (str_to_em(max(time_inserted_strs)) - str_to_em(min(time_inserted_strs)))/1000
				# Seconds after the 'poll minute' that the last report was inserted: 
				time_finished_secs = (str_to_em(max(time_inserted_strs)) - (report_time-1000*60))/1000
				span_flagstr = '%-5s' % ('*'*rein_in((secs_span-25)/5, 0, 5)) # tricky: lowest non-zero yielded for secs_span=30, not 25 or 26.  
				finished_flagstr = '%-5s' % ('*'*rein_in((time_finished_secs-50)/5, 0, 5)) # Likewise with 55, not 50 or 51.
				print '%s  took: %3ds  finished: %3ds  %s %s' % \
						(out_report_timestr, secs_span, time_finished_secs, span_flagstr, finished_flagstr)
			else:
				print out_report_timestr



