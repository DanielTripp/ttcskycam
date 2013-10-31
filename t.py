#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snaptogrid
#from routes import *

if __name__ == '__main__':

	l = range(5)
	for e in l:
		print e
		if e == 3:
			l.insert(-1, 'x')

	print l

