#!/usr/bin/python2.6 -O

import sys, json, os.path, pprint, sqlite3, multiprocessing, time, subprocess, threading
from collections import *
from lru_cache import lru_cache
import vinfo, geom, routes, predictions, mc, c, snapgraph, traffic, picklestore, streets, system
from misc import *

@lru_cache(1)
@picklestore.decorate
def get_snapgraph():
	plines = [
	[
	[43.658403, -79.442825], 
	[43.666630, -79.403601] 
	], 
	[
	[43.657658, -79.442568], 
	[43.660266, -79.441280], 
	[43.657906, -79.437633], 
	[43.661228, -79.436731], 
	[43.659086, -79.432054], 
	[43.663681, -79.430165], 
	[43.660669, -79.423685], 
	[43.664906, -79.421514], 
	[43.660755, -79.419319], 
	[43.666195, -79.420853], 
	[43.660600, -79.417838], 
	[43.665230, -79.418607], 
	[43.662625, -79.412570], 
	[43.669579, -79.405017] 
	]
	]

	#r = system.SystemSnapGraph(plines)
	r = snapgraph.SnapGraph(plines)
	return r

if __name__ == '__main__':

	pass


