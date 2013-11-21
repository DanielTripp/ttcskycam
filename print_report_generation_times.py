#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore
#from routes import *

if __name__ == '__main__':

	froute_to_timetally = defaultdict(lambda: [0, 0])

	yyyymmdd = '2013-11-15'

	for hour in range(7, 23+1):
	#for hour in [10]:
		for minute in range(0, 60, 5):
		#for minute in [30]:
			tstr = '%s %02d:%02d' % (yyyymmdd, hour, minute)
			t = str_to_em(tstr)
			curs = db.conn().cursor()
			sqlstr = 'select froute, time_inserted_str from reports where time = %s order by time_inserted_str, froute' 
			curs.execute(sqlstr, [t])
			time_inserted_strs = []
			froute_to_mintime_n_maxtime = defaultdict(lambda: [None,None])
			last_froute = None
			for row in curs:
				tstr = row[1]
				time_inserted_strs.append(tstr)
				froute = row[0]
				if froute != last_froute:
					froute_to_mintime_n_maxtime[last_froute][1] = tstr
					froute_to_mintime_n_maxtime[froute][0] = tstr
					last_froute = froute
			curs.close()

			for froute, (mintime, maxtime) in froute_to_mintime_n_maxtime.iteritems():
				#print froute, mintime, maxtime
				if maxtime and mintime:
					timegap = (str_to_em(maxtime) - str_to_em(mintime))/1000
					froute_to_timetally[froute][0] += timegap
					froute_to_timetally[froute][1] += 1
					#print froute, timegap
				else:
					pass # print 'omitting %s' % froute


			tstr = tstr[11:]
			if len(time_inserted_strs) > 0:
				numsecs = (str_to_em(max(time_inserted_strs)) - str_to_em(min(time_inserted_strs)))/1000
				print tstr, numsecs  
			else:
				print tstr


	if 0:
		for timetally, froute in sorted([(float(y[0])/y[1], x) for x, y in froute_to_timetally.items()], reverse=True):
			print timetally, froute


