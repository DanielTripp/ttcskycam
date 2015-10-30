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

# Abbreviations / vocabulary:
# pcp = pre-calculated paths.
# way = list of (fudgeroutename / direction) pairs.

import sys, json, os.path, pprint, sqlite3, multiprocessing, time, subprocess, threading
from itertools import *
from collections import *
from lru_cache import lru_cache
import vinfo, geom, grid, routes, predictions, mc, c, snapgraph, traffic, picklestore, streets
from misc import *

USE_CITY_TESTING_SUBSET = False

class SystemSnapGraph(snapgraph.SnapGraph):

	def __init__(self, froute_to_pline_):
		super(SystemSnapGraph, self).__init__(froute_to_pline_, forpaths_disttolerance=70, name='trip', 
				vertex_limit_zones_filename='systemsnapgraph-vertex-limit-zones.yaml')
		self.waiting_for_vehicle_equiv_dist = kmph_to_mps(15)*(10*60)
		self.add_inter_pline_transfers()
		#self.add_periodic_stops()
		self.init_floyd_warshall_data()
		self.build_stopvertidx_by_vertidx()
		self.build_pcp()
		self.build_misc()

	def build_misc(self):
		numverts = len(self.verts)
		self.edge_by_vertidxes = [[None]*numverts for i in range(numverts)]
		for vertidx, edges in enumerate(self.edges):
			if len(set(edge.vertidx for edge in edges)) != len(edges):
				raise Exception('More than one edge from vert %d.')
			for edge in edges:
				self.edge_by_vertidxes[vertidx][edge.vertidx] = edge

	def is_stop_vert(self, vertidx_):
		return (self.stopvertidx_by_vertidx[vertidx_] is None)

	def add_periodic_stops(self):
		DIST_STEP = 1000
		for plinename in [x for x in self.plinename2pts.iterkeys() if not x.startswith('!')]:
			if self.min_vert_mapl(plinename) > 100:
				self.add_stop(plinename, 0)
			if self.max_vert_mapl(plinename) < self.get_pline_len(plinename) - 100:
				self.add_stop(plinename, self.get_pline_len(plinename)-1)
			for vert2_ptidx, vert1_ptidx in hopscotch(sorted(self.plinename_to_ptidx_to_vertidx[plinename].keys(), reverse=True)):
				vert1_mapl = self.plinename_to_ptidx_to_mapl[plinename][vert1_ptidx]
				vert2_mapl = self.plinename_to_ptidx_to_mapl[plinename][vert2_ptidx]
				if (vert2_mapl - vert1_mapl) > DIST_STEP:
					num_stops_to_add = 1
					while (vert2_mapl - vert1_mapl)/(num_stops_to_add+1) > DIST_STEP:
						num_stops_to_add += 1
					for stopnum in range(num_stops_to_add):
						new_stop_mapl = vert1_mapl + ((vert2_mapl - vert1_mapl)/(num_stops_to_add+1))*(stopnum+1)
						self.add_stop(plinename, new_stop_mapl)
		self.build_spatial_index()

	def min_vert_mapl(self, plinename_):
		return self.plinename_to_ptidx_to_mapl[plinename_][min(self.plinename_to_ptidx_to_vertidx[plinename_].keys())]

	def max_vert_mapl(self, plinename_):
		return self.plinename_to_ptidx_to_mapl[plinename_][max(self.plinename_to_ptidx_to_vertidx[plinename_].keys())]

	def add_stop(self, plinename_, mapl_):
		new_vert_on_pline = self.add_vertex_at_mapl(plinename_, mapl_)
		new_vert_on_pline = self.add_penalizing_stop_subgraph_to_vertex(new_vert_on_pline)[1]
		self.rename_vert(new_vert_on_pline, '!%s' % new_vert_on_pline.name)

	def add_vertex_at_mapl(self, plinename_, mapl_):
		latlng = self.mapl_to_latlng(plinename_, mapl_)
		presplit_snapped_posaddr = self.snap_to_pline(latlng, 100, plinename_)
		new_ptidx = presplit_snapped_posaddr.ptidx+1
		self.plinename2pts[plinename_].insert(new_ptidx, latlng)
		self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(plinename_, new_ptidx)
		self.adjust_addrs_in_vertexes_to_deal_with_polyline_split(plinename_, new_ptidx)
		ptaddr = snapgraph.PtAddr(plinename_, new_ptidx)
		self.plinename_to_ptidx_to_vertidx[plinename_] = {(ptidx+1 if ptidx >= new_ptidx else ptidx): vertidx \
				for ptidx, vertidx in self.plinename_to_ptidx_to_vertidx[plinename_].iteritems()}
		bounding_verts = self.get_bounding_verts(snapgraph.PosAddr(ptaddr, 0.0))
		self.plinename_to_ptidx_to_mapl[plinename_].insert(new_ptidx, mapl_)
		new_vert = snapgraph.Vertex.create_open(self)
		new_vert.ptaddrs.add(ptaddr)
		new_vert.set_closed()
		new_vertidx = self.add_vert(new_vert)
		self.plinename_to_ptidx_to_vertidx[plinename_][new_ptidx] = new_vertidx
		assert len(bounding_verts) in (1, 2)
		for i, bounding_vert in enumerate(bounding_verts):
			bounding_vertidx = self.vertname_to_idx[bounding_vert.name]
			if len(bounding_verts) == 2:
				other_bounding_vert = bounding_verts[int(not bool(i))]
				other_bounding_vertidx = self.vertname_to_idx[other_bounding_vert.name]
				filter_in_place(self.edges[other_bounding_vertidx], lambda edge: edge.vertidx != bounding_vertidx)
			bounding_vert_ptidx = bounding_vert.get_ptidx(plinename_)
			wdist_new_vert_to_bounding_vert = self.get_wdist_between_points(plinename_, new_ptidx, bounding_vert_ptidx)
			edge_new_vert_to_bounding_vert = snapgraph.Edge(bounding_vertidx, wdist_new_vert_to_bounding_vert, plinename_)
			self.edges[new_vertidx].append(edge_new_vert_to_bounding_vert)
			edge_bounding_vert_to_new_vert = snapgraph.Edge(new_vertidx, wdist_new_vert_to_bounding_vert, plinename_)
			self.edges[bounding_vertidx].append(edge_bounding_vert_to_new_vert)
		return new_vert

	def adjust_addrs_in_vertexes_to_deal_with_polyline_split(self, plinename_, new_ptidx_):
		for vert in self.verts:
			for ptaddr in vert.ptaddrs:
				if ptaddr.plinename == plinename_ and ptaddr.ptidx >= new_ptidx_:
					ptaddr.ptidx += 1

	def snap_to_pline(self, latlng_, snap_tolerance_, plinename_):
		for posaddr in self.multisnap(latlng_, snap_tolerance_, includeverts=False):
			if posaddr.plinename == plinename_:
				return posaddr
		else:
			return None

	def add_inter_pline_transfers(self):
		for orig_vert in self.verts[:]:
			self.add_penalizing_stop_subgraph_to_vertex(orig_vert)

		self.build_spatial_index()

	# returns a list of the vertexes that this function call created, starting with the stop vert. 
	def add_penalizing_stop_subgraph_to_vertex(self, orig_vert_):
		r = []
		orig_vert_idx = self.vertname_to_idx[orig_vert_.name]
		vertpos = orig_vert_.pos()
		new_stop_vert_ptaddrs = []
		for plinename in orig_vert_.get_plinenames():
			new_pline_vertname = get_vertname_for_orig_pline(orig_vert_, plinename)
			orig_pline_to_stop_plinename = get_orig_pline_to_stop_plinename(orig_vert_, plinename)
			stop_to_orig_pline_plinename = get_stop_to_orig_pline_plinename(orig_vert_, plinename)
			new_pline_vert_ptaddrs = [orig_vert_.get_ptaddr(plinename), 
					snapgraph.PtAddr(orig_pline_to_stop_plinename, 0), snapgraph.PtAddr(stop_to_orig_pline_plinename, 1)]

			new_stop_vert_ptaddrs.append(snapgraph.PtAddr(orig_pline_to_stop_plinename, 1))
			new_stop_vert_ptaddrs.append(snapgraph.PtAddr(stop_to_orig_pline_plinename, 0))

			new_pline_vert = snapgraph.Vertex.create_closed(new_pline_vertname, new_pline_vert_ptaddrs, self)
			r.append(new_pline_vert)
			new_pline_vertidx = self.add_vert(new_pline_vert)
			for bounding_vert in self.get_verts_bounding_vertexes(orig_vert_, plinename):
				for edge in self.edges[self.vertname_to_idx[bounding_vert.name]]:
					if edge.vertidx == orig_vert_idx and edge.plinename == plinename:
						edge.vertidx = new_pline_vertidx
						break
			self.plinename_to_ptidx_to_vertidx[plinename][orig_vert_.get_ptidx(plinename)] = new_pline_vertidx
			self.plinename2pts[orig_pline_to_stop_plinename] = [vertpos, vertpos]
			self.plinename2pts[stop_to_orig_pline_plinename] = [vertpos, vertpos]
			self.plinename_to_ptidx_to_mapl[orig_pline_to_stop_plinename] = [0.0, 0.0]
			self.plinename_to_ptidx_to_mapl[stop_to_orig_pline_plinename] = [0.0, 0.0]
			self.edges[new_pline_vertidx] = \
					[edge.copy() for edge in self.edges[self.vertname_to_idx[orig_vert_.name]] if edge.plinename == plinename]
			assert len(self.verts) == len(self.edges)

		self.del_vert(orig_vert_)
		new_stop_vertname = get_vertname_for_stop(orig_vert_)
		new_stop_vert = snapgraph.Vertex.create_closed(new_stop_vertname, new_stop_vert_ptaddrs, self)
		r.insert(0, new_stop_vert)
		new_stop_vertidx = self.add_vert(new_stop_vert)

		for plinename in orig_vert_.get_plinenames():
			new_pline_vert = self.get_vertex(get_vertname_for_orig_pline(orig_vert_, plinename))
			new_pline_vertidx = self.vertname_to_idx[new_pline_vert.name]
			self.edges[new_pline_vertidx].append(
					snapgraph.Edge(new_stop_vertidx, 0.0, get_orig_pline_to_stop_plinename(orig_vert_, plinename), 0))
			self.edges[new_stop_vertidx].append(
					snapgraph.Edge(new_pline_vertidx, self.waiting_for_vehicle_equiv_dist, get_stop_to_orig_pline_plinename(orig_vert_, plinename), 0))

			self.plinename_to_ptidx_to_vertidx[get_orig_pline_to_stop_plinename(orig_vert_, plinename)] = \
					{0: new_pline_vertidx, 1: new_stop_vertidx}
			self.plinename_to_ptidx_to_vertidx[get_stop_to_orig_pline_plinename(orig_vert_, plinename)] = \
					{0: new_stop_vertidx, 1: new_pline_vertidx}

		return r

	def del_vert(self, vert_):
		vertidx = self.vertname_to_idx[vert_.name]
		del self.vertname_to_idx[vert_.name]
		self.vertname_to_idx = {vertname: (idx-1 if idx > vertidx else idx) for vertname, idx in self.vertname_to_idx.iteritems()}
		del self.verts[vertidx]
		del self.edges[vertidx]

		for edges in self.edges:
			for edge in edges:
				if edge.vertidx == vertidx:
					raise Exception()
				elif edge.vertidx > vertidx:
					edge.vertidx -= 1

		for ptidx_to_vertidx in self.plinename_to_ptidx_to_vertidx.itervalues():
			newdict = ptidx_to_vertidx.copy()
			for ptidx in newdict.iterkeys():
				if newdict[ptidx] == vertidx:
					raise Exception()
				elif newdict[ptidx] > vertidx:
					newdict[ptidx] -= 1
			ptidx_to_vertidx.update(newdict)

	def add_vert(self, vert_):
		self.verts.append(vert_)
		self.edges.append([])
		vertidx = len(self.verts)-1
		self.vertname_to_idx[vert_.name] = vertidx
		return vertidx

	def iter_nonstop_verts(self):
		return (vert for vertidx, vert in enumerate(self.verts) if not self.is_stop_vert(vertidx))

	def get_snap_error_fudge_dist_for_find_paths(self, latlng_, loc_):
		# Figuring that walking is 1/3 the speed of a transit vehicle. 
		if latlng_ is None:
			return 0.0
		else:
			return self.get_latlng(loc_).dist_m(latlng_)*3

	def build_pcp(self):
		self.use_vert_only_floyd_warshall = True
		self.build_pcp_vert2vert_distsnpaths()
		self.use_vert_only_floyd_warshall = False
		self.use_floyd_warshall = True
		# tdr unc self.build_pcp_multisnap_info()

	def build_stopvertidx_by_vertidx(self):
		# This stores the adjacent stop vertidx for each non-stop vertidx. 
		# If the element in this list is None, that means the element IS a stop.
		self.stopvertidx_by_vertidx = [None]*len(self.verts)
		for vertidx, vert in enumerate(self.verts):
			if not is_stop_vert(vert):
				self.stopvertidx_by_vertidx[vertidx] = self.get_stop_vertidx(vertidx)

	def build_pcp_vert2vert_distsnpaths(self):
		# Will be somewhat sparsely populated, because this function only deals with non-stop verts: 
		self.pcp_vert2vert_distsnpaths = [[None]*len(self.verts) for i in range(len(self.verts))]
		vert_combos = list(combinations(self.iter_nonstop_verts(), 2))
		t0 = time.time()
		self.pcp_yen_k = (10, 2.0)
		for i, (vert1, vert2) in enumerate(vert_combos):
			distsnpaths = self.find_paths(None, vert1, None, vert2, k=self.pcp_yen_k)
			vert1idx = self.vertname_to_idx[vert1.name]
			vert2idx = self.vertname_to_idx[vert2.name]
			self.pcp_vert2vert_distsnpaths[vert1idx][vert2idx] = distsnpaths
			self.pcp_vert2vert_distsnpaths[vert2idx][vert1idx] = self.get_reverse_dir_distsnpaths(distsnpaths)
			print_est_time_remaining('build_pcp_vert2vert_distsnpaths', t0, i, len(vert_combos), 100)
		printerr('pcp build time: %.1f' % (time.time() - t0)) # tdr 

	@staticmethod
	def get_reverse_dir_distsnpaths(distsnpaths_):
		# We assume that any (vertex-to-vertex) path in our system graph is valid in the reverse order too, 
		# and will have the same length (dist). 
		# The plines traversed might be different around the stops, but the vertex list will be the same. 
		r = []
		for dist, forwardpath in distsnpaths_:
			r.append((dist, forwardpath[::-1]))
		return r

	def build_pcp_multisnap_info(self):
		latstep = 0.0025; lngstep = 0.00333
		self.pcp_max_snap_radius = 3000
		bbox = self.get_pcp_snap_boundingbox()
		self.pcp_gridsquaresys = grid.GridSquareSystem(None, None, latstep, lngstep, bbox)
		self.pcp_multisnap_posaddrndists_by_gridsquareidx = []
		t0 = time.time()
		gridsquareidxes = range(self.pcp_gridsquaresys.num_idxes())
		for i, gridsquareidx in enumerate(gridsquareidxes):
			gridsquare = self.pcp_gridsquaresys.gridsquare(gridsquareidx)
			latlng = gridsquare.center_latlng()
			posaddrsndists = self.multisnap_with_dists(latlng, self.pcp_max_snap_radius, \
					includeverts=False, plineomitflag='w')
			self.pcp_multisnap_posaddrndists_by_gridsquareidx.append(posaddrsndists)
			print_est_time_remaining('build_pcp_multisnap_info', t0, i, len(gridsquareidxes), 100)
		assert len(self.pcp_multisnap_posaddrndists_by_gridsquareidx) == len(gridsquareidxes)

	def get_pcp_snap_boundingbox(self):
		all_pts = sum(self.plinename2pts.itervalues(), [])
		all_pts_boundingbox = geom.BoundingBox(all_pts)
		return all_pts_boundingbox.get_enlarged(self.pcp_max_snap_radius)

	def get_bounding_box(self):
		return geom.BoundingBox(sum(self.plinename2pts.itervalues(), []))

	def find_paths(self, startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance=100, 
			k=None, out_visited_vertexes=None):
		if startlocs_ == 'pcp' and destlocs_ == 'pcp':
			if not yen_k_lte(k, self.pcp_yen_k):
				raise Exception('Yen k arg %s (effectively %s) is larger than value used for pcp data %s.' % \
						(k, snapgraph.get_yen_int_and_float(k), self.pcp_yen_k))
			r = self.pcp_find_paths(startlatlng_, destlatlng_, snap_tolerance)
			self.remove_useless_paths(r)
			snapgraph.yen_reduce_list_according_to_k(r, k)
			return r
		else:
			return super(SystemSnapGraph, self).find_paths(startlatlng_, startlocs_, destlatlng_, destlocs_, \
					snap_tolerance=snap_tolerance, k=k, out_visited_vertexes=out_visited_vertexes)

	def remove_useless_paths(self, distsnpaths_):
		self.remove_looping_paths(distsnpaths_)
		self.remove_alongside_paths(distsnpaths_)

	def remove_looping_paths(self, distsnpaths_):
		for i in xrange(len(distsnpaths_)-1, -1, -1):
			path = distsnpaths_[i][1]
			if self.does_path_loop(path):
				distsnpaths_.pop(i)

	def does_path_loop(self, path_):
		stop_vertidxes = set()
		for i, vertidx in list(enumerate(path_))[1:-1]:
			stop_vertidx = self.stopvertidx_by_vertidx[vertidx]
			if stop_vertidx is None:
				stop_vertidx = vertidx
			prev_vertidx = path_[i-1]; next_vertidx = path_[i+1]
			if (stop_vertidx not in (prev_vertidx, vertidx, next_vertidx)) and (stop_vertidx in stop_vertidxes):
				return True
			stop_vertidxes.add(stop_vertidx)
		return False

	# Will remove the latter of a pair of paths that differ in only two verts, such as will happen 
	# when two routes are alongside each other and share two consecutive stops, and path X says to 
	# transfer at one stop and path Y says to transfer at the next stop.  
	# (Example: queen / ossington / shaw, or king / ossington / shaw.) 
	# Only one of these paths is useful to use, not both, so we want to remove one (might as well be the latter - 
	# we're assuming the list arg is sorted by dist.) 
	def remove_alongside_paths(self, distsnpaths_):
		for i1, (dist1, path1), i2, (dist2, path2) in hopscotch_enumerate(distsnpaths_, reverse=True):
			if len(path1) == len(path2):
				num_diffs = 0
				for e1, e2 in zip(path1, path2):
					if e1 != e2:
						num_diffs += 1
					if num_diffs == 3:
						break
				else:
					if num_diffs == 2:
						distsnpaths_.pop(i2)

	def pcp_find_paths(self, orig_latlng_, dest_latlng_, snap_tolerance_):
		if snap_tolerance_ > self.pcp_max_snap_radius:
			raise Exception('Snap radius arg %.1f is larger than radius used for pcp data %.1f.' % (snap_tolerance_, self.pcp_max_snap_radius))
		r = []
		for orig_posaddr in self.pcp_multisnap(orig_latlng_, snap_tolerance_):
			orig_bounding_vertidxes = set(self.get_bounding_vertidxes(orig_posaddr))
			orig_walking_dist = self.get_snap_error_fudge_dist_for_find_paths(orig_latlng_, orig_posaddr)
			for dest_posaddr in self.pcp_multisnap(dest_latlng_, snap_tolerance_):
				dest_bounding_vertidxes = set(self.get_bounding_vertidxes(dest_posaddr))
				dest_walking_dist = self.get_snap_error_fudge_dist_for_find_paths(dest_latlng_, dest_posaddr)
				walking_dists = orig_walking_dist + dest_walking_dist
				if self.no_verts_between(orig_posaddr, dest_posaddr):
					dist = walking_dists + self.waiting_for_vehicle_equiv_dist + self.get_wdist(orig_posaddr, dest_posaddr)
					r.append((dist, [orig_posaddr, dest_posaddr]))
				else:
					for orig_boundingvertidx in orig_bounding_vertidxes:
						for dest_boundingvertidx in dest_bounding_vertidxes:
							ends_dist = self.get_wdist(orig_posaddr, orig_boundingvertidx) + \
										self.get_wdist(dest_posaddr, dest_boundingvertidx)
							if orig_boundingvertidx == dest_boundingvertidx:
								vertidx = orig_boundingvertidx
								dist = walking_dists + self.waiting_for_vehicle_equiv_dist + ends_dist
								assert orig_posaddr.plinename == dest_posaddr.plinename
								path = [orig_posaddr, vertidx, dest_posaddr]
								r.append((dist, path))
							else:
								for vert2vert_distnpath in self.pcp_vert2vert_distsnpaths[orig_boundingvertidx][dest_boundingvertidx]:
									vert2vert_dist, vert2vert_path = vert2vert_distnpath
									path = vert2vert_path[:] # Don't want to risk modifying self's data. 
									assert len(path) >= 2
									if not (set(path[:2]) == orig_bounding_vertidxes or set(path[-2:]) == dest_bounding_vertidxes):
										dist = walking_dists + self.waiting_for_vehicle_equiv_dist + vert2vert_dist + ends_dist
										assert path[0] == orig_boundingvertidx and path[-1] == dest_boundingvertidx
										path = [orig_posaddr] + path + [dest_posaddr]
										r.append((dist, path))
		r.sort(key=lambda x: x[0])
		return r

	def pcp_multisnap(self, latlng_, snap_tolerance_):
		assert snap_tolerance_ <= self.pcp_max_snap_radius
		gridsquare = snapgraph.grid.GridSquare.from_latlng(latlng_, self.pcp_gridsquaresys)
		gridsquareidx = gridsquare.idx()
		all_posaddrsndists = self.pcp_multisnap_posaddrndists_by_gridsquareidx[gridsquareidx][:]
		r = [posaddr for posaddr, dist in all_posaddrsndists if dist <= snap_tolerance_]
		return r

	def get_mainline_vertidx(self, stopvertidx_, plinename_):
		assert self.is_stop_vert(stopvertidx_)
		for edge in self.edges[stopvertidx_]:
			for edge2 in self.edges[edge.vertidx]:
				if edge2.plinename == plinename_:
					return edge.vertidx
		raise Exception()

	def get_stop_vertidx(self, vertidx__):
		assert not is_stop_vert(self.verts[vertidx__])
		all_edges_to_stops = [edge for edge in self.edges[vertidx__] if is_stop_vert(self.verts[edge.vertidx])]
		if len(all_edges_to_stops) != 1:
			raise Exception()
		return all_edges_to_stops[0].vertidx

	def get_ways(self, startlatlng_, destlatlng_):
		r = []
		distsnpaths = self.find_paths(startlatlng_, None, destlatlng_, None, snap_tolerance=1000, k=(10,1.55))
		for dist, path in distsnpaths:
			r.append(self.pathsteps_to_way(path))
		return r

	def pathsteps_to_way(self, pathsteps_):
		assert len(pathsteps_) >= 2
		assert all(isinstance(x, snapgraph.PosAddr) for x in [pathsteps_[0], pathsteps_[-1]])
		assert all(isinstance(x, int) for x in pathsteps_[1:-1])
		WDIST_CUTOFF = 300 # We don't want to mention short legs.  Might as well walk. 
		froutesndirs = []
		if self.get_wdist(pathsteps_[0], pathsteps_[1]) > WDIST_CUTOFF:
			froutesndirs.append((get_froute(pathsteps_[0]), self.get_dir(pathsteps_[0], pathsteps_[1])))
		if len(pathsteps_) > 2:
			for vertidx1, vertidx2 in hopscotch(pathsteps_[1:-1]):
				edge = self.edge_by_vertidxes[vertidx1][vertidx2]
				if not snapgraph.has_flag(edge.plinename, 'w') and edge.wdist > WDIST_CUTOFF:
					froutesndirs.append((get_froute(edge), edge.direction))
			if self.get_wdist(pathsteps_[-2], pathsteps_[-1]) > WDIST_CUTOFF:
				froutesndirs.append((get_froute(pathsteps_[-1]), self.get_dir(pathsteps_[-2], pathsteps_[-1])))
		return uniq(froutesndirs)

	def get_dir(self, loc1_, loc2_):
		if isinstance(loc1_, int) and isinstance(loc2_, snapgraph.PosAddr):
			posaddr1 = self.verts[loc1_].get_posaddr(loc2_.plinename)
			posaddr2 = loc2_
			if posaddr2.pals == 0.0:
				posaddr2 = snapgraph.PosAddr(posaddr2.linesegaddr(), posaddr2.pals+0.1)
		elif isinstance(loc1_, snapgraph.PosAddr) and isinstance(loc2_, int):
			posaddr1 = loc1_
			if posaddr1.pals == 0.0:
				posaddr1 = snapgraph.PosAddr(posaddr1.linesegaddr(), posaddr1.pals+0.1)
			posaddr2 = self.verts[loc2_].get_posaddr(loc1_.plinename)
		elif isinstance(loc1_, snapgraph.PosAddr) and isinstance(loc2_, snapgraph.PosAddr):
			posaddr1 = loc1_
			posaddr2 = loc2_
		else:
			raise Exception()
		return (0 if posaddrs_lessthan(posaddr1, posaddr2) else 1)

#	@staticmethod
#	def make_get_connected_vertexndists_callable(sg_, startloc_, destloc_):
#		super_obj = snapgraph.SnapGraph.make_get_connected_vertexndists_callable(sg_, startloc_, destloc_)
#
#		class C(object):
#			
#			def __call__(self, vvert__):
#				max_walking_dist_m = 300
#				walking_weight = 4.0
#				if isinstance(vvert__, geom.LatLng):
#					verts = sg_.multisnap_stop_verts_only(vvert__, max_walking_dist_m)
#					return [(vert, vert.pos().dist_m(vvert__)*walking_weight) for vert in verts]
#				else:
#					assert isinstance(vvert__, snapgraph.Vertex)
#					r = super_obj(vvert__)
#					if vvert__.name.endswith('transfer'):
#						verts = sg_.multisnap_stop_verts_only(vvert__.pos(), max_walking_dist_m)
#						verts = [vert for vert in verts if vert != vvert__]
#						r += [(vert, vert.pos().dist_m(vvert__.pos())*walking_weight) for vert in verts]
#						if isinstance(destloc_, geom.LatLng):
#							dist_vert_to_dest = vvert__.pos().dist_m(destloc_)
#							if dist_vert_to_dest <= max_walking_dist_m:
#								r.append((destloc_, dist_vert_to_dest*walking_weight))
#					return r
#
#		return C()
#
#	def a_star_heuristic(self, loc1_, loc2_):
#		def latlng(x__):
#			if isinstance(x__, geom.LatLng):
#				return x__
#			else:
#				return self.get_latlng(x__)
#
#		return latlng(loc1_).dist_m(latlng(loc2_))*self.min_weight
#
#

def posaddrs_lessthan(posaddr1_, posaddr2_):
	assert posaddr1_.plinename == posaddr2_.plinename
	return (cmp((posaddr1_.ptidx, posaddr1_.pals), (posaddr2_.ptidx, posaddr2_.pals)) < 0)

def get_froute(x_):
	assert isinstance(x_, snapgraph.PosAddr) or isinstance(x_, snapgraph.Edge)
	return snapgraph.get_base_plinename(x_.plinename)

def pack_ways(ways_):
	if not ways_:
		return ([], [])
	else:
		froutendir_to_score = defaultdict(int)
		for wayi, way in enumerate(ways_):
			for froutendir in way:
				froutendir_to_score[froutendir] += len(ways_)-wayi
		all_froutendirs = [x[0] for x in sorted(froutendir_to_score.items(), key=lambda x: x[1], reverse=True)]
		for i in range(len(all_froutendirs)-1, -1, -1):
			froutendir = all_froutendirs[i]
			froutenoppositedir = (froutendir[0], 1 if froutendir[1] == 0 else 0)
			if froutenoppositedir in all_froutendirs[:i]:
				all_froutendirs.pop(i)
		return (ways_[0], all_froutendirs)

def get_packed_ways(orig_latlng_, dest_latlng_):
	r = pack_ways(get_snapgraph().get_ways(orig_latlng_, dest_latlng_))
	return r

# lte = 'less than or equal to'. 
def yen_k_lte(k1_, k2_):
	k1 = snapgraph.get_yen_int_and_float(k1_)
	k2 = snapgraph.get_yen_int_and_float(k2_)
	# None for the int or float means unlimited. 
	def part_lte(k1part__, k2part__):
		return (k2part__ is None) or (k1part__ is not None and k1part__ <= k2part__)
	return part_lte(k1[0], k2[0]) and part_lte(k1[1], k2[1])

def is_stop_vert(vert_):
	return snapgraph.has_flag(vert_.name, 's')

def get_vertname_for_orig_pline(orig_vert_, plinename_):
	return '%s-%s' % (orig_vert_.name, plinename_)

def get_vertname_for_stop(orig_vert_):
	return snapgraph.add_flag('%s-stop' % orig_vert_.name, 's')

def get_orig_pline_to_stop_plinename(orig_vert_, plinename_):
	return snapgraph.add_flag('%s-%s-to-stop' % (orig_vert_.name, plinename_), 'w')

def get_stop_to_orig_pline_plinename(orig_vert_, plinename_):
	return snapgraph.add_flag('%s-stop-to-%s' % (orig_vert_.name, plinename_), 'w')

@lru_cache(1)
@picklestore.decorate
def get_snapgraph():
	froute_to_pline = {froute: routes.routeinfo(froute).routepts(0, c.MAX_DATAZOOM) for froute in routes.FUDGEROUTES}
	for subway_froute in routes.SUBWAY_FUDGEROUTES:
		pline = froute_to_pline.pop(subway_froute)
		subway_froute_weighted_name = snapgraph.set_plinename_weight(subway_froute, 0.6)
		froute_to_pline[subway_froute_weighted_name] = pline

	if USE_CITY_TESTING_SUBSET:
		poly = [geom.LatLng(43.63446004,-79.43870544) , geom.LatLng(43.66228361,-79.44694519) , 
				geom.LatLng(43.67047917,-79.40128326) , geom.LatLng(43.64570281,-79.38591957) ]

		def reduce_plines(plinename2pts__):
			for pline in plinename2pts__.values():
				while len(pline) > 0 and not pline[0].inside_polygon(poly):
					del pline[0]
				while len(pline) > 0 and not pline[-1].inside_polygon(poly):
					del pline[-1]
			for froute in plinename2pts__.keys():
				if len(plinename2pts__[froute]) == 0:
					del plinename2pts__[froute]

		reduce_plines(froute_to_pline)

	r = SystemSnapGraph(froute_to_pline)

	return r

if __name__ == '__main__':

	sg = get_snapgraph()




