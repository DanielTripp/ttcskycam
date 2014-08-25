#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, picklestore, streets, testgraph

def get_sg(sgname_):
	if sgname_ == 'streets':
		return streets.get_snapgraph()
	elif sgname_ == 'tracks':
		return tracks.get_snapgraph()
	elif sgname_ == 'system':
		return system.get_snapgraph()
	elif sgname_ == 'testgraph':
		return testgraph.get_snapgraph()
	else:
		raise Exception()

def get_infos_for_box(sgname_, sw_, ne_):
	return get_sg(sgname_).get_infos_for_box(sw_, ne_)

def get_connected_vert_latlngs(sgname_, vertid_):
	return [vert.pos() for vert in get_sg(sgname_).get_connected_vertexes(vertid_)]

def find_multipath(sgname_, latlngs_):
	path = get_sg(sgname_).find_multipath(latlngs_)[1]
	return (path.latlngs() if path is not None else None)

def find_paths(sgname_, startlatlng_, destlatlng_, multisnap_, snap_tolerance_, k_, get_visited_vertexes_):
	sg = get_sg(sgname_)

	k = k_
	if isinstance(k, Sequence): # Will come from client as a list, which isn't hashable and so it can't 
		# be an argument to find_paths() because of the caching that it does based on its arguments. 
		k = tuple(k)

	visited_vertexes = (set() if get_visited_vertexes_ else None)
	snap_arg = ('m' if multisnap_ else '1')
	dists_n_pathsteps = sg.find_paths(startlatlng_, snap_arg, destlatlng_, snap_arg, snap_tolerance=snap_tolerance_, k=k, \
			out_visited_vertexes=visited_vertexes)
	path_latlngs = []
	for dist, pathsteps in dists_n_pathsteps:
		path = snapgraph.Path([pathsteps], sg)
		path_latlngs.append(path.latlngs())

	if get_visited_vertexes_:
		visited_vertex_latlngs = [sg.get_latlng(vvert) for vvert in visited_vertexes]
	else:
		visited_vertex_latlngs = None

	return {'path_latlngs': path_latlngs, 'visited_vertex_latlngs': visited_vertex_latlngs}

def multisnap(sgname_, latlng_, radius_):
	posaddrs = get_sg(sgname_).multisnap(latlng_, radius_)
	return [(get_sg(sgname_).get_latlng(posaddr), str(posaddr)) for posaddr in posaddrs]

def get_pline_latlngs(sgname_, plinename_):
	plinename2pts = get_sg(sgname_).plinename2pts
	if plinename_ in plinename2pts:
		return plinename2pts[plinename_]
	else:
		return None

def get_vert_pos(sgname_, vertname_or_idx_):
	sg = get_sg(sgname_)
	if isinstance(vertname_or_idx_, str):
		vert = sg.get_vertex(vertname_or_idx_)
	elif isinstance(vertname_or_idx_, int):
		if vertname_or_idx_ in xrange(len(sg.verts)):
			vert = sg.verts[vertname_or_idx_]
		else:
			vert = None
	else:
		raise Exception()
	return (vert.pos() if vert is not None else None)

def get_posaddr_latlng(sgname_, posaddr_str_):
	posaddr = snapgraph.parse_posaddr(posaddr_str_)
	if posaddr is None:
		return None
	else:
		return get_sg(sgname_).get_latlng(posaddr)

if __name__ == '__main__':

	for i in range(300):
		try:
			print get_connected_vert_latlngs(i)
		except KeyError:
			print 'keyerror on', i


