#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

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
	path = get_sg(sgname_).find_multipath(latlngs_)
	return (path.latlngs() if path is not None else None)

def find_paths(sgname_, startlatlng_, destlatlng_, snap_style_, snap_tolerance_, k_, get_visited_vertexes_):
	assert snap_style_ in ('1', 'm', 'pcp')

	sg = get_sg(sgname_)

	k = k_
	if isinstance(k, Sequence): # Will come from client as a list, which isn't hashable and so it can't 
		# be an argument to find_paths() because of the caching that it does based on its arguments. 
		k = tuple(k)

	visited_vertexes = (set() if get_visited_vertexes_ else None)
	dists_n_pathsteps = sg.find_paths(startlatlng_, snap_style_, destlatlng_, snap_style_, snap_tolerance=snap_tolerance_, k=k, \
			out_visited_vertexes=visited_vertexes)
	path_latlngs = []
	path_ways = ([] if sgname_ == 'system' and snap_style_ == 'pcp' else None)
	for dist, pathsteps in dists_n_pathsteps:
		path = snapgraph.Path([pathsteps], sg)
		path_latlngs.append(path.latlngs())
		if path_ways is not None:
			path_ways.append(sg.pathsteps_to_way(pathsteps))

	if get_visited_vertexes_:
		visited_vertex_latlngs = [sg.get_latlng(vvert) for vvert in visited_vertexes]
	else:
		visited_vertex_latlngs = None

	if path_ways is not None:
		assert len(path_ways) == len(path_latlngs)

	return {'path_latlngs': path_latlngs, 'visited_vertex_latlngs': visited_vertex_latlngs, 
			'path_ways': path_ways}

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


