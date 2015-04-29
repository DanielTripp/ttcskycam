#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore, streets
#from routes import *

if __name__ == '__main__':

	encoded_vals = sys.argv[1:]
	decoded_vals = [decode_url_paramval(v) for v in encoded_vals]
	print decoded_vals

