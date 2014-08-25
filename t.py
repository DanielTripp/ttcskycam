#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	sg = system.get_snapgraph()
	#sg.build_paths_db_get_snap_info()
	sg.build_paths_db_get_stop2stop_distsnpaths()


