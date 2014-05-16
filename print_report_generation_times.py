#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, c, reports, streetlabels, snapgraph, picklestore
#from routes import *

def dots(val_, min_, max_):
	ratio = rein_in((val_-min_)/float(max_-min_), 0, 1.0)
	max_n = 20
	n = int(ratio*max_n)
	if n == max_n:
		r = '.'*(max_n-1) + '*'
	else:
		r = '.'*n
	r = ('%-'+str(max_n)+'s') % r
	return r

if __name__ == '__main__':

	froute_to_timetally = defaultdict(lambda: [0, 0])

	if len(sys.argv) < 2:
		sys.exit('Takes two args: 1) (dev|prod) and 2) a date [optional].')

	appversiontype = sys.argv[1]
	if appversiontype not in ('dev', 'prod'):
		raise Exception()
	if len(sys.argv) == 3:
		yyyymmdd = sys.argv[2]
		date_was_cmdline_arg = True
	else:
		if em_to_str_hm(now_em())[:2] in ('00', '01', '02', '03'):
			yyyymmdd = em_to_str_ymd(now_em() - 1000*60*60*24)
		else:
			yyyymmdd = em_to_str_ymd(now_em())
		date_was_cmdline_arg = False
		print yyyymmdd

	for hour in range(24):
	#for hour in [10]:
		for minute in range(0, 60, 5):
		#for minute in [30]:
			report_timestr = '%s %02d:%02d' % (yyyymmdd, hour, minute)
			report_time = str_to_em(report_timestr)
			if not date_was_cmdline_arg:
				if report_time < now_em() - 1000*60*60:
					continue
				elif report_time > now_em() + 1000*60*5:
					break
			curs = db.conn().cursor()
			sqlstr = 'select time_inserted_str from reports where time = %s and app_version '\
					+('like' if appversiontype == 'dev' else 'not like' )+' \'dev%%\' order by time_inserted_str' 
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
				span_flagstr = dots(secs_span, 20, 45)
				finished_flagstr = dots(time_finished_secs, 30, 60)
				print '%s  took: %3ds  finished: %3ds  %s %s' % \
						(out_report_timestr, secs_span, time_finished_secs, span_flagstr, finished_flagstr)
			else:
				print out_report_timestr



