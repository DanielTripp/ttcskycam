#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions

if __name__ == '__main__':


	routes.get_intersections()
	for froute in routes.FUDGEROUTES:
		routes.routeinfo(froute)


