#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore, streets
#from routes import *

#if __name__ == '__main__':
if 1:


	@picklestore.decorate
	def get_some_streets_polylines():
		all_streets_polylines = streets.get_polylines()
		box_sw = geom.LatLng(43.6267185, -79.4405155)
		box_ne = geom.LatLng(43.6708135, -79.3856697)
		fact = 0.4
		box_sw = geom.LatLng(avg(box_ne.lat, box_sw.lat, fact), avg(box_ne.lng, box_sw.lng, fact))
		some_streets_polylines = []
		for polyline in all_streets_polylines:
			if any(pt.is_within_box(box_sw, box_ne) for pt in polyline):
				some_streets_polylines.append(polyline)
		return some_streets_polylines

	@picklestore.decorate
	def get_snapgraph():
		polylines = get_some_streets_polylines()

		if 0:
			with open('s-test-graph-3') as fin:
				polylines = json.load(fin)
				for i, polyline in enumerate(polylines):
					polylines[i] = [geom.LatLng(pt) for pt in polyline]

		#util.to_json_file(polylines, 's-streets')

		return snapgraph.SnapGraph(polylines, forpaths=True, disttolerance=1)

	g_snapgraph = get_snapgraph()

	start = geom.LatLng(43.6610036, -79.3969135)
	dest = geom.LatLng(43.6683302, -79.3887810)

	#start = geom.LatLng(43.6544951, -79.4095628)
	#dest = geom.LatLng(43.6544389, -79.4093187)

	#snapgraph.pprint()
	#util.to_json_file([vert.pos() for vert in snapgraph.get_vertexes()], 's-verts')

	def get_path(startpos_, destpos_):
		visited_vertexes = []
		t0 = time.time()
		path_result = g_snapgraph.find_shortest_path_by_latlngs(startpos_, destpos_, visited_vertexes)
		printerr('find path took %.2f seconds' % (time.time() - t0))
		if path_result is None:
			return [[], []]
		else:
			dist, path = path_result
			return ([vert.pos() for vert in path], [vert.pos() for vert in visited_vertexes])

	@mc.decorate
	def get_snapgraph_polylines():
		return g_snapgraph.polylines

	#print get_path(start, dest)

if __name__ == '__main__':

	print g_snapgraph.find_shortest_path_by_latlngs(geom.LatLng(43.65615238,-79.39040110), geom.LatLng(43.66833020,-79.3887810))



