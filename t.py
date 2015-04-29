#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph
from misc import *
import geom
import numpy as np

if __name__ == '__main__':


	class C(object):

		def __init__(self, i_):
			self.i = i_

		def __hash__(self):
			print 'in hash %d' % self.i
			return hash(self.i)

	c1 = C(1)
	c2 = C(2)

	d = {}
	d[c1] = None
	d[c2] = None

