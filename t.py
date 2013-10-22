#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snaptogrid

if __name__ == '__main__':


	c = snaptogrid.SnapToGridCache([[geom.LatLng(40.0, 80.0), geom.LatLng(40.01, 80.01)]])

	print c.snap(geom.LatLng(40.1, 80.1), None)


