#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore
#from routes import *

if __name__ == '__main__':

	for hour in range(7, 23+1):
		for minute in range(0, 60, 5):
			tstr = '2013-11-12 %02d:%02d' % (hour, minute)
			t = str_to_em(tstr)
			curs = db.conn().cursor()
			sqlstr = 'select time_inserted_str from reports where time = %s' 
			curs.execute(sqlstr, [t])
			time_inserted_strs = []
			for row in curs:
				time_inserted_strs.append(row[0])
			curs.close()
			tstr = tstr[11:]
			if len(time_inserted_strs) > 0:
				numsecs = (str_to_em(max(time_inserted_strs)) - str_to_em(min(time_inserted_strs)))/1000
				print tstr, numsecs  
			else:
				print tstr, '-'




