#!/usr/bin/python2.6

import copy
from collections import defaultdict, Sequence
from itertools import *
import pprint, math, json, yaml, random
from lru_cache import lru_cache
import geom, grid, mc, c
from misc import *

# Some vocabulary: 
# A Vertex is a vertex in the graph theory sense. 
# A PosAddr represents a location on an edge of the graph.  It is represented in terms of a line segment address and a 
# 	percentage along that line segment. 
# A 'location' has no corresponding class, but is used in some function arguments to describe an object which could be a 
# 	vertex or a posaddr. 
# 
# Abbreviations:
# si = spatial index 


# in meters
DEFAULT_GRAPH_VERTEX_DIST_TOLERANCE = 0.5

# I got this '3' by trial and error.  It's not a precise issue, at least not at my level of understanding.  
# I tried different values for this until I got the results that I wanted. 
PATHS_GPS_ERROR_FACTOR=3

POSADDR_PALS_NUM_DIGITS = 4

# Identifies a point or a line segment within a list of polylines - in particular, within 
# the SnapGraph.plinename2pts field - via a plinename and the index of a point on that pline.
# Whether this identifies a line segment or a point will depend on the context.  
# If it addresses a line segment, then the ptidx field of this class will identify 
# the /first/ point of the line segment (as it appears in the list SnapGraph.plinename2pts[NAME]).  
class PtAddr(object):

	def __init__(self, plinename_, ptidx_):
		self.plinename = plinename_
		self.ptidx = ptidx_

	def __eq__(self, other):
		return (self.plinename == other.plinename) and (self.ptidx == other.ptidx)

	def __hash__(self):
		return hash(self.plinename) + self.ptidx

	def __str__(self):
		return 'PtAddr(%s,%d)' % (self.plinename, self.ptidx)

	def __repr__(self):
		return self.__str__()

	def __cmp__(self, other):
		cmp1 = cmp(self.plinename, other.plinename)
		if cmp1 != 0:
			return cmp1
		else:
			return cmp(self.ptidx, other.ptidx)

	def copy(self):
		return PtAddr(self.plinename, self.ptidx)

class Vertex(object):

	next_namenum = 0

	# Creating a new vertex that will very likely be added to.  
	# Could be seen as mutable. 
	@classmethod
	def create_open(cls_, snapgraph_):
		r = cls_()
		r.name = 'v%d' % cls_.next_namenum
		cls_.next_namenum += 1
		r.snapgraph = snapgraph_
		r.ptaddrs = set() # starts off as a set, but will be a sorted list after this object is completely built. 
		r.is_closed = False
		return r

	@classmethod
	def create_closed(cls_, id_, ptaddrs_, snapgraph_):
		assert isinstance(id_, str) and is_seq_of(ptaddrs_, PtAddr) and isinstance(snapgraph_, SnapGraph)
		r = cls_()
		r.name = id_
		r.snapgraph = snapgraph_
		r.ptaddrs = ptaddrs_
		r.is_closed = False
		r.set_closed()
		return r

	def set_closed(self):
		# We want a vertex to mention each pline that it's a part of only once.
		assert len(self.ptaddrs) == len(set([ptaddr.plinename for ptaddr in self.ptaddrs]))

		self.is_closed = True
		# We want 'ptaddrs' to have a predictable iteration order across different calls in the same program run 
		# so that pos() will return the same thing every time, which is a little bit important for Path.latlngs(). 
		# (Otherwise the polyline that it returns could have some minor but odd things going on around certain corners.) 
		# Also, we want 'ptaddrs' to have a predictable iteration order across different calls in DIFFERENT program runs, 
		# because for my own debugging needs, I want outputs to be 100% reproducible. 
		self.ptaddrs = sorted(self.ptaddrs)

	def pos(self):
		assert self.is_closed
		return self.snapgraph.get_point(self.ptaddrs[0])

	# arg plinename_: None ==> first polyline appearing in this vertex.  Whatever 'first' means.  Arbitrary.  Random.  Any.
	def get_ptaddr(self, plinename_=None):
		if plinename_ is None:
			return self.ptaddrs[0]
		else:
			ptaddrs = [ptaddr for ptaddr in self.ptaddrs if ptaddr.plinename == plinename_]
			if len(ptaddrs) != 1:
				plinenames = [ptaddr.plinename for ptaddr in self.ptaddrs]
				plinename_to_pts = dict((plinename, self.snapgraph.plinename2pts[plinename]) for plinename in plinenames)
				raise Exception('Problem around %s, polyline %d (%s) - %s, %s' \
						% (self, plinename_, ptaddrs, self.ptaddrs, plinename_to_pts))
			return ptaddrs[0]

	def get_posaddr(self, plinename_):
		return PosAddr(self.get_ptaddr(plinename_), 0.0)

	def get_ptidx(self, plinename_):
		return self.get_ptaddr(plinename_).ptidx

	# No need for adjacent points on a single polyline to be included in the vertex.  
	# Here for each group of such adjacent points we remove all but the closest point to the 'vertex mean pos' 
	# from this vertex. 
	def remove_unnecessary_ptaddrs(self):
		assert isinstance(self.ptaddrs, set)
		vertex_mean_pos = geom.latlng_avg([self.snapgraph.get_latlng(ptaddr) for ptaddr in self.ptaddrs])
		assert not self.is_closed
		for plinename in set(ptaddr.plinename for ptaddr in self.ptaddrs):
			ptidxes = [ptaddr.ptidx for ptaddr in self.ptaddrs if ptaddr.plinename == plinename]
			if len(ptidxes) > 1:
				for ptidxgroup in get_maximal_sublists2(ptidxes, lambda ptidx1, ptidx2: abs(ptidx1-ptidx2)==1):
					dist_to_mean_pos = lambda ptidx: self.snapgraph.get_latlng(PtAddr(plinename,ptidx)).dist_m(vertex_mean_pos)
					chosen_ptidx = min(ptidxgroup, key=dist_to_mean_pos)
					self.ptaddrs = set([ptaddr for ptaddr in self.ptaddrs if ptaddr.plinename != plinename or ptaddr.ptidx == chosen_ptidx])

	# Returns any polylines that are mentioned more than once in this vertex. 
	def get_looping_plinenames(self):
		r = set()
		for ptaddr1 in self.ptaddrs:
			if len([ptaddr2 for ptaddr2 in self.ptaddrs if ptaddr2.plinename == ptaddr1.plinename]) > 1:
				r.add(ptaddr1.plinename)
		return r

	def __cmp__(self, other):
		return cmp(self.__class__.__name__, other.__class__.__name__) or cmp(self.name, other.name)

	def __hash__(self):
		return hash(self.name)

	def __eq__(self, other):
		return isinstance(other, Vertex) and (self.name == other.name)

	def __str__(self):
		return 'Vertex(%s)' % (self.name)

	def __repr__(self):
		return self.__str__()

	def strlong(self):
		return 'Vertex(%s, %s, %s)' % (self.name, self.pos(), self.ptaddrs)

	def to_json_dict(self):
		sg = self.snapgraph
		idx = self.idx()
		edges = sg.edges[idx]
		return {'name': self.name, 'idx': idx, 'pos': self.pos(), 
				'ptaddrs': [[addr.plinename, addr.ptidx] for addr in self.ptaddrs], 
				'connectedvertnamesandidxes': [(self.snapgraph.verts[edge.vertidx].name, edge.vertidx) for edge in edges], 
				'connectedvertlatlngs': [self.snapgraph.verts[edge.vertidx].pos() for edge in edges]}

	def get_shortest_common_plinename(self, other_):
		assert isinstance(other_, Vertex) and (self.snapgraph is other_.snapgraph)
		plinenames = set(ptaddr.plinename for ptaddr in self.ptaddrs) & set(ptaddr.plinename for ptaddr in other_.ptaddrs)
		if len(plinenames) == 0:
			return None
		elif len(plinenames) == 1:
			return anyelem(plinenames)
		else:
			def key(plinename__):
				self_ptidx = self.get_ptidx(plinename__)
				other_ptidx = other_.get_ptidx(plinename__)
				return self.snapgraph.get_wdist_between_points(plinename__, self_ptidx, other_ptidx)
			return min(plinenames, key=key)

	def is_on_pline(self, plinename_):
		return len([ptaddr for ptaddr in self.ptaddrs if ptaddr.plinename == plinename_]) > 0

	def get_plinenames(self):
		return sorted([ptaddr.plinename for ptaddr in self.ptaddrs])

	def idx(self):
		return self.snapgraph.vertname_to_idx.get(self.name)

class PosAddr(object):

	def __init__(self, linesegaddr_, pals_):
		assert (isinstance(linesegaddr_, PtAddr) or is_seq_like(linesegaddr_, (0, 0))) and isinstance(pals_, float)
		linesegaddr = (linesegaddr_ if isinstance(linesegaddr_, PtAddr) else PtAddr(linesegaddr_[0], linesegaddr_[1]))
		assert 0.0 <= pals_ <= 1.0
		if pals_ == 1.0: # Normalizing so that self.pals will be between 0.0 and 1.0 inclusive / exclusive.  
			# Saves us from writing code to that effect elsewhere. 
			self.plinename = linesegaddr.plinename
			self.ptidx = linesegaddr.ptidx+1
			self.pals = 0.0
		else:
			self.plinename = linesegaddr.plinename
			self.ptidx = linesegaddr.ptidx
			self.pals = pals_
		assert 0.0 <= self.pals < 1.0
		self.pals = round(self.pals, POSADDR_PALS_NUM_DIGITS)
		if self.pals == 1.0:
			self.pals = 1.0 - 10**-POSADDR_PALS_NUM_DIGITS

	def __str__(self):
		assert 0.0 <= self.pals < 1.0
		return 'PosAddr(\'%s\', %d, %.4f)' % (self.plinename, self.ptidx, self.pals)

	def __hash__(self):
		return hash(self._key())

	def __eq__(self, other):
		return isinstance(other, PosAddr) and (self._key() == other._key())

	def _key(self):
		return (self.plinename, self.ptidx, self.pals)

	def __cmp__(self, other):
		return cmp(self.__class__.__name__, other.__class__.__name__) or cmp(self._key(), other._key())

	def __repr__(self):
		return self.__str__()

	def copy(self):
		return PosAddr(PtAddr(self.plinename, self.ptidx), self.pals)

	def linesegaddr(self):
		return PtAddr(self.plinename, self.ptidx)

# Vocabulary: a Path has one or more 'pieces'.  
# 	A 'piece' is a list of 'steps' (1 or more).  
#		A 'step' is a PosAddr or a Vertex. 
class Path(object):
	
	def __init__(self, piecestepses_, snapgraph_):
		assert isinstance(piecestepses_, Sequence)
		for piecesteps in piecestepses_:
			assert self.is_piece_valid(piecesteps)
		assert isinstance(snapgraph_, SnapGraph)
		for steps1, steps2 in hopscotch(piecestepses_, 2):
			assert steps1[-1] == steps2[0]
		self.piecestepses = piecestepses_
		self.pieces = [None]*len(self.piecestepses)
		self.snapgraph = snapgraph_

	@staticmethod
	def is_piece_valid(steps_):
		if len(steps_) < 1:
			return False
		if not all((isinstance(e, int) or isinstance(e, PosAddr) for e in steps_)):
			return False
		return True

	def latlngs(self, pieceidx_=None):
		allsteps = (sum(self.piecestepses, []) if pieceidx_ is None else self.piecestepses[pieceidx_])
		assert len(allsteps) > 0
		if len(allsteps) == 1:
			return [self.snapgraph.get_latlng(allsteps[0])]
		startposaddr = allsteps[0]; destposaddr = allsteps[-1]
		r = []
		for step1, step2 in hopscotch(allsteps):
			if isinstance(step1, PosAddr):
				r += [self.snapgraph.get_latlng(step1)] 
			if isinstance(step1, PosAddr) and isinstance(step2, int):
				plinename = step1.plinename
				step1_ptidx = step1.ptidx
				vert = self.snapgraph.verts[step2]
				vert_ptidx = vert.get_ptidx(plinename)
				step1_ptidx += (1 if step1_ptidx < vert_ptidx else 0)
				r += sliceii(self.snapgraph.plinename2pts[plinename], step1_ptidx, vert_ptidx)[:-1] + [vert.pos()]
			elif isinstance(step1, int) and isinstance(step2, int):
				vert1 = self.snapgraph.verts[step1]; vert2 = self.snapgraph.verts[step2]
				plinename = vert1.get_shortest_common_plinename(vert2)
				vert1_ptidx = vert1.get_ptidx(plinename)
				vert2_ptidx = vert2.get_ptidx(plinename)
				r += [vert1.pos()] + sliceii(self.snapgraph.plinename2pts[plinename], vert1_ptidx, vert2_ptidx)[1:-1] + [vert2.pos()]
			elif isinstance(step1, int) and isinstance(step2, PosAddr):
				plinename = step2.plinename
				step2_ptidx = step2.ptidx
				vert = self.snapgraph.verts[step1]
				vert_ptidx = vert.get_ptidx(plinename)
				step2_ptidx += (1 if step2_ptidx < vert_ptidx else 0)
				r += [vert.pos()] + sliceii(self.snapgraph.plinename2pts[plinename], vert_ptidx, step2_ptidx)[1:]
			elif isinstance(step1, PosAddr) and isinstance(step2, PosAddr):
				r += self.snapgraph.get_pts_between(step1, step2)
			if isinstance(step2, PosAddr):
				r += [self.snapgraph.get_latlng(step2)] 
		return r

	def plinenames(self, pieceidx_=None):
		allsteps = (sum(self.piecestepses, []) if pieceidx_ is None else self.piecestepses[pieceidx_])
		assert len(allsteps) > 0
		if len(allsteps) == 1:
			return [self.snapgraph.get_latlng(allsteps[0])]
		startposaddr = allsteps[0]; destposaddr = allsteps[-1]
		r = []
		for step1, step2 in hopscotch(allsteps):
			if isinstance(step1, PosAddr) and isinstance(step2, int):
				r.append(step1.plinename)
			elif isinstance(step1, int) and isinstance(step2, int):
				if step1 != step2:
					vert1 = self.snapgraph.verts[step1]; vert2 = self.snapgraph.verts[step2]
					r.append(vert1.get_shortest_common_plinename(vert2))
			elif isinstance(step1, int) and isinstance(step2, PosAddr):
				r.append(step2.plinename)
			elif isinstance(step1, PosAddr) and isinstance(step2, PosAddr):
				if step1 != step2:
					r.append(step1.plinename)
		r = uniq(r)
		return r

	def piece_latlngs(self):
		return [self.latlngs(pieceidx) for pieceidx in xrange(self.num_pieces())]

	def leg_descs(self):
		allsteps = sum(self.piecestepses, [])
		assert len(allsteps) > 0
		startposaddr = allsteps[0]; destposaddr = allsteps[-1]
		r = []
		for step1, step2 in hopscotch(allsteps):
			if isinstance(step1, PosAddr) and isinstance(step2, int):
				plinename = step1.plinename
				step1_ptidx = step1.ptidx
				vert = self.snapgraph.verts[step2]
				vert_ptidx = vert.get_ptidx(plinename)
				direction = (0 if step1_ptidx < vert_ptidx else 1)
			elif isinstance(step1, int) and isinstance(step2, int):
				vert1 = self.snapgraph.verts[step1]; vert2 = self.snapgraph.verts[step2]
				plinename = vert1.get_shortest_common_plinename(vert2)
				vert1_ptidx = vert1.get_ptidx(plinename)
				vert2_ptidx = vert2.get_ptidx(plinename)
				direction = (0 if vert1_ptidx < vert2_ptidx else 1)
			elif isinstance(step1, int) and isinstance(step2, PosAddr):
				plinename = step2.plinename
				step2_ptidx = step2.ptidx
				vert = self.snapgraph.verts[step1]
				vert_ptidx = vert1.get_ptidx(plinename)
				direction = (0 if vert_ptidx <= step2_ptidx else 1)
			elif isinstance(step1, PosAddr) and isinstance(step2, PosAddr):
				plinename = step1.plinename
				if step1.ptidx == step2.ptidx:
					direction = (0 if step1.pals < step2.pals else 1)
				else:
					direction = (0 if step1.ptidx < step2.ptidx else 1)
			else:
				raise Exception()
			if not has_flag(plinename, 'w'):
				r.append((plinename, direction))
		return uniq(r)

	# arg pieceidx_: supports negative indexes. 
	def get_piece(self, pieceidx_):
		r = self.pieces[pieceidx_]
		if r is None:
			r = PathPiece(self, pieceidx_, self.snapgraph)
			self.pieces[pieceidx_] = r
		return r

	def num_pieces(self):
		return len(self.piecestepses)

	def __str__(self):
		return 'Path(%s)' % (self.piecestepses.__str__())

	def __repr__(self):
		return self.__str__()

class PathPiece(object):

	def __init__(self, path_, pieceidx_, parent_sg_):
		assert len(path_.piecestepses[pieceidx_]) > 0
		self.path = path_
		piecesteps = self.path.piecestepses[pieceidx_]
		assert len(piecesteps) >= 2
		if piecesteps[0] == piecesteps[-1]:
			assert len(piecesteps) == 2
			self.is_zero_length = True
			self.zero_length_latlng = path_.latlngs(pieceidx_)[0]
			self.zero_length_heading = self._get_zero_length_heading(pieceidx_, parent_sg_)
		else:
			self.is_zero_length = False
			self.sg = SnapGraph([path_.latlngs(pieceidx_)], forsnaps=False, forpaths=False)

	def _get_zero_length_heading(self, pieceidx_, parent_sg_):
		cur_step = self.path.piecestepses[pieceidx_][0]
		cur_latlng = parent_sg_.get_latlng(cur_step)

		if pieceidx_ >= 1:
			for prev_pieceidx in xrange(pieceidx_-1, -1, -1):
				prev_piecesteps = self.path.piecestepses[prev_pieceidx]
				prev_step = prev_piecesteps[-2]
				if prev_step != cur_step:
					prev_latlng = parent_sg_.get_latlng(prev_step)
					return prev_latlng.heading(cur_latlng)

		# If we're here then we don't have much to go on.  
		# This is a guess, and it will be wrong at least half the time. 
		if isinstance(cur_step, PosAddr):
			linesegaddr = cur_step.linesegaddr()
		else:
			assert isinstance(cur_step, int)
			linesegaddr = parent_sg_.verts[cur_step].get_ptaddr()
		return parent_sg_.heading(linesegaddr, False)

	def length_m(self):
		if self.is_zero_length:
			return 0.0
		else:
			return self.sg.get_pline_len('0')

	# arg mapl_: should be a float between 0.0 and self.length_m() inclusive, or the string 'max'. 
	def mapl_to_latlngnheading(self, mapl_):
		if mapl_ == 'max':
			mapl = self.length_m()
		else:
			mapl = mapl_
		if self.is_zero_length:
			if mapl != 0.0:
				raise Exception()
			return (self.zero_length_latlng, self.zero_length_heading)
		else:
			return self.sg.mapl_to_latlngnheading('0', mapl)

class Edge(object):

	def __init__(self, vertidx_, wdist_, plinename_, direction_):
		assert isinstance(vertidx_, int) and isinstance(wdist_, float) and isinstance(plinename_, str)
		assert direction_ in (0, 1)
		self.vertidx = vertidx_
		self.wdist = wdist_
		self.plinename = plinename_
		self.direction = direction_

	def copy(self):
		return Edge(self.vertidx, self.wdist, self.plinename, self.direction)

	def __str__(self):
		return 'Edge(%d, %.1f, %s, %s)' % (self.vertidx, self.wdist, self.plinename, self.direction)

	def __repr__(self):
		return self.__str__()

# This can be pickled or memcached. 
class SnapGraph(object):

	# arg polylines_: We might modify this, if 'forpaths' is true.  We might split some line segments, where they 
	# 	intersect other line segments.  We will not join polylines or remove any points. 
	# arg forpaths_disttolerance: Two points need to be less than this far apart for us to consider them 
	# 	coincident AKA the same point, for our path-graph purposes. 
	def __init__(self, plines_, forsnaps=True, forpaths=True, 
				forpaths_disttolerance=DEFAULT_GRAPH_VERTEX_DIST_TOLERANCE, 
				remove_crowded_vertexes=True, vertex_limit_zones_filename=None, 
				name=None):
		self.name = name
		self.init_plines(plines_)
		if forsnaps:
			self.build_spatial_index()
		if forpaths:
			self.plinename2pts = {plinename: pts for plinename, pts in self.plinename2pts.iteritems() if \
					geom.dist_m_polyline(pts) > forpaths_disttolerance}
			self.init_path_structures(forpaths_disttolerance, remove_crowded_vertexes, vertex_limit_zones_filename)
			self.build_spatial_index() # rebuilding it because for those 
				# linesegs that were split within init_path_structures() - 
				# say lineseg A was split into A1 and A2, and A covered the sets of 
				# gridsquares S.  after init_path_structures() is done, 
				# self.si_linesegaddrs_by_gridsquareidx will be such that A1 is portrayed as 
				# covering all of S, and so does A2.  This is of course too wide a net 
				# in many cases - I think if the original start point, the original end 
				# point, and the split point, are in 3 different gridsquares.  
				# init_path_structures() does this because the code is easier to write.  
				# But at this point we can make the spatial index better by rebuilding it. 
		else:
			# We want to build this even if 'forpaths' is false, because get_mapl() 
			# depends on it, and we want get_mapl() to be available even if 
			# 'forpaths' is false.  If 'forpaths' is true, then this is built at a 
			# sensitive time, elsewhere (after the intersections of line segments are 
			# found and the line segments split appropriately, but before the 
			# distance-between-vertexes info is built.)
			self.init_plinename_to_ptidx_to_mapl()
		self.use_floyd_warshall = False
		self.use_vert_only_floyd_warshall = False

	def init_plines(self, plines_):
		self.init_plinename2pts(plines_)

	def init_plinename2pts(self, plines_):
		def to_latlng(pt__):
			return pt__ if isinstance(pt__, geom.LatLng) else geom.LatLng(pt__)
		def to_latlngs(pts__):
			return [to_latlng(pt) for pt in pts__]
		if isinstance(plines_, Sequence):
			for pline in plines_:
				assert all(isinstance(e, geom.LatLng) or is_seq_like(e, (0.0, 0.0)) for e in pline)
			self.plinename2pts = dict((str(i), to_latlngs(pts)) for i, pts in enumerate(plines_))
		else:
			if __debug__:
				assert isinstance(plines_, dict)
				for key in plines_.keys():
					assert isinstance(key, str)
				for value in plines_.values():
					assert isinstance(value, Sequence)
					for e in value:
						assert isinstance(e, geom.LatLng) or is_seq_like(e, (0.0, 0.0))
			self.plinename2pts = {plinename: to_latlngs(pts) for plinename, pts in plines_.iteritems()}
	
	def __str__(self):
		return 'SnapGraph(%s)' % (self.name if self.name is not None else id(self))

	# This is used in lru_cache keys so it's important that we implement it right.  
	def __hash__(self):
		if self.name is None:
			raise Exception()
		return hash(self.name)

	# return list of (dist, pathsteps) pairs.  Dist is a float, in meters.   List is sorted in ascending order of dist. 
	@lru_cache(maxsize=60000, cacheable=lambda args, kwds: kwds.get('out_visited_vertexes') is None)
	def find_paths(self, startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance=c.GRAPH_SNAP_RADIUS, \
			k=None, out_visited_vertexes=None):
		if out_visited_vertexes is not None:
			return self.find_paths_impl(startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance_=snap_tolerance, 
					k_=k, out_visited_vertexes=out_visited_vertexes)
		else:
			# We could almost decorate this function with mc.decorate instead of calling mc.get() ourselves, 
			# but that won't quite work, because we can't store anything with a reference to a SnapGraph object in memcache, 
			# because they're large.  Vertexes have those.  So we will nullify those references before the result is put 
			# into memcache, and un-nullify them before we return from this function.
			# It probably wouldn't be that hard to make Vertex not have a reference to it's owner snapgraph.  Maybe later.

			def locs_arg_to_str(locs_arg__):
				if locs_arg__ in ('1', 'm'):
					return locs_arg__
				else:
					return str(locs_arg__)

			def set_sg_of_vertexes(r__, sg__):
				for dist, pathsteps in r__:
					for pathstep in pathsteps:
						if isinstance(pathstep, Vertex):
							pathstep.snapgraph = sg__

			assert self.name is not None
			def find_paths_and_nullify_vertex_sgs(sgname__, startlatlng__, startlocsstr__, startlocs__, 
					destlatlng__, destlocsstr__, destlocs__, snap_tolerance__, k__):
				r = self.find_paths_impl(startlatlng__, startlocs__, destlatlng__, destlocs__, snap_tolerance__, k__)
				set_sg_of_vertexes(r, None)
				return r
			r = mc.get(find_paths_and_nullify_vertex_sgs, [self.name, startlatlng_, locs_arg_to_str(startlocs_), startlocs_, 
					destlatlng_, locs_arg_to_str(destlocs_), destlocs_, snap_tolerance, k], 
					{}, posargkeymask=[1,1,1,0,1,1,0,1,1])
			set_sg_of_vertexes(r, self)
			return r

	def find_paths_impl(self, startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance_, 
			k_, out_visited_vertexes=None):
		assert (snap_tolerance_ > 0) and is_yen_k_valid(k_)

		def get_locs_from_arg(locs_arg__, latlng__):
			assert isinstance(latlng__, geom.LatLng) or latlng__ is None
			if locs_arg__ == '1':
				r = self.snap_for_find_paths(latlng__, snap_tolerance_)
				r = ([r] if r is not None else [])
			elif locs_arg__ == 'm':
				r = self.multisnap_for_find_paths(latlng__, snap_tolerance_)
			elif isinstance(locs_arg__, Sequence):
				r = locs_arg__
			elif isinstance(locs_arg__, Vertex) or isinstance(locs_arg__, PosAddr):
				r = [locs_arg__]
			else:
				raise Exception('locs arg "%s" (type %s) is unacceptable' % (locs_arg__, type(locs_arg__)))
			return [(e if isinstance(e, PosAddr) else e.idx()) for e in r]

		start_locs = get_locs_from_arg(startlocs_, startlatlng_)
		dest_locs = get_locs_from_arg(destlocs_, destlatlng_)
		if not(start_locs and dest_locs):
			return []
		else:
			r_dists_n_paths = []
			yen_k_firstpass = get_yen_k_firstpass(k_)
			for start_loc, dest_loc in product(start_locs, dest_locs):
				start_latlng_to_loc_dist = self.get_snap_error_fudge_dist_for_find_paths(startlatlng_, start_loc)
				dest_latlng_to_loc_dist = self.get_snap_error_fudge_dist_for_find_paths(destlatlng_, dest_loc)
				distnpaths = self.find_paths_by_locs(start_loc, dest_loc, k=yen_k_firstpass, 
						out_visited_vertexes=out_visited_vertexes)
				if k_ in (1, None):
					distnpaths = [distnpaths]
				for dist, path in distnpaths:
					if dist is not None:
						dist += start_latlng_to_loc_dist + dest_latlng_to_loc_dist
						r_dists_n_paths.append((dist, path))
			r_dists_n_paths.sort(key=lambda e: e[0])
			yen_reduce_list_according_to_k(r_dists_n_paths, k_)
			for path in (e[1] for e in r_dists_n_paths):
				assert len(path) >= 2
			return r_dists_n_paths

	def snap_for_find_paths(self, latlng_, snap_tolerance_):
		return self.snap(latlng_, snap_tolerance_)

	def multisnap_for_find_paths(self, latlng_, snap_tolerance_):
		return self.multisnap(latlng_, snap_tolerance_)

	def get_snap_error_fudge_dist_for_find_paths(self, latlng_, loc_):
		if latlng_ is None:
			return 0.0
		else:
			# Multiplying these by a certain factor because otherwise some strange choices will be made for shortest path 
			# when going around corners.  I don't know how to explain this in comments, without pictures. 
			return self.get_latlng(loc_).dist_m(latlng_)*PATHS_GPS_ERROR_FACTOR

	# return a Path, or None if no path is possible.
	def find_multipath(self, latlngs_, vid_, locses=None, snap_tolerance=c.GRAPH_SNAP_RADIUS, log_=False):
		return self.find_multipath_impl(tuple(latlngs_), vid_, locses=tuple(locses), snap_tolerance=snap_tolerance, log_=log_)

	# It's important for performance that this is large enough that it will cache everything for a route between 
	# generating reports one minute and the next.  This 600 is based on 50 per fudgeroutes times 12 fudgeroutes.  
	# If the number of fudgeroutes that we're calculating increases, so should this. 
	@lru_cache(600) 
	def find_multipath_impl(self, latlngs_, vid_, locses=None, snap_tolerance=c.GRAPH_SNAP_RADIUS, log_=False):
		if len(latlngs_) < 2:
			raise Exception()
		our_locses = ([self.multisnap(latlng, snap_tolerance) for latlng in latlngs_] if locses is None else locses)
		assert len(our_locses) == len(latlngs_)
		if len(latlngs_) == 2:
			dists_n_pieces = self.find_paths(latlngs_[0], our_locses[0], latlngs_[1], our_locses[1], snap_tolerance=snap_tolerance)
			if len(dists_n_pieces) > 0:
				return Path([dists_n_pieces[0][1]], self)
			else:
				return None
		else:
			r_dist = 0
			r_pieces = []
			n = len(latlngs_)
			i_startnendloc_to_distnpiece = []
			for (latlng1, locses1), (latlng2, locses2) in hopscotch(zip(latlngs_, our_locses), 2):
				i_startnendloc_to_distnpiece.append({})
				for dist, path in self.find_paths(latlng1, locses1, latlng2, locses2, snap_tolerance=snap_tolerance):
					startnendloc = (path[0], path[-1])
					i_startnendloc_to_distnpiece[-1][startnendloc] = (dist, path)
			assert len(i_startnendloc_to_distnpiece) == n-1
			for idx_a, idx_b, idx_c in hopscotch(range(n), 3):
				if idx_a == 0:
					combo_args = our_locses[idx_a:idx_c+1]
				else:
					combo_args = ((r_pieces[-1][-1],),) + our_locses[idx_b:idx_c+1]
				relative_i_startnendloc_to_distnpiece = i_startnendloc_to_distnpiece[idx_a:idx_a+len(combo_args)]
				chosen_dists_n_pieces = self.find_multipath_single_step(combo_args, relative_i_startnendloc_to_distnpiece, 
						snap_tolerance, idx_a, vid_, log_=log_)
				if chosen_dists_n_pieces is None:
					r_pieces = None
					break
				chosen_dist_n_piece_ab = chosen_dists_n_pieces[0]
				r_dist += chosen_dist_n_piece_ab[0]
				r_pieces.append(chosen_dist_n_piece_ab[1])
				if idx_c == n-1:
					chosen_dist_n_piece_bc = chosen_dists_n_pieces[1]
					r_dist += chosen_dist_n_piece_bc[0]
					r_pieces.append(chosen_dist_n_piece_bc[1])
			r_pieces = self.fix_gps_artifact_path_doublebacks(r_pieces, snap_tolerance, vid_, log_)
			return (Path(r_pieces, self) if r_pieces is not None else None)

	# It's important for performance that this is large enough that it will cache everything for a route between 
	# generating reports one minute and the next.  This 6000 is based on 500 per fudgeroutes times 12 fudgeroutes.  
	# If the number of fudgeroutes that we're calculating increases, so should this. 
	@lru_cache(6000, posargkeymask=[1,1,0,1,0,1])
	def find_multipath_single_step(self, combo_args_, relative_i_startnendloc_to_distnpiece_, 
			snap_tolerance_, log_idx_a_, log_vid_, log_=False):
		combined_dists_n_pieces = []
		for loc_combo in product(*combo_args_):
			cur_dists_n_pieces = []
			for i, (loc1, loc2) in enumerate(hopscotch(loc_combo, 2)):
				locs = tuple(e.idx() if isinstance(e, Vertex) else e for e in (loc1, loc2))
				dist_n_path = relative_i_startnendloc_to_distnpiece_[i][locs]
				cur_dists_n_pieces.append(dist_n_path)
			combined_dists_n_pieces.append(cur_dists_n_pieces)
		if len(combined_dists_n_pieces) == 0:
			if log_:
				printerr('Multipath is not possible.  (snapgraph: "%s").  idx_a=[%d] %s' \
						% (self.name, log_idx_a_, combo_args_))
			return None # No path possible for this part.  No path is possible at all. 
		combined_dists_n_pieces.sort(key=lambda e: self.get_combined_cost(e, snap_tolerance_))
		if log_:
			printerr('find_multipath: combined dists/pieces for idx_a=%d, sorted:' % (log_idx_a_))
			for i, ((dist_ab, pieces_ab), (dist_bc, pieces_bc)) in enumerate(combined_dists_n_pieces):
				printerr('[{}] a->b dist={:8.3f} {}'.format(i, dist_ab, pieces_ab))
				printerr('[{}] b->c dist={:8.3f} {}'.format(i, dist_bc, pieces_bc))
		chosen_dists_n_pieces = combined_dists_n_pieces[0]
		return chosen_dists_n_pieces

	def fix_gps_artifact_path_doublebacks(self, pieces_, snap_tolerance_, vid_, log_):
		if not pieces_:
			return pieces_
		# I think that this code assumes that plines don't intersect themselves. 
		def is_doubleback(steps__):
			if steps__[0] != steps__[-1] or not isinstance(steps__[0], int):
				return False
			plinenames = Path([steps__], self).plinenames()
			if len(plinenames) < 2:
				return False
			for i in xrange(len(plinenames)/2):
				if plinenames[i] != plinenames[len(plinenames)-1-i]:
					return False
			return True
		allsteps = uniq(sum(pieces_, []))
		left_idx = 0
		while left_idx < len(allsteps)-2:
			for right_idx in xrange(left_idx+2, len(allsteps)):
				#if allsteps[left_idx] == allsteps[right_idx]:
				if is_doubleback(allsteps[left_idx:right_idx+1]):
					left_latlng = self.get_latlng(allsteps[left_idx])
					max_dist = max(left_latlng.dist_m(self.get_latlng(allsteps[between_idx])) \
							for between_idx in xrange(left_idx+1, right_idx))
					if max_dist < snap_tolerance_:
						new_reality_loc = allsteps[left_idx]
						for i in xrange(left_idx+1, right_idx+1):
							allsteps[i] = new_reality_loc
					left_idx = right_idx-1
					break
			left_idx += 1
		r = []
		cur_piece_startidx_in_allsteps = 0
		for orig_piece in pieces_:
			if len(set(orig_piece)) == 1:
				new_piece = [allsteps[cur_piece_startidx_in_allsteps]]*2
			else:
				new_piece = allsteps[cur_piece_startidx_in_allsteps:cur_piece_startidx_in_allsteps+len(orig_piece)]
				cur_piece_startidx_in_allsteps += len(orig_piece) - 1
			new_piece = uniq(new_piece)
			if len(new_piece) == 1:
				new_piece *= 2
			r.append(new_piece)
		return r

	def get_combined_cost(self, dists_n_pieces_, snap_tolerance_):
		r = sum(e[0] for e in dists_n_pieces_)
		for distnpiece1, distnpiece2 in hopscotch(dists_n_pieces_):
			r += self.get_doubleback_cost_if_any(distnpiece1, distnpiece2, snap_tolerance_)
		return r

	# Trying to strongly discourage choosing of a path that doubles back.  Can't 
	# add something silly like 9999999 because I suspect that every now and then, 
	# a vehicle will double back.  (At least it will appear to, on for example 
	# our simplified graph of streetcar tracks.)   The only reason that a 
	# doublebacking path would be incorrectly chosen is because our use of 
	# PATHS_GPS_ERROR_FACTOR sometimes causes us to choose a loc that is close to 
	# the sample latlng and suggests a doubleback over a loc that is a 
	# little farther from the sample latlng and does not suggest a doubleback.  
	# So this code fudges for that.  I don't know how to describe the thinking 
	# without pictures.
	def get_doubleback_cost_if_any(self, distnpiece1_, distnpiece2_, snap_tolerance_):
		assert Path.is_piece_valid(distnpiece1_[1]) and Path.is_piece_valid(distnpiece2_[1])
		doubleback_steps = get_common_prefix(distnpiece1_[1][::-1], distnpiece2_[1])
		doubleback_dist = self.get_wlength_of_pathpiece(doubleback_steps)
		if doubleback_dist > 0:
			return 2000.0 # I made this up. 
		else:
			return 0.0

	def get_wlength_of_pathpiece(self, piecesteps_):
		r = 0.0
		for step1, step2 in hopscotch(piecesteps_):
			r += self.get_wdist(step1, step2)
		return r

	def get_pts_between(self, posaddr1_, posaddr2_):
		assert posaddr1_.plinename == posaddr2_.plinename
		plinename = posaddr1_.plinename
		pos1_ptidx = posaddr1_.ptidx
		pos2_ptidx = posaddr2_.ptidx
		if pos1_ptidx == pos2_ptidx:
			return []
		elif pos1_ptidx < pos2_ptidx:
			return self.plinename2pts[plinename][pos1_ptidx+1:pos2_ptidx+1]
		else:
			return sliceii(self.plinename2pts[plinename], pos1_ptidx, pos2_ptidx+1)

	# return a list of Vertex, length 0, 1, or 2.  
	# If returned list has length of 2: first elem will be the index of the 'low' vertex (by point index on the polyline), 
	# 	second elem will be the index of the 'high' vertex. 
	# If always_return_both_ is True: then the returned list will always have a length of 2, and one or both 
	#		elements might be None. 
	# 
	# If posaddr_ has a pals of 0.0 and it is right on top of a vertex, then we will act like the pals is eg. 0.00001, 
	# and return the bounding vertidxes for that.  This makes some code elsewhere easier to write. 
	def get_bounding_vertidxes(self, posaddr_, always_return_both_=False):
		assert isinstance(posaddr_, PosAddr)
		ptaddr = posaddr_.linesegaddr()
		ptidxes_with_a_vert = self.plinename_to_ptidx_to_vertidx.get(ptaddr.plinename, {}).keys()
		if len(ptidxes_with_a_vert) == 0:
			return ([None, None] if always_return_both_ else [])
		else:
			lo_vert_ptidx = max2(ptidx for ptidx in ptidxes_with_a_vert if ptidx <= ptaddr.ptidx)
			hi_vert_ptidx = min2(ptidx for ptidx in ptidxes_with_a_vert if ptidx > ptaddr.ptidx)
			lo_vertidx = self.plinename_to_ptidx_to_vertidx[ptaddr.plinename].get(lo_vert_ptidx, None)
			hi_vertidx = self.plinename_to_ptidx_to_vertidx[ptaddr.plinename].get(hi_vert_ptidx, None)
			if always_return_both_:
				return [lo_vertidx, hi_vertidx]
			else:
				return [v for v in [lo_vertidx, hi_vertidx] if v is not None]

	def get_bounding_verts(self, posaddr_, always_return_both_=False):
		idxes = self.get_bounding_vertidxes(posaddr_, always_return_both_)
		return [(self.verts[idx] if idx is not None else None) for idx in idxes]

	def get_verts_bounding_vertexes(self, vert_, plinename_):
		assert vert_ in self.verts and plinename_ in self.plinename2pts
		assert vert_.is_on_pline(plinename_)
		edges = self.edges[vert_.idx()]
		return [self.verts[edge.vertidx] for edge in edges if edge.plinename == plinename_]

	def get_latlng(self, loc_):
		if isinstance(loc_, PtAddr):
			return self.get_point(loc_)
		elif isinstance(loc_, PosAddr):
			assert loc_.pals < 1.0 # i.e. has been normalized.  Probably not a big deal.   
			if loc_.pals == 0.0:
				return self.get_point(loc_.linesegaddr())
			else:
				pt1 = self.get_point(loc_.linesegaddr())
				pt2 = self.get_point(PtAddr(loc_.plinename, loc_.ptidx+1))
				return pt1.avg(pt2, loc_.pals)
		elif isinstance(loc_, int):
			return self.verts[loc_].pos()
		elif isinstance(loc_, Vertex):
			return loc_.pos()
		else:
			raise Exception('loc arg is instance of %s' % loc_.__class__.__name__)

	def get_latlngs(self, locs_):
		return [self.get_latlng(loc) for loc in locs_]

	def get_mapl(self, posaddr_):
		r = self.plinename_to_ptidx_to_mapl[posaddr_.plinename][posaddr_.ptidx]
		r += self.get_dist_to_reference_point(posaddr_)
		return r

	def get_dist_to_reference_point(self, posaddr_):
		if posaddr_.pals == 0.0:
			return 0.0
		else:
			ptidx_to_mapl = self.plinename_to_ptidx_to_mapl[posaddr_.plinename]
			ptidx = posaddr_.ptidx
			dist_between_bounding_pts = ptidx_to_mapl[ptidx+1] - ptidx_to_mapl[ptidx]
			return dist_between_bounding_pts*posaddr_.pals

	# Returns shortest path (or paths (plural) if k != 1)
	# each path as a (dist, pathsteps) (i.e. (float, list<PosAddr|int>)) pair.   If no path is possible, 
	# then both dist and path will be None. 
	# We pass a fancy 'get connected vertexes' function to dijkstra, to support path finding from somewhere along an edge 
	# (which dijkstra doesn't do) by pretending like we've inserted a temporary vertex at the start and dest positions. 
	# In the code below, 'vvert' is short for 'virtual vertex' which is a term I made up for this function, 
	# to describe something that is a vertex in the graph theory sense and from the dijkstra function's perspective, 
	# but is not necessarily one of our Vertex objects.  A virtual vertex could be a Vertex, or it could be a PosAddr. 
	def find_paths_by_locs(self, startloc_, destloc_, k=None, out_visited_vertexes=None, log=False):
		assert self.isloc(startloc_) and self.isloc(destloc_) and is_yen_k_simple(k)

		if startloc_ == destloc_:
			return (0.0, [startloc_, destloc_])
		else:
			def heuristic(loc1__, loc2__):
				return self.a_star_heuristic(loc1__, loc2__)
			all_vverts = self.verts + [loc for loc in (startloc_, destloc_) if isinstance(loc, PosAddr)]
			get_connected_vertexndists = self.make_get_connected_vertexndists_callable(self, startloc_, destloc_)
			r = a_star(startloc_, destloc_, all_vverts, get_connected_vertexndists, heuristic, 
					k=k, out_visited_vertexes=out_visited_vertexes, log=log)

			return r

	def single_source_dijkstra(self, startvert_, destverts_=None):
		assert isinstance(startvert_, Vertex) and (destverts_ is None or is_seq_of(destverts_, Vertex))
		all_verts = self.verts
		get_connected_vertexndists = self.make_get_connected_vertexndists_callable(self, None, None)
		return dijkstra(startvert_, destverts_, all_verts, get_connected_vertexndists)
		

	# The word 'heuristic' might sound forgiving, but A* puts a strict requirement on this one: 
	# that it not overestimate the length of the path between two vertexes i.e. 
	# this can return a length less than the shortest path, but it better not return a length greater than 
	# it or else the algorithm will silently fail, returning a non-optimal path. 
	# See http://en.wikipedia.org/wiki/File:Weighted_A_star_with_eps_5.gif 
	def a_star_heuristic(self, loc1_, loc2_):
		if self.use_vert_only_floyd_warshall:
			return self.vert_only_floyd_warshall_heuristic(loc1_, loc2_)
		elif self.use_floyd_warshall:
			return self.floyd_warshall_heuristic(loc1_, loc2_)
		else:
			# This one can give bad results when the distance tolerance that we built the graph 
			# with is significant eg. system graph, intersection of spadina / bloor subway / uni subway. 
			return self.get_latlng(loc1_).dist_m(self.get_latlng(loc2_))*self.min_weight

	def vert_only_floyd_warshall_heuristic(self, loc1_, loc2_):
		return self.floyd_warshall_data[loc1_][loc2_]

	def floyd_warshall_heuristic(self, loc1_, loc2_):
		if isinstance(loc1_, int) and isinstance(loc2_, int):
			return self.floyd_warshall_data[loc1_][loc2_]
		elif isinstance(loc1_, int) and isinstance(loc2_, PosAddr):
			return min(self.floyd_warshall_data[loc1_][vertidx] for vertidx in self.get_bounding_vertidxes(loc2_))
		elif isinstance(loc1_, PosAddr) and isinstance(loc2_, int):
			return min(self.floyd_warshall_data[vertidx][loc2_] for vertidx in self.get_bounding_vertidxes(loc1_))
		elif isinstance(loc1_, PosAddr) and isinstance(loc2_, PosAddr):
			vertidx_combos = product(self.get_bounding_vertidxes(loc1_), self.get_bounding_vertidxes(loc2_))
			return min(self.floyd_warshall_data[orig_vertidx][dest_vertidx] for orig_vertidx, dest_vertidx in vertidx_combos)

	def init_floyd_warshall_data(self):
		self.floyd_warshall_data = self.floyd_warshall()

	@staticmethod
	def make_get_connected_vertexndists_callable(sg_, startloc_, destloc_):

		if isinstance(startloc_, int) and isinstance(destloc_, int):
			class D(object):
				def __call__(self, vertidx__):
					return [(edge.vertidx, edge.wdist) for edge in sg_.edges[vertidx__]]

			return D()

		class C(object):

			def __init__(self):
				self.startispos = isinstance(startloc_, PosAddr)
				self.destispos = isinstance(destloc_, PosAddr)
				self.startpos_bounding_vertidxes = (sg_.get_bounding_vertidxes(startloc_, True) if self.startispos else [])
				self.destpos_bounding_vertidxes = (sg_.get_bounding_vertidxes(destloc_, True) if self.destispos else [])
				self.shared_bounding_vertidxes = set(self.startpos_bounding_vertidxes) & set(self.destpos_bounding_vertidxes)

			def __call__(self, vvert__):
				if (len(self.shared_bounding_vertidxes) == 2) and (startloc_.plinename == destloc_.plinename):
					startpos_is_lo = (cmp(startloc_, destloc_) < 0)
					if vvert__ in (startloc_, destloc_): # going to return one vert and one posaddr.
						vertidx = self.startpos_bounding_vertidxes[not ((startpos_is_lo) ^ (vvert__ == destloc_))]
						thisposaddr, otherposaddr = (startloc_, destloc_)[::-1 if vvert__ == destloc_ else 1]
						r = ([(vertidx, sg_.get_wdist(thisposaddr, vertidx))] if vertidx is not None else [])
						r += [(otherposaddr, sg_.get_wdist_between_posaddrs(thisposaddr, otherposaddr))]
					else:
						assert isinstance(vvert__, int)
						r = [(edge.vertidx, edge.wdist) for edge in sg_.edges[vvert__]]
						if vvert__ in self.startpos_bounding_vertidxes:
							r = [(v,d) for v,d in r if v not in self.shared_bounding_vertidxes]
							posaddr = (startloc_, destloc_)[(startpos_is_lo) ^ (vvert__ == self.startpos_bounding_vertidxes[0])]
							r += [(posaddr, sg_.get_wdist(posaddr, vvert__))]
				else:
					def default():
						return [(edge.vertidx, edge.wdist) for edge in sg_.edges[vvert__]]
					if vvert__ == startloc_:	
						if not self.startispos:
							r = default()
							if self.destispos and startloc_ in self.destpos_bounding_vertidxes:
								r = [(v,d) for v,d in r if v not in self.destpos_bounding_vertidxes] + [(destloc_,sg_.get_wdist(startloc_,destloc_))]
						else:
							r = [(vert,sg_.get_wdist(startloc_, vert)) for vert in self.startpos_bounding_vertidxes if vert is not None]
					elif vvert__ == destloc_:
						if not self.destispos:
							r = default()
							if self.startispos and destloc_ in self.startpos_bounding_vertidxes:
								r = [(v,d) for v,d in r if v not in self.startpos_bounding_vertidxes] + [(startloc_,sg_.get_wdist(startloc_,destloc_))]
						else:
							r = [(vert,sg_.get_wdist(destloc_, vert)) for vert in self.destpos_bounding_vertidxes if vert is not None]
					else:
						assert isinstance(vvert__, int)
						r = default()
						if (len(self.shared_bounding_vertidxes) == 1) and (vvert__ == anyelem(self.shared_bounding_vertidxes)):
							r = [(v,d) for v,d in r if v not in self.startpos_bounding_vertidxes + self.destpos_bounding_vertidxes]
							r += [(posaddr, sg_.get_wdist(posaddr, vvert__)) for posaddr in (startloc_, destloc_)]
						elif vvert__ in self.startpos_bounding_vertidxes:
							r = [(v,d) for v,d in r if v not in self.startpos_bounding_vertidxes] + [(startloc_,sg_.get_wdist(startloc_, vvert__))]
							if len(self.shared_bounding_vertidxes) == 2: # but note that the start pos and dest pos are not on the same polyline, 
									# otherwise we wouldn't be here. 
								assert set(self.startpos_bounding_vertidxes) == set(self.destpos_bounding_vertidxes)
								r += [(destloc_,sg_.get_wdist(destloc_, vvert__))]
						elif vvert__ in self.destpos_bounding_vertidxes:
							r = [(v,d) for v,d in r if v not in self.destpos_bounding_vertidxes] + [(destloc_,sg_.get_wdist(destloc_, vvert__))]
							# if len(self.shared_bounding_vertidxes) == 2, then that is caught 3 lines above this one.
				return r

		return C()

	def floyd_warshall(self):
		log = True

		verts = self.verts
		numverts = len(verts)
		r = [[float('inf')]*numverts for i in range(numverts)]

		for vertidx in range(len(verts)):
			r[vertidx][vertidx] = 0.0
			for edge in self.edges[vertidx]:
				r[vertidx][edge.vertidx] = edge.wdist

		if log:
			t0 = time.time()
		for k in xrange(numverts):
			for i in xrange(numverts):
				for j in xrange(numverts):
					if r[i][j] > r[i][k] + r[k][j]:
						r[i][j] = r[i][k] + r[k][j]
			if log:
				print_est_time_remaining('Floyd-Warshall', t0, k, numverts, 30)

		return r

	def rename_vert(self, vert_, new_name_):
		assert isinstance(vert_, Vertex)
		vertidx = self.vertname_to_idx[vert_.name]
		del self.vertname_to_idx[vert_.name]
		self.vertname_to_idx[new_name_] = vertidx
		vert_.name = new_name_

	@staticmethod
	def isloc(obj_):
		return isinstance(obj_, int) or isinstance(obj_, PosAddr)

	# returns None if that vertex name does not exist.
	def get_vertex(self, name_):
		idx = self.vertname_to_idx.get(name_)
		return (self.verts[idx] if idx is not None else None)

	def init_path_structures(self, disttolerance_, remove_crowded_vertexes_, vertex_limit_zones_filename_):
		self.paths_disttolerance = disttolerance_

		# These data structures will be built twice: once before and once after removing the island plines. 
		# We do it the first time (before) because in order to figure out which plines are part of those 
		# undesirable islands, we need these data structures.  
		# We do it the second time (after) because the act of removing plines 
		# might remove some vertexes, and so it invalidates the data structures.  
		# It would be possible to massage the data structures to deal with this, but that would require writing 
		# some bug-prone code.  I'd rather wait for it to build twice than write that code. 
		self.init_path_structures_business(remove_crowded_vertexes_, vertex_limit_zones_filename_)

		self.remove_island_plines()

		# This is the second time.  For good this time. 
		self.init_path_structures_business(remove_crowded_vertexes_, vertex_limit_zones_filename_)

		assert len(self.get_island_plinenames()) == 0

	def init_path_structures_business(self, remove_crowded_vertexes_, vertex_limit_zones_filename_):
		self.init_weights()
		self.init_plinename_to_ptidx_to_vertidx(remove_crowded_vertexes_, vertex_limit_zones_filename_)
		self.init_plinename_to_ptidx_to_mapl()
		self.init_edges()
		self.vertname_to_idx = {vert.name: idx for idx, vert in enumerate(self.verts)}

	def init_weights(self):
		self.plinename_to_weight = {} # Only plines w/ weight != 1.0 will be present in this dict. 
		for plinename in self.plinename2pts.iterkeys():
			weight = get_weight_from_plinename(plinename)
			if weight != 1.0:
				self.plinename_to_weight[plinename] = weight
		self.min_weight = (min(self.plinename_to_weight.itervalues()) if len(self.plinename_to_weight) else 1.0)

	def get_pline_weight(self, plinename_):
		return self.plinename_to_weight.get(plinename_, 1.0)

	def remove_island_plines(self):
		island_plinenames = self.get_island_plinenames()
		self.plinename2pts = {k: v for k, v in self.plinename2pts.iteritems() if k not in island_plinenames}
		
	def get_island_plinenames(self):
		# Any plines w/ no vertexes are islands, so first get those: 
		r = set([plinename for plinename, ptidx_to_vertidx in self.plinename_to_ptidx_to_vertidx.iteritems() if len(ptidx_to_vertidx) == 0])
		# Also check all vertexes connectivity to each other in a graph theory type of way. 
		# Thanks to http://stackoverflow.com/questions/15394254/graph-algorithm-finding-if-graph-is-connected-bipartite-has-cycle-and-is-a-tre 
		visited = dict((vert, False) for vert in self.verts)
		components = []
		for vert in self.verts:
			if not visited[vert]:
				cur_component = set()
				to_traverse = [vert]
				while len(to_traverse) > 0:
					vert2 = to_traverse.pop()
					to_traverse += [vert3 for vert3 in self.get_connected_vertexes(vert2.name) if not visited[vert3]]
					visited[vert2] = True
					cur_component.add(vert2)
				components.append(cur_component)

		largest_component = max(components, key=len)
		for non_largest_component in [c for c in components if c is not largest_component]:
			for vert in non_largest_component:
				for plinename in [ptaddr.plinename for ptaddr in vert.ptaddrs]:
					r.add(plinename)

		if len(r) > len(largest_component)/200:
			# This is meant to handle rare cases.  If it's handling common cases, then that's probably a bug. 
			raise Exception('Something is probably wrong.  %d island plines, %d vertexes in largest component.' \
					% (len(r), len(largest_component)))

		return r

	def init_plinename_to_ptidx_to_vertidx(self, remove_crowded_vertexes_, vertex_limit_zones_filename_):
		addr_to_vertex = self.get_addr_to_vertex()
		verts = set(addr_to_vertex.values())
		if vertex_limit_zones_filename_ is not None:
			verts = self.apply_vertex_limit_zones(verts, vertex_limit_zones_filename_)
		if remove_crowded_vertexes_:
			verts = self.remove_crowded_vertexes(verts)
		self.verts = list(verts)
		self.plinename_to_ptidx_to_vertidx = {plinename: {} for plinename in self.plinename2pts.iterkeys()}
		for vertidx, vert in enumerate(self.verts):
			for ptaddr in vert.ptaddrs:
				self.plinename_to_ptidx_to_vertidx[ptaddr.plinename][ptaddr.ptidx] = vertidx

	@staticmethod
	def apply_vertex_limit_zones(vertexes_, vertex_limit_zones_filename_):
		assert isinstance(vertexes_, set) and isinstance(vertex_limit_zones_filename_, str)
		limitzones = get_vertex_limit_zones_from_yaml_file(vertex_limit_zones_filename_)
		vertexes_by_limitzoneidx = [[]]*len(limitzones)
		r = []
		for vertex in vertexes_:
			for limitzoneidx, limitzone in enumerate(limitzones):
				if vertex.pos().inside_polygon(limitzone.zone_poly):
					vertexes_by_limitzoneidx[limitzoneidx].append(vertex)
					break
			else:
				r.append(vertex)
		for limitzone, vertexes in zip(limitzones, vertexes_by_limitzoneidx):
			if limitzone.ideal_vert_latlng is not None:
				r.append(min(vertexes, key=lambda vert: vert.pos().dist_m(limitzone.ideal_vert_latlng)))
		return set(r)

	@staticmethod
	def remove_crowded_vertexes(vertexes_):
		assert isinstance(vertexes_, set)
		plinenameset_to_verts = defaultdict(lambda: [])
		for vert in vertexes_:
			plinenameset = frozenset(ptaddr.plinename for ptaddr in vert.ptaddrs)
			plinenameset_to_verts[plinenameset].append(vert)
		r = []
		for plinenameset, verts in plinenameset_to_verts.iteritems():
			if len(verts) == 1:
				r.append(verts[0])
			else:
				ref_plinename = anyelem(plinenameset)
				# Sorted along ref_plinename, that is: 
				verts_sorted = sorted(verts, key=lambda vert: vert.get_ptidx(ref_plinename))
				def vertpos(vertidx__): # Just an index into the verts_sorted variable.  Index has no other meaning. 
					return verts_sorted[vertidx__].pos()
				def vert(vertidx__):
					return verts_sorted[vertidx__]
				if vertpos(0).dist_m(vertpos(-1)) < 100:
					r.append(vert(0))
				else:
					r += [vert(0), vert(-1)]
					vert1idx = 0; vert2idx = 1
					DIST = 250
					while vert2idx < len(verts_sorted)-2:
						if vertpos(vert2idx).dist_m(vertpos(vert1idx)) >= DIST:
							r.append(vert(vert2idx))
							vert2idx += 1
							vert1idx = vert2idx-1
						else:
							vert2idx += 1
					if len(r) >= 3 and \
							r[-1].pos().dist_m(vertpos(-2)) >= DIST or vertpos(-2).dist_m(vertpos(-1)) >= DIST:
						r.append(vert(-2))
		return set(r)

	def init_edges(self):
		self.edges = [[] for i in range(len(self.verts))]
		for plinename, ptidx_to_vertidx in self.plinename_to_ptidx_to_vertidx.iteritems():
			vertidxes_in_polyline_order = list(vert for ptidx, vert in iteritemssorted(ptidx_to_vertidx))
			for vertidx1, vertidx2 in hopscotch(vertidxes_in_polyline_order):
				vert1 = self.verts[vertidx1]; vert2 = self.verts[vertidx2]
				vert1_ptidx = vert1.get_ptidx(plinename); vert2_ptidx = vert2.get_ptidx(plinename)
				dist = self.get_wdist_between_points(plinename, vert1_ptidx, vert2_ptidx)
				direction = (0 if vert2_ptidx > vert1_ptidx else 1)
				self.edges[vertidx1].append(Edge(vertidx2, dist, plinename, direction))
				opposite_direction = int(not direction)
				self.edges[vertidx2].append(Edge(vertidx1, dist, plinename, opposite_direction))

	def pprint(self, stream=sys.stdout):
		print >> stream, '{'
		for polyline in self.plinename2pts.itervalues():
			print >> stream, '\t%s' % polyline
		for gridsquareidx, linesegaddrs in self.si_linesegaddrs_by_gridsquareidx.iteritems():
			print >> stream, '\t%s' % gridsquareidx
			for linesegaddr in linesegaddrs:
				print >> stream, '\t\t%s' % linesegaddr
		for vert, edges in iteritemssorted(self.edges):
			print >> stream, '\t%s' % (vert.strlong())
			for edge in edges:
				print >> stream, '\t\t%s' % edge
		print >> stream, '}'

	# mapl = 'meters along polyline' 
	def init_plinename_to_ptidx_to_mapl(self):
		self.plinename_to_ptidx_to_mapl = {}
		for plinename, polyline in self.plinename2pts.iteritems():
			ptidx_to_mapl = [0]
			for ptidx in range(1, len(polyline)):
				prevpt = polyline[ptidx-1]; curpt = polyline[ptidx]
				ptidx_to_mapl.append(ptidx_to_mapl[ptidx-1] + prevpt.dist_m(curpt))
			assert len(ptidx_to_mapl) == len(polyline)
			self.plinename_to_ptidx_to_mapl[plinename] = ptidx_to_mapl
		assert set(self.plinename_to_ptidx_to_mapl.keys()) == set(self.plinename2pts.keys())

	def get_connected_vertexes(self, vertname_):
		edges = self.edges[self.vertname_to_idx[vertname_]]
		return [self.verts[edge.vertidx] for edge in edges]

	# pt args are inclusive / inclusive. 
	def get_wdist_between_points(self, plinename_, startptidx_, endptidx_):
		mapl1 = self.plinename_to_ptidx_to_mapl[plinename_][endptidx_]
		mapl2 = self.plinename_to_ptidx_to_mapl[plinename_][startptidx_]
		uwdist = abs(mapl1 - mapl2)
		wdist = uwdist*self.get_pline_weight(plinename_)
		return wdist

	def get_wdist_between_posaddrs(self, posaddr1_, posaddr2_):
		if posaddr1_.plinename != posaddr2_.plinename:
			raise Exception()
		plinename = posaddr1_.plinename
		r = self.get_wdist_between_points(plinename, posaddr1_.ptidx, posaddr2_.ptidx)
		weight = self.get_pline_weight(plinename)
		posaddr1_dist_to_refpt = self.get_dist_to_reference_point(posaddr1_)*weight
		posaddr2_dist_to_refpt = self.get_dist_to_reference_point(posaddr2_)*weight
		is_posaddr1_less_than_posaddr2 = \
				cmp([posaddr1_.ptidx, posaddr1_.pals], [posaddr2_.ptidx, posaddr2_.pals]) < 0
		if is_posaddr1_less_than_posaddr2:
			r -= posaddr1_dist_to_refpt
			r += posaddr2_dist_to_refpt
		else:
			r += posaddr1_dist_to_refpt
			r -= posaddr2_dist_to_refpt
		return r

	# Each arg can be either a PosAddr or a vertidx (int).  
	# This is meant for use in simple code dealing with paths so, if it's two vertexes, they must be (directly) connected. 
	# If it's a posaddr and a vertex, then we're more lenient.  There can be other vertexes in between but they 
	# must be on the same polyline.  
	# Likewise with two posaddrs.  They must be on the same polyline. 
	def get_wdist(self, arg1_, arg2_):
		assert (isinstance(arg, PosAddr) or isinstance(arg, int) for arg in (arg1_, arg2_))
		if arg1_ == arg2_:
			return 0.0
		else:
			arg1isvert = isinstance(arg1_, int); arg2isvert = isinstance(arg2_, int)
			if not arg1isvert and not arg2isvert:
				return self.get_wdist_between_posaddrs(arg1_, arg2_)
			elif arg1isvert and arg2isvert:
				return min([edge.wdist for edge in self.edges[arg1_] if edge.vertidx == arg2_])
			else:
				posaddr, vertidx = (arg1_, arg2_)[::1 if arg2isvert else -1]
				vertex = self.verts[vertidx]
				ptaddr_of_vertex_on_posaddrs_pline = vertex.get_ptaddr(posaddr.plinename)
				posaddr_of_vertex = PosAddr(ptaddr_of_vertex_on_posaddrs_pline, 0.0)
				return self.get_wdist_between_posaddrs(posaddr, posaddr_of_vertex)

	def get_addr_to_vertex(self):
		self.deloop_polylines()
		latlngid_to_ontop_latlngids = self.get_graph_latlngid_to_ontop_latlngids()
		latlngid_to_addr = self.get_latlngid_to_addr(latlngid_to_ontop_latlngids)
		ptaddr_to_vertex = {}

		# Iterating in a sorted order like this not because this sort has any 
		# useful meaning in itself, but so that the Vertex objects are created in a 
		# predictable order from one run to the next, and so their ids will be the 
		# same, to make debugging easier. 
		def key(latlngid__):
			pt = self.get_point(latlngid_to_addr[latlngid__])
			return pt.lat + pt.lng
		for latlngid, ontop_latlngids in iteritemssorted(latlngid_to_ontop_latlngids, key=key):
			ptaddrs = set(latlngid_to_addr[ontop_latlngid] for ontop_latlngid in set([latlngid]) | ontop_latlngids)
			for ptaddr1, ptaddr2 in combinations(ptaddrs, 2):
				if ptaddr1 in ptaddr_to_vertex:
					vertex = ptaddr_to_vertex[ptaddr1]
					ptaddr_to_vertex[ptaddr2] = vertex
				elif ptaddr2 in ptaddr_to_vertex:
					vertex = ptaddr_to_vertex[ptaddr2]
					ptaddr_to_vertex[ptaddr1] = vertex
				else:
					vertex = Vertex.create_open(self)
					ptaddr_to_vertex[ptaddr1] = vertex
					ptaddr_to_vertex[ptaddr2] = vertex
				vertex.ptaddrs.add(ptaddr1)
				vertex.ptaddrs.add(ptaddr2)

		for ptaddr in ptaddr_to_vertex.keys():
			vertex = ptaddr_to_vertex[ptaddr]
			vertex.remove_unnecessary_ptaddrs()
			if len(vertex.get_looping_plinenames()) > 0:
				del ptaddr_to_vertex[ptaddr]

		for vertex in ptaddr_to_vertex.values():
			vertex.set_closed()

		return dict(ptaddr_to_vertex)

	# This function might modify self.plinename2pts. 
	# This function exists because we don't handle polylines that are loops at all.  
	# (I forget why.  But such polylines are removed when the graph is built.  Currently this happens in 
	# get_addr_to_vertex - "if len(vertex.get_looping_plinenames()) > 0: del ptaddr_to_vertex[ptaddr]".)  
	# But if we split a looping polyline into two, then we handle that fine.  So here we try to split them.
	def deloop_polylines(self):
		for plinename in self.plinename2pts.keys():
			pline = self.plinename2pts[plinename]
			if pline[0].dist_m(pline[-1]) <= self.paths_disttolerance:
				midpt_idx = len(pline)/2
				midpt = pline[midpt_idx]
				assert pline[0].dist_m(midpt) > self.paths_disttolerance and pline[-1].dist_m(midpt) > self.paths_disttolerance
					# ^^ I don't know what to do with a polyline like that.  Sounds useless anyway. 
				new_pline = [pt.copy() for pt in pline[midpt_idx:]] # copying latlngs b/c of the things we do w/ latlng object ids. 
				pline[:] = pline[:midpt_idx+1]
				new_plinename = 'loop part 2 '+plinename # putting new part of name BEFORE, so any suffixes are preserved. 
				assert new_plinename not in self.plinename2pts
				self.plinename2pts[new_plinename] = new_pline
		self.build_spatial_index() # b/c this function might have added new polylines.   

	def get_latlngid_to_addr(self, latlngid_to_ontop_latlngids_):
		r = {}
		for plinename, polyline in self.plinename2pts.iteritems():
			for ptidx, pt in enumerate(polyline):
				r[id(pt)] = PtAddr(plinename, ptidx)
		return r

	def get_graph_latlngid_to_ontop_latlngids(self):
		return self.get_graph_latlngid_to_ontop_latlngids_new()
		
	# Might modify self.plinename2pts (by splitting line segments - not by adding or removing plines).
	def get_graph_latlngid_to_ontop_latlngids_new(self):
		log = False

		latlngid_to_ontop_latlngids = defaultdict(lambda: set())
		def add(pt1_, pt2_):
			assert isinstance(pt1_, geom.LatLng) and isinstance(pt2_, geom.LatLng)
			latlngid_to_ontop_latlngids[id(pt1_)].add(id(pt2_))
			latlngid_to_ontop_latlngids[id(pt2_)].add(id(pt1_))

		for addr1plinename in self.plinename2pts.keys():
			while True:
				num_splits = 0
				for addr1ptidx in range(len(self.plinename2pts[addr1plinename])-1):
					addr1 = PtAddr(addr1plinename, addr1ptidx)
					for addr2 in self.get_linesegaddrs_near_lineseg(addr1, self.paths_disttolerance):
						lineseg1 = self.get_lineseg(addr1)
						lineseg2 = self.get_lineseg(addr2)
						intersection_pt = lineseg1.get_intersection(lineseg2)
						if intersection_pt is not None:
							if all(pt.dist_m(intersection_pt) > self.paths_disttolerance for pt in lineseg1.ptlist() + lineseg2.ptlist()):
								if log: print '-------- line/line splitting', addr1.plinename, ': adding pt', addr1.ptidx+1
								self.plinename2pts[addr1.plinename].insert(addr1.ptidx+1, intersection_pt)
								self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(addr1.plinename, addr1.ptidx+1)

								# Need to do this 'copy' because we're building our maps based on object id of the latlngs and that code 
								# doesn't handle a single LatLng object being used in more than one place.
								if log: print '-------- line/line splitting', addr2.plinename, ': adding pt', addr2.ptidx+1
								intersection_pt_copy_for_line2 = intersection_pt.copy()
								self.plinename2pts[addr2.plinename].insert(addr2.ptidx+1, intersection_pt_copy_for_line2)
								self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(addr2.plinename, addr2.ptidx+1)

								num_splits += 1
								break
					if num_splits > 0:
						break
				if num_splits == 0:
					break

		for addr1plinename in self.plinename2pts.keys():
			while True:
				num_splits = 0
				for addr1ptidx in range(len(self.plinename2pts[addr1plinename])):
					addr1 = PtAddr(addr1plinename, addr1ptidx)
					for addr2 in self.get_linesegaddrs_near_point(addr1, self.paths_disttolerance):
						addr1_pt = self.get_point(addr1)
						addr2_lineseg = self.get_lineseg(addr2)
						snapped_pt, dist_to_lineseg = addr1_pt.snap_to_lineseg_opt(addr2_lineseg, self.paths_disttolerance)
						if (dist_to_lineseg is not None) and (dist_to_lineseg < self.paths_disttolerance):
							if log: print '-------- pt/line splitting', addr2.plinename, ': adding pt', addr2.ptidx+1
							self.plinename2pts[addr2.plinename].insert(addr2.ptidx+1, snapped_pt)
							self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(addr2.plinename, addr2.ptidx+1)
							num_splits += 1
							break
					if num_splits > 0:
						break
				if num_splits == 0:
					break

		for ptaddr1, ptaddr2 in self.get_addr_combos_near_each_other(False, False, self.paths_disttolerance):
			pt1 = self.get_point(ptaddr1)
			pt2 = self.get_point(ptaddr2)
			if log: print '-------- testing pt/pt    ', ptaddr1, ptaddr2
			if pt1.dist_m(pt2) <= self.paths_disttolerance:
				if log: print '-------- adding pt/pt    ', ptaddr1, ptaddr2, pt1
				add(pt1, pt2)

		return dict(latlngid_to_ontop_latlngids)

	# Might modify self.plinename2pts (by splitting line segments - not by adding or removing plines).
	def get_graph_latlngid_to_ontop_latlngids_old(self):
		latlngid_to_ontop_latlngids = defaultdict(lambda: set())
		def add(pt1_, pt2_):
			assert isinstance(pt1_, geom.LatLng) and isinstance(pt2_, geom.LatLng)
			latlngid_to_ontop_latlngids[id(pt1_)].add(id(pt2_))
			latlngid_to_ontop_latlngids[id(pt2_)].add(id(pt1_))
		for ptaddr1, ptaddr2 in self.get_addr_combos_near_each_other(False, False, self.paths_disttolerance):
			pt1 = self.get_point(ptaddr1)
			pt2 = self.get_point(ptaddr2)
			#print '-------- testing pt/pt    ', ptaddr1, ptaddr2
			if pt1.dist_m(pt2) <= self.paths_disttolerance:
				#print '-------- adding pt/pt    ', ptaddr1, ptaddr2, pt1
				add(pt1, pt2)
		for ptaddr, linesegaddr in self.get_addr_combos_near_each_other(False, True, self.paths_disttolerance):
			pt = self.get_point(ptaddr)
			lineseg = self.get_lineseg(linesegaddr)
			t0 = time.time()

			#print '-------- testing pt/line  ', ptaddr, linesegaddr
			snapped_pt, dist_to_lineseg = pt.snap_to_lineseg_opt(lineseg, self.paths_disttolerance)
			if (dist_to_lineseg is not None) and (dist_to_lineseg < self.paths_disttolerance):

			#snapped_pt, snapped_to_lineseg_ptidx, dist_to_lineseg = pt.snap_to_lineseg(lineseg)
			#if dist_to_lineseg < self.paths_disttolerance and snapped_to_lineseg_ptidx is None \
			#		and (snapped_pt.dist_m(lineseg.start) > self.paths_disttolerance and snapped_pt.dist_m(lineseg.end) > self.paths_disttolerance):

				# The point of that last test (not being too close to either end of the lineseg) is because those cases will 
				# be picked up by the point/point combos above.  Also, splitting a lineseg that close to one end would be ridiculous. 
				#print '-------- adding pt/line  ', ptaddr, linesegaddr, pt
				self.plinename2pts[linesegaddr.plinename].insert(linesegaddr.ptidx+1, snapped_pt)
				linesegaddr.ptidx += 1
				add(pt, snapped_pt)

		for linesegaddr1, linesegaddr2 in self.get_addr_combos_near_each_other(True, True, self.paths_disttolerance):
			#print '-------- testing line/line', linesegaddr1, linesegaddr2
			lineseg1 = self.get_lineseg(linesegaddr1)
			lineseg2 = self.get_lineseg(linesegaddr2)
			intersection_pt = lineseg1.get_intersection(lineseg2)
			if intersection_pt is not None:
				if all(pt.dist_m(intersection_pt) > self.paths_disttolerance for pt in lineseg1.ptlist() + lineseg2.ptlist()):
					#print '-------- adding line/line', linesegaddr1, linesegaddr2, intersection_pt
					self.plinename2pts[linesegaddr1.plinename].insert(linesegaddr1.ptidx+1, intersection_pt)
					# Need to do this 'copy' because we're building our maps based on object id of the latlngs and that code 
					# doesn't handle a single LatLng object being used in more than one place.
					intersection_pt_copy_for_line2 = intersection_pt.copy()
					self.plinename2pts[linesegaddr2.plinename].insert(linesegaddr2.ptidx+1, intersection_pt_copy_for_line2)
					linesegaddr1.ptidx += 1
					linesegaddr2.ptidx += 1
					add(intersection_pt, intersection_pt_copy_for_line2)
		#self.assert_latlngid_to_ontop_latlngids_is_sane(latlngid_to_ontop_latlngids)
		return dict(latlngid_to_ontop_latlngids)

	def assert_latlngid_to_ontop_latlngids_is_sane(self, latlngid_to_ontop_latlngids_):
		def latlngid_is_in_polylines(latlngid_):
			for polyline in self.plinename2pts.itervalues():
				for pt in polyline:
					if id(pt) == latlngid_:
						return True
			return False
		for latlngid, ontop_latlngids in latlngid_to_ontop_latlngids_.iteritems():
			assert latlngid_is_in_polylines(latlngid)
			for ontop_latlngid in ontop_latlngids:
				assert latlngid_is_in_polylines(ontop_latlngid)

	def build_spatial_index(self):
		all_pts = sum(self.plinename2pts.itervalues(), [])
		all_pts_boundingbox = geom.BoundingBox(all_pts)
		self.si_gridsquaresys = grid.GridSquareSystem(None, None, None, None, all_pts_boundingbox)
		self.si_linesegaddrs_by_gridsquareidx = [set() for i in range(self.si_gridsquaresys.num_idxes())]
		self.si_plinename_to_gridsquareidxes = {plinename: set() for plinename in self.plinename2pts.iterkeys()}
		for plinename, polyline in self.plinename2pts.iteritems():
			for startptidx in range(0, len(polyline)-1):
				linesegaddr = PtAddr(plinename, startptidx)
				for gridsquare in get_gridsquares_touched_by_lineseg(self.get_lineseg(linesegaddr), self.si_gridsquaresys):
					gridsquareidx = self.si_gridsquaresys.idx(gridsquare)
					self.si_linesegaddrs_by_gridsquareidx[gridsquareidx].add(linesegaddr)
					self.si_plinename_to_gridsquareidxes[plinename].add(gridsquareidx)

	def get_lineseg(self, linesegaddr_):
		polyline = self.plinename2pts[linesegaddr_.plinename]
		return geom.LineSeg(polyline[linesegaddr_.ptidx], polyline[linesegaddr_.ptidx+1])

	def get_point(self, linesegaddr_):
		return self.plinename2pts[linesegaddr_.plinename][linesegaddr_.ptidx]

	# returns: list, each element either a PosAddr or a Vertex, sorted by dist to target_ in increasing order. 
	# There are three stages to this.  The first stage finds all of the possible lineseg (i.e. PosAddr) snaps.  Simple.  
	# 
	# The second stage reduces that list of lineseg snaps to probably one per polyline.  The reason for doing this is because 
	# for most cases, several consecutive linesegs will be within the search radius, and we'll see a lot of useless 
	# snaps with a pals of 0 or 1.  These are not useful.  So we get the closest ones to our target only, 
	# AKA the local minima by dist to target.
	# 
	# The third stages adds all of the vertexes surrounding the posaddrs that we have.
	def multisnap(self, target_, searchradius_, includeverts=True, plineomitflag=None):
		r = self.multisnap_with_dists(target_, searchradius_, includeverts=includeverts, plineomitflag=plineomitflag)
		return tuple(x[0] for x in r)

	def multisnap_with_dists(self, target_, searchradius_, includeverts=True, plineomitflag=None):
		assert (searchradius_ is not None) and (plineomitflag is None or len(plineomitflag))
		linesegaddr_to_lssr = {}
		gridsquare = grid.GridSquare.from_latlng(target_, self.si_gridsquaresys)
		for linesegaddr in self.get_nearby_linesegaddrs_grid_order(gridsquare, searchradius_):
			if plineomitflag is not None and has_flag(linesegaddr.plinename, plineomitflag):
				continue
			lineseg = self.get_lineseg(linesegaddr)
			lssr = target_.snap_to_lineseg(lineseg)
			if lssr.dist <= searchradius_:
				linesegaddr_to_lssr[linesegaddr] = lssr
		plinenames = set(addr.plinename for addr in linesegaddr_to_lssr.keys())

		# It's not a big deal but in the return value for this function we sort the 
		# posaddrs and vertexes not just but dist but by (dist, plinename) or 
		# (dist, vert.name).  Mostly doing this to make a unit test easy for 
		# myself, as I experiment with changing the iteration order of gridsquares.  
		# Some elements in the returned list will have the same latlng (and hence 
		# the same dist) such as vertexes that are part of the same intersection, 
		# and also some plines that are coincident and made from the same source 
		# data (such as king and dundas, currently.)  So this (dist, name) sorting 
		# ensures consistent order of the returned value regardless of the 
		# iteration order of the gridsquares.  

		r = [] # initially a list of (<PosAddr|Vertex>, (dist, name)) pairs 

		for plinename in plinenames:
			plines_linesegaddr_to_lssr = sorteddict((k, v) for k, v in linesegaddr_to_lssr.iteritems() if k.plinename == plinename)
			plines_linesegaddrs = plines_linesegaddr_to_lssr.sortedkeys()
			plines_lssrs = plines_linesegaddr_to_lssr.values_sorted_by_key()
			relevant_idxes = get_local_minima_indexes(plines_lssrs, lambda lssr: lssr.dist)
			for idx in relevant_idxes:
				linesegaddr = plines_linesegaddrs[idx]
				lssr = plines_lssrs[idx]
				r.append((PosAddr(linesegaddr.copy(), lssr.pals), (lssr.dist, linesegaddr.plinename)))

		if includeverts:
			r_verts = []
			for i, posaddr in list(enumerate([e[0] for e in r]))[::-1]:
				bounding_vertexes = self.get_bounding_verts(posaddr)
				for vert in bounding_vertexes:
					dist = vert.pos().dist_m(target_) 
					if dist <= searchradius_:
						r_verts.append((vert, (dist, vert.name)))
				if any(self.get_latlng(posaddr).dist_m(vert.pos()) < 5 for vert in bounding_vertexes):
					r.pop(i)
			r += uniq(sorted(r_verts))

		r.sort(key=lambda x: x[1])
		r = [(e[0], e[1][0]) for e in r]
		return tuple(r)

	def is_there_a_vertex_at(self, ptaddr_):
		assert isinstance(ptaddr_, PtAddr)
		return ptaddr_.ptidx in self.plinename_to_ptidx_to_vertidx[ptaddr_.plinename]

	def no_verts_between(self, posaddr1_, posaddr2_):
		assert isinstance(posaddr1_, PosAddr) and isinstance(posaddr2_, PosAddr)
		if posaddr1_.plinename != posaddr2_.plinename:
			return False
		else:
			return self.get_bounding_vertidxes(posaddr1_) == self.get_bounding_vertidxes(posaddr2_)

	# arg searchradius_ is in metres.  None means unlimited i.e. keep looking forever.  
	# As long as this object contains some lines, something will be found and returned.  Probably quickly, too. 
	# The word 'forever' is misleading. 
	#
	# returns: a PosAddr, or None if no lines were found within the search radius.
	def snap(self, target_, searchradius_):
		return self.snap_with_dist(target_, searchradius_)[0]

	def snap_with_dist(self, target_, searchradius_):
		assert isinstance(target_, geom.LatLng) and (searchradius_ > 0)
		target_gridsquare = grid.GridSquare.from_latlng(target_, self.si_gridsquaresys)
		a_nearby_linesegaddr = self.get_a_nearby_linesegaddr(target_gridsquare, searchradius_)
		if a_nearby_linesegaddr is None:
			return (None, None)
		a_nearby_lineseg = self.get_lineseg(a_nearby_linesegaddr)
		endgame_search_radius = self._snap_get_endgame_search_radius(a_nearby_lineseg, target_gridsquare)
		best_yet_lssr = None; best_yet_linesegaddr = None  # "lssr" stands for LineSegSnapResult. 
		for linesegaddr in self._snap_get_endgame_linesegaddrs(target_gridsquare, endgame_search_radius):
			lineseg = self.get_lineseg(linesegaddr)
			cur_lssr = target_.snap_to_lineseg(lineseg)
			if best_yet_lssr==None or cur_lssr.dist < best_yet_lssr.dist:
				best_yet_lssr = cur_lssr
				best_yet_linesegaddr = linesegaddr
		if (best_yet_lssr == None) or (searchradius_ is not None and best_yet_lssr.dist > searchradius_):
			return (None, None)
		else:
			return (PosAddr(best_yet_linesegaddr.copy(), best_yet_lssr.pals), best_yet_lssr.dist)

	def _snap_get_endgame_linesegaddrs(self, target_gridsquare_, search_radius_):
		assert isinstance(target_gridsquare_, grid.GridSquare)
		r = set()
		for linesegaddr in self.get_nearby_linesegaddrs_grid_order(target_gridsquare_, search_radius_):
			r.add(linesegaddr)
		return r

	def _snap_get_endgame_search_radius(self, a_nearby_lineseg_, target_gridsquare_):
		assert isinstance(a_nearby_lineseg_, geom.LineSeg) and isinstance(target_gridsquare_, grid.GridSquare)
		corners = target_gridsquare_.corner_latlngs()
		r = max(sr.dist for sr in [latlng.snap_to_lineseg(a_nearby_lineseg_) for latlng in corners])
		return int(r)

	def heading(self, linesegaddr_, referencing_lineseg_aot_point_):
		assert isinstance(linesegaddr_, PtAddr)
		# TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is False.
		assert linesegaddr_.plinename in self.plinename2pts
		if referencing_lineseg_aot_point_:
			assert 0 <= linesegaddr_.ptidx < len(self.plinename2pts[linesegaddr_.plinename])-1
		else:
			assert 0 <= linesegaddr_.ptidx < len(self.plinename2pts[linesegaddr_.plinename])
		startptidx = linesegaddr_.ptidx
		if linesegaddr_.ptidx == len(self.plinename2pts[linesegaddr_.plinename])-1:
			assert not referencing_lineseg_aot_point_
			startptidx -= 1
		linesegaddr = PtAddr(linesegaddr_.plinename, startptidx)
		lineseg = self.get_lineseg(linesegaddr)
		return lineseg.start.heading(lineseg.end)

	# Return a linesegaddr, any linesegaddr.  It will probably be one nearby, but definitely not guaranteed to be the closest. 
	def get_a_nearby_linesegaddr(self, gridsquare_, searchradius_):
		for linesegaddr in self.get_nearby_linesegaddrs_spiral_order(gridsquare_, searchradius_):
			return linesegaddr
		return None

	# This grid order function is faster than the spiral order function, 
	# but might be inappropriate for a (single) snap with a large search radius, 
	# because it doesn't give up early if a lineseg is found, so you might not want to use it there.  
	# I haven't proven this. 
	def get_nearby_linesegaddrs_grid_order(self, gridsquare_, searchradius_):
		assert isinstance(gridsquare_, grid.GridSquare)
		for gridsquareidx in self.get_nearby_gridsquareidxes_grid_order(gridsquare_, searchradius_):
			for linesegaddr in self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]:
				yield linesegaddr

	def get_nearby_gridsquareidxes_grid_order(self, square_, searchradius_):
		latreach, lngreach = get_reaches(square_, searchradius_)
		bottomleft_square = grid.GridSquare.from_ints(square_.gridlat - latreach, square_.gridlng - lngreach, self.si_gridsquaresys)
		self.si_gridsquaresys.rein_in_gridsquare(bottomleft_square)
		topright_square = grid.GridSquare.from_ints(square_.gridlat + latreach, square_.gridlng + lngreach, self.si_gridsquaresys)
		self.si_gridsquaresys.rein_in_gridsquare(topright_square)
		r = self.si_gridsquaresys.idx(bottomleft_square)
		sw, ne = self.si_gridsquaresys.southwest_gridsquare, self.si_gridsquaresys.northeast_gridsquare
		numlngcolumns_entire = (ne.gridlng - sw.gridlng + 1)
		numlngcolumns_ourbox = (topright_square.gridlng - bottomleft_square.gridlng + 1)
		for lat in xrange(bottomleft_square.gridlat, topright_square.gridlat+1):
			for lng in xrange(bottomleft_square.gridlng, topright_square.gridlng+1):
				yield r
				r += 1
			r += numlngcolumns_entire - numlngcolumns_ourbox

	def get_nearby_linesegaddrs_spiral_order(self, gridsquare_, searchradius_):
		assert isinstance(gridsquare_, grid.GridSquare)
		for gridsquareidx in self.si_gridsquaresys.idxes(gridsquare_spiral_gen_by_geom_vals(gridsquare_, searchradius_)):
			for linesegaddr in self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]:
				yield linesegaddr

	# If the consumer of this generator modifies the ptidx field of the 
	# yielded objects, that will be noticed by the generator and looping will be 
	# affected.   This behaviour is only supported for ptidx (not 
	# plinename) because that's all I need right now. 
	def get_addr_combos_near_each_other(self, linesforaddr1_, linesforaddr2_, dist_m_):
		assert not (linesforaddr1_ and not linesforaddr2_) # Not supported due to laziness. 
		if dist_m_ is None: raise Exception()  # we work with sets.  can't handle infinite search radius. 
		for addr1plinename in self.plinename2pts.keys():
			addr1ptidx = 0
			while addr1ptidx < len(self.plinename2pts[addr1plinename]) - (1 if linesforaddr1_ else 0):
				addr1 = PtAddr(addr1plinename, addr1ptidx)
				if linesforaddr1_:
					if linesforaddr2_:
						addr2s = self.get_linesegaddrs_near_lineseg(addr1, dist_m_)
					else:
						addr2s = self.get_ptaddrs_near_lineseg(addr1, dist_m_)
				else:
					if linesforaddr2_:
						addr2s = self.get_linesegaddrs_near_point(addr1, dist_m_)
					else:
						addr2s = self.get_ptaddrs_near_point(addr1, dist_m_)
				addr2s = list(addr2s)
				addr2i = 0
				while addr2i < len(addr2s):
					addr2 = addr2s[addr2i]
					# Doing this because if we don't, for point/point combos we'll yield eg. (A, B) and (B, A) for everything, 
					# and the user of this generator doesn't want that.  Same applies for line/line combos.   This doesn't 
					# apply for point/line combos, because the combination of point A lineseg B is very different than the combination 
					# of point B lineseg A. 
					if (not linesforaddr1_ and linesforaddr2_) or (addr1.plinename < addr2.plinename):
						if not(linesforaddr2_ and addr2.ptidx == len(self.plinename2pts[addr2.plinename])-1):
							yielded_addr2 = addr2.copy()
							yield (addr1, yielded_addr2)
							if addr1ptidx != addr1.ptidx:
								assert addr1plinename == addr1.plinename and addr1ptidx == addr1.ptidx-1
								addr1.ptidx -= 1
								addr2s = get_adjusted_addrs_from_polyline_split(addr1.plinename, addr1.ptidx, addr2s)
								self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(addr1.plinename, addr1.ptidx)
							if addr2.ptidx != yielded_addr2.ptidx:
								assert addr2.plinename == yielded_addr2.plinename and addr2.ptidx == yielded_addr2.ptidx-1
								addr2s = get_adjusted_addrs_from_polyline_split(yielded_addr2.plinename, yielded_addr2.ptidx, addr2s)
								self.adjust_addrs_in_spatial_index_to_deal_with_polyline_split(yielded_addr2.plinename, yielded_addr2.ptidx)
								addr2i += 1
					addr2i += 1
				addr1ptidx += 1

	def adjust_addrs_in_spatial_index_to_deal_with_polyline_split(self, plinename_, newptidx_):
		for gridsquareidx in self.si_plinename_to_gridsquareidxes[plinename_]:
			self.si_linesegaddrs_by_gridsquareidx[gridsquareidx] \
					= get_adjusted_addrs_from_polyline_split(plinename_, newptidx_, self.si_linesegaddrs_by_gridsquareidx[gridsquareidx])

	def get_linesegaddrs_near_lineseg(self, linesegaddr_, searchradius_):
		r = set()
		for gridsquareidx in self.si_gridsquaresys.idxes(self.get_gridsquares_near_lineseg(linesegaddr_, searchradius_)):
			r |= self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]
		return r

	def get_ptaddrs_near_lineseg(self, linesegaddr_, searchradius_):
		return self.get_ptaddrs_in_gridsquares(self.get_gridsquares_near_lineseg(linesegaddr_, searchradius_))

	def get_ptaddrs_in_gridsquares(self, gridsquares_):
		r = set()
		for gridsquareidx in self.si_gridsquaresys.idxes(gridsquares_):
			for ptaddr in self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]:
				r.add(ptaddr)
				if ptaddr.ptidx == len(self.plinename2pts[ptaddr.plinename]) - 2:
					r.add(PtAddr(ptaddr.plinename, ptaddr.ptidx+1))
		return r

	def get_linesegaddrs_near_point(self, ptaddr_, searchradius_):
		r = set()
		for gridsquareidx in self.si_gridsquaresys.idxes(self.get_gridsquares_near_point(ptaddr_, searchradius_)):
			r |= self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]
		return r

	def get_ptaddrs_near_point(self, ptaddr_, searchradius_):
		return self.get_ptaddrs_in_gridsquares(self.get_gridsquares_near_point(ptaddr_, searchradius_))

	def get_gridsquares_near_point(self, ptaddr_, searchradius_):
		r = set()
		pts_gridsquare = grid.GridSquare.from_latlng(self.get_point(ptaddr_), self.si_gridsquaresys)
		r.add(pts_gridsquare)
		r |= get_nearby_gridsquares(pts_gridsquare, searchradius_)
		return r

	def get_gridsquares_near_lineseg(self, linesegaddr_, searchradius_):
		r = set()
		lineseg = self.get_lineseg(linesegaddr_)
		for gridsquare in get_gridsquares_touched_by_lineseg(lineseg, self.si_gridsquaresys):
			r.add(gridsquare)
			r |= get_nearby_gridsquares(gridsquare, searchradius_)
		return r

	def get_infos_for_box(self, sw_, ne_):
		assert all(isinstance(x, geom.LatLng) for x in [sw_, ne_])
		linesegaddrs = self.get_linesegaddrs_for_box(sw_, ne_)
		vertexes = set()
		plinenames = sorted(set([linesegaddr.plinename for linesegaddr in linesegaddrs]))
		for plinename in plinenames:
			vertidxes = set(self.plinename_to_ptidx_to_vertidx.get(plinename, {}).values())
			vertexes |= set(self.verts[vertidx] for vertidx in vertidxes)
		vertexes = [vert for vert in vertexes if vert.pos().is_within_box(sw_, ne_)]

		plinename_to_ptidx_to_pt = {}
		plinename_to_ptidx_to_hasvertex = {}
		for plinename in plinenames:
			ptidxes = [addr.ptidx for addr in linesegaddrs if addr.plinename == plinename]
			ptidxes = sorted(set(sum(([ptidx, ptidx+1] for ptidx in ptidxes), [])))
			ptidxes = range(min(ptidxes), max(ptidxes)+1)
			ptidx_to_pt = {ptidx: self.get_point(PtAddr(plinename, ptidx)) for ptidx in ptidxes}
			plinename_to_ptidx_to_pt[plinename] = ptidx_to_pt
			ptidx_to_hasvertex = {ptidx: self.is_there_a_vertex_at(PtAddr(plinename, ptidx)) for ptidx in ptidxes}
			plinename_to_ptidx_to_hasvertex[plinename] = ptidx_to_hasvertex
		return {'vertname_to_info': dict((vert.name, vert.to_json_dict()) for vert in vertexes), 
				'plinename_to_ptidx_to_pt': plinename_to_ptidx_to_pt, 
				'plinename_to_ptidx_to_hasvertex': plinename_to_ptidx_to_hasvertex}

	def get_linesegaddrs_for_box(self, sw_, ne_):
		assert all(isinstance(x, geom.LatLng) for x in [sw_, ne_])
		sw_gridsquare = grid.GridSquare.from_latlng(sw_, self.si_gridsquaresys)
		ne_gridsquare = grid.GridSquare.from_latlng(ne_, self.si_gridsquaresys)
		r = set()
		for gridlat in range(sw_gridsquare.gridlat, ne_gridsquare.gridlat+1):
			for gridlng in range(sw_gridsquare.gridlng, ne_gridsquare.gridlng+1):
				gridsquareidx = self.si_gridsquaresys.idx(grid.GridSquare.from_ints(gridlat, gridlng, self.si_gridsquaresys))
				if gridsquareidx == -1:
					continue
				r |= self.si_linesegaddrs_by_gridsquareidx[gridsquareidx]
		return r

	def mapl_to_latlng(self, plinename_, mapl_):
		r = self.mapl_to_latlngnheading(plinename_, mapl_)
		return (r[0] if r is not None else None)
		
	def mapl_to_latlngnheading(self, plinename_, mapl_):
		if mapl_ < 0:
			return None
		ptidx_to_mapl = self.plinename_to_ptidx_to_mapl[plinename_]
		# Writing this code this way because we might need to handle a mapl_ that 
		# is a little greater than the max mapl of this route.  Hopefully not too 
		# much - maybe a couple of meters?  I'm not sure.
		for i in range(1, len(ptidx_to_mapl)):
			if ptidx_to_mapl[i] >= mapl_:
				break
		prevpt = self.plinename2pts[plinename_][i-1]; curpt = self.plinename2pts[plinename_][i]
		prevmapl = ptidx_to_mapl[i-1]; curmapl = ptidx_to_mapl[i]
		pt = curpt.subtract(prevpt).scale((mapl_-prevmapl)/float(curmapl-prevmapl)).add(prevpt)
		return (pt, prevpt.heading(curpt))

	def get_pline_len(self, plinename_):
		return self.plinename_to_ptidx_to_mapl[plinename_][-1]

def get_adjusted_addrs_from_polyline_split(plinename_, newptidx_, addrs_):
	assert isinstance(plinename_, str) and isinstance(newptidx_, int)
	inaddrs = (addrs_ if isinstance(addrs_, Sequence) else list(addrs_))
	r = []
	for addr in inaddrs:
		if addr.plinename == plinename_ and addr.ptidx >= newptidx_:
			r.append(PtAddr(addr.plinename, addr.ptidx+1))
		else:
			r.append(addr)
	if PtAddr(plinename_, newptidx_-1) in addrs_:
		r.append(PtAddr(plinename_, newptidx_))
	return (r if isinstance(addrs_, Sequence) else set(r))

def get_gridsquares_touched_by_lineseg(lineseg_, gridsquaresys_):
	assert isinstance(lineseg_, geom.LineSeg)
	linesegstartgridsquare = grid.GridSquare.from_latlng(lineseg_.start, gridsquaresys_)
	linesegendgridsquare = grid.GridSquare.from_latlng(lineseg_.end, gridsquaresys_)
	# TODO: be more specific in the grid squares considered touched by a line.  We are covering a whole bounding box.
	# we could narrow down that set of squares a lot.
	for gridlat in intervalii(linesegstartgridsquare.gridlat, linesegendgridsquare.gridlat):
		for gridlng in intervalii(linesegstartgridsquare.gridlng, linesegendgridsquare.gridlng):
			yield grid.GridSquare.from_ints(gridlat, gridlng, gridsquaresys_)

# "reach" means how man grid squares one should search in each direction (lat/lng) 
# in order to cover a given search radius.  
# return always >= 1. 
# arg searchradius_ None means unlimited. 
def get_reaches(target_gridsquare_, searchradius_):
	assert isinstance(target_gridsquare_, grid.GridSquare)
	if searchradius_ is None:
		return (None, None)
	else:
		lat_reach = get_reach_single(target_gridsquare_, searchradius_, True)
		gridsquaresys = target_gridsquare_.sys
		lon_reach_top = get_reach_single(grid.GridSquare.from_ints(target_gridsquare_.gridlat+lat_reach+1, target_gridsquare_.gridlng, gridsquaresys), searchradius_, False)
		lon_reach_bottom = get_reach_single(grid.GridSquare.from_ints(target_gridsquare_.gridlat-lat_reach, target_gridsquare_.gridlng, gridsquaresys), searchradius_, False)
		return (lat_reach, max(lon_reach_top, lon_reach_bottom))

def get_reach_single(reference_gridsquare_, searchradius_, lat_aot_lng_):
	assert isinstance(reference_gridsquare_, grid.GridSquare) and (isinstance(searchradius_, int) or isinstance(searchradius_, float)) 
	assert isinstance(lat_aot_lng_, bool)
	reference_gridsquare_latlng = reference_gridsquare_.latlng()
	r = 1
	gridsquaresys = reference_gridsquare_.sys
	while True:
		if lat_aot_lng_:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat + r*gridsquaresys.latstep, reference_gridsquare_latlng.lng)
		else:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat, reference_gridsquare_latlng.lng + r*gridsquaresys.lngstep)
		if cur_latlng.dist_m(reference_gridsquare_latlng) >= searchradius_:
			return r
		r += 1

def offsets_for_square_spiral_gen(square_reach_):
	r = [0, 0]
	yield r
	for spiralidx in (count() if square_reach_ is None else range(square_reach_+2)):
		for i in range(spiralidx*2 + 1): # north 
			r[0] += 1
			yield r
		for i in range(spiralidx*2 + 1): # east 
			r[1] += 1
			yield r
		for i in range(spiralidx*2 + 2): # south
			r[0] -= 1
			yield r
		for i in range(spiralidx*2 + 2): # west
			r[1] -= 1
			yield r

# yields a 2-tuple of integer offsets - that is, lat/lng offsets eg. (0,0), (1,0), (1,1), (-1, 1), etc.
def gridsquare_offset_spiral_gen(latreach_, lngreach_):
	assert (isinstance(latreach_, int) and isinstance(lngreach_, int)) or (latreach_ is None and lngreach_ is None)

	unlimited = (latreach_ is None)

	# Note that max(None,None) == None
	for offsetlat, offsetlng in offsets_for_square_spiral_gen(max(latreach_, lngreach_) if not unlimited else None):
		if unlimited or (abs(offsetlat) <= latreach_ and abs(offsetlng) <= lngreach_):
			yield (offsetlat, offsetlng)

# reach args - None means unlimited.
def gridsquare_spiral_gen_by_grid_vals(center_gridsquare_, latreach_, lngreach_):
	assert isinstance(center_gridsquare_, grid.GridSquare)
	assert (latreach_ is None) == (lngreach_ is None)
	gridsquaresys = center_gridsquare_.sys
	for offsetlat, offsetlng in gridsquare_offset_spiral_gen(latreach_, lngreach_):
		yield grid.GridSquare.from_ints(center_gridsquare_.gridlat + offsetlat, center_gridsquare_.gridlng + offsetlng, gridsquaresys)

# arg searchradius_ meters or None for unlimited. 
def gridsquare_spiral_gen_by_geom_vals(center_gridsquare_, searchradius_):
	latreach, lngreach = get_reaches(center_gridsquare_, searchradius_)
	for gridsquare in gridsquare_spiral_gen_by_grid_vals(center_gridsquare_, latreach, lngreach):
		yield gridsquare

def get_nearby_gridsquares(center_gridsquare_, searchradius_):
	return set(gridsquare_spiral_gen_by_geom_vals(center_gridsquare_, searchradius_))

def pt_lies_along(pt_, lineseg_):
	if 0.00 <= geom.get_pass_ratio(lineseg_.start, lineseg_.end, pt_) <= 1.0:
		pass_pt = geom.get_pass_point(lineseg_.start, lineseg_.end, pt_)
		if (pass_pt.dist_m(lineseg_.start) > 1) and (pass_pt.dist_m(lineseg_.end) > 1):
		#if 1:
			return (pass_pt.dist_m(pt_) < 2)
	return False

def linesegs_coincide(lineseg1_, lineseg2_):
	headings_tolerance = 2
	diff_headings = geom.diff_headings(lineseg1_.heading(), lineseg2_.heading())
	if not(diff_headings <= headings_tolerance or diff_headings >= 180 - headings_tolerance):
		return False
	else:
		return pt_lies_along(lineseg1_.start, lineseg2_) or pt_lies_along(lineseg1_.end, lineseg2_)

# Thanks to http://tech-algorithm.com/articles/drawing-line-using-bresenham-algorithm/ 
def bresenham2(gridsquare0_, gridsquare1_):
	assert gridsquare0_.sys == gridsquare1_.sys
	gridsquaresys = gridsquare0_.sys
	r = []
	def ret(x__, y__):
		r.append(grid.GridSquare.from_ints(y__, x__, gridsquaresys))

	x = gridsquare0_.gridlng; y = gridsquare0_.gridlat
	x2 = gridsquare1_.gridlng; y2 = gridsquare1_.gridlat

	w = x2 - x 
	h = y2 - y 
	dx1 = 0; dy1 = 0; dx2 = 0; dy2 = 0 
	if (w<0):
		dx1 = -1
	elif (w>0):
		dx1 = 1 
	if (h<0):
		dy1 = -1
	elif (h>0):
		dy1 = 1 
	if (w<0):
		dx2 = -1
	elif (w>0):
		dx2 = 1 
	longest = abs(w) 
	shortest = abs(h) 
	if( not (longest>shortest)) :
		longest = abs(h) 
		shortest = abs(w) 
		if (h<0) : 
			dy2 = -1 
		elif (h>0):
			dy2 = 1 
		dx2 = 0             
	numerator = longest >> 1 
	for i in range(longest+1):
		ret(x, y)
		numerator += shortest 
		if ( not (numerator<longest)):
			numerator -= longest 
			x += dx1 
			y += dy1 
		else:
			x += dx2 
			y += dy2 

	return r
	

# Thanks to http://en.wikipedia.org/wiki/Bresenham%27s_line_algorithm#Algorithm_with_Integer_Arithmetic 
def bresenham1(gridsquare0_, gridsquare1_):
	assert gridsquare0_.sys == gridsquare1_.sys
	gridsquaresys = gridsquare0_.sys

	r = []

	x0 = gridsquare0_.gridlng; y0 = gridsquare0_.gridlat
	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat

	def ret(x__, y__):
		r.append(grid.GridSquare.from_ints(y__, x__, gridsquaresys))

	dx=x1-x0
	dy=y1-y0

	D = 2*dy - dx
	ret(x0, y0)
	y=y0

	for x in range(x0+1, x1+1):
		if D > 0:
			y = y+1
			ret(x, y)
			D = D + (2*dy-2*dx)
		else:
			ret(x, y)
			D = D + (2*dy)

	return r

def get_octant(gridsquare1_, gridsquare2_):
	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat
	x2 = gridsquare2_.gridlng; y2 = gridsquare2_.gridlat
	dx = x2 - x1; dy = y2 - y1
	if dx >= 0 and dy >= 0:
		return 1 if dx >= dy else 2
	elif dx <= 0 and dy >= 0:
		return 3 if dy >= abs(dx) else 4
	elif dx <= 0 and dy <= 0:
		return 5 if abs(dx) >= abs(dy) else 6
	else:
		return 7 if abs(dy) >= dx else 8

def get_supercover(gridsquare1_, gridsquare2_):
	def switchxy(x__, y__):
		return (y__, x__)
	def negx(x__, y__):
		return (-x__, y__)
	def negy(x__, y__):
		return (x__, -y__)
	def negxy(x__, y__):
		return (-x__, -y__)
	def identity(x__, y__):
		return (x__, y__)
	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat
	x2 = gridsquare2_.gridlng; y2 = gridsquare2_.gridlat
	dx = x2 - x1; dy = y2 - y1
	octant = get_octant(gridsquare1_, gridsquare2_)
	funcs = {1: [identity], 2: [switchxy], 3: [negx, switchxy], 4: [negx], 
			5: [negxy], 6: [switchxy, negxy], 7: [negy, switchxy], 8: [negy]}[octant]


# Thanks to http://lifc.univ-fcomte.fr/~dedu/projects/bresenham/index.html 
def get_supercover_first_octant_only(gridsquare1_, gridsquare2_):
	assert gridsquare0_.sys == gridsquare1_.sys
	gridsquaresys = gridsquare0_.sys

	r = []

	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat
	x2 = gridsquare2_.gridlng; y2 = gridsquare2_.gridlat
	assert x1 <= x2 and y1 <= y2 and y2-y1 <= x2-x1

	def ret(x__, y__):
		r.append(grid.GridSquare.from_ints(y__, x__, gridsquaresys))

	x = x1
	y = y1
	dx = x2-x1
	dy = y2-y1

	ret(x1, y1)

	ddy = 2 * dy
	ddx = 2 * dx

	errorprev = error = dx
	for i in range(dx):
		x += 1
		error += ddy
		if error > ddx:
			y += 1
			error -= ddx
			if error + errorprev < ddx:
				ret(x, y-1)
			elif error + errorprev > ddx:
				ret(x-1, y)
			else:
				ret(x, y-1)
				ret(x-1, y)
		ret(x, y)
		errorprev = error

	assert (y == y2) and (x == x2)

	return r
	
# Returns shortest path, as one (dist, path) pair.   
# If no path is possible, both 'dist' and the Path will be None. 
# 'path' is a list of vertexes. 
# Thanks to http://en.wikipedia.org/wiki/Dijkstra's_algorithm 
def dijkstra(srcvertex_, dest_, all_vertexes_, get_connected_vertexndists_, out_visited_vertexes=None):
	assert srcvertex_ in all_vertexes_
	assert (out_visited_vertexes is None) or isinstance(out_visited_vertexes, set)

	if dest_ is None:
		singledest = False; destlist = False
	elif is_seq_of(dest_, Vertex):
		singledest = False; destlist = True
	elif dest_ in all_vertexes_:
		singledest = True; destlist = False
	else:
		assert False

	class VertexInfo(object):
		def __init__(self):
			self.dist = float('inf')
			self.visited = False
			self.previous = None

	info = dict((vertex, VertexInfo()) for vertex in all_vertexes_)
	info[srcvertex_].dist = 0.0
	q = set([srcvertex_])
	while len(q) > 0:
		u = min((vertex for vertex, info in info.iteritems() if not info.visited), key=lambda vertex: info[vertex].dist)
		if singledest and (u == dest_):
			break
		elif destlist and (u in dest_) and all(info[v].visited for v in dest_ if v != u):
			break
		q.remove(u)
		info[u].visited = True
		for v, vdist in get_connected_vertexndists_(u):
			alt = info[u].dist + vdist
			if alt < info[v].dist and not info[v].visited:
				info[v].dist = alt
				info[v].previous = u
				q.add(v)

	if singledest:
		if out_visited_vertexes is not None:
			out_visited_vertexes.update([vert for vert, vertinfo in info.iteritems() if vertinfo.visited])

		if info[dest_].dist == float('inf'):
			return (None, None)
		else:
			path = []
			u = dest_
			while info[u].previous is not None:
				path.insert(0, u)
				u = info[u].previous
			path.insert(0, srcvertex_)
			return (info[dest_].dist, path)
	else:
		return {vert: info[vert].dist for vert in (dest_ if destlist else info.iterkeys())}

# Returns a single (dist, pathsteps) pair if k==1.
# 	otherwise returns a list of (dist, pathsteps) pairs.
# The A* path-finding algorithm.  Thanks to http://en.wikipedia.org/wiki/A*_search_algorithm
# This version assumes, and exploits, a monotonic heuristic function. 
def a_star(srcvertex_, destvertex_, all_vertexes_, get_connected_vertexndists_, heuristic_cost_estimate_, 
		k=None, out_visited_vertexes=None, log=False):
	assert is_yen_k_simple(k)
	assert (out_visited_vertexes is None) or isinstance(out_visited_vertexes, set)
	closedset = set() # The set of nodes already evaluated.
	came_from = {} # The map of navigated nodes.

	# Cost from start along best known path:
	g_score = {srcvertex_: 0}
	# Estimated total cost from srcvertex_ to destvertex_ through y:
	f_score = {srcvertex_: heuristic_cost_estimate_(srcvertex_, destvertex_)}
	# The set of tentative nodes to be evaluated, initially containing the start node: 
	openset = set([srcvertex_])

	while len(openset) > 0:
		current = min(openset, key=lambda v: f_score[v])
		if current == destvertex_:
			path = [destvertex_]
			while path[0] in came_from:
				path.insert(0, came_from[path[0]])
			r = (g_score[destvertex_], path)
			if k not in (1, None):
				r = yen_k_shortest_path(k, r[0], r[1], srcvertex_, destvertex_, 
						all_vertexes_, get_connected_vertexndists_, heuristic_cost_estimate_, 
						out_visited_vertexes=out_visited_vertexes, log=log)
			if out_visited_vertexes is not None:
				out_visited_vertexes |= closedset
			return r
 
		openset.remove(current)
		closedset.add(current)
		for neighbor, current_to_neighbor_edge_dist in get_connected_vertexndists_(current):
			if neighbor in closedset:
				continue
			tentative_g_score = g_score[current] + current_to_neighbor_edge_dist

			if (neighbor not in openset) or (tentative_g_score < g_score[neighbor]):
				came_from[neighbor] = current
				g_score[neighbor] = tentative_g_score
				f_score[neighbor] = g_score[neighbor] + heuristic_cost_estimate_(neighbor, destvertex_)
				openset.add(neighbor)

	if out_visited_vertexes is not None:
		out_visited_vertexes |= closedset

	return ((None, None) if k in (1, None) else [(None, None)])

# arg k_ if int: interpret simply as 'get k shortest paths'. 
#	       if float: interpret as 'keep finding a next-shortest path until the length of it 
#	                 is greater than k_*(length of absolute shortest path).
#	                 So you should only pass in a k_ > 1.0. 
# return value is a list of (dist, pathsteps) pairs, sorted by increasing dist.
# 	It includes the already-computed shortest path that is given as arguments to this function. 
# Algorithm thanks to http://en.wikipedia.org/wiki/Yen%27s_algorithm 
def yen_k_shortest_path(k_, shortest_dist_, shortest_path_, srcvertex_, destvertex_, 
		all_vertexes_, get_connected_vertexndists_, heuristic_cost_estimate_, 
		out_visited_vertexes=None, log=False):
	assert k_ not in (1, None) and is_yen_k_simple(k_)
	if srcvertex_ == destvertex_:
		return [(shortest_dist_, shortest_path_)]
	A = [(shortest_dist_, shortest_path_, 0)]
	# Initialize the heap to store the potential kth shortest path.
	B = []
	
	k = 1
	while True:
		if yen_should_stop_because_of_kint(A, k_):
			break

		prevPath = A[k - 1][1]
		prevPathEdgeDists = [0]
		for step1, step2 in hopscotch(prevPath):
			edgeDist = min(x[1] for x in get_connected_vertexndists_(step1) if x[0] == step2)
			prevPathEdgeDists.append(edgeDist)
		assert len(prevPath) == len(prevPathEdgeDists)

		# In the simple version of Yen, the spur node ranges from the first node to the next to last 
		# node in the previous k-shortest path.  But for performance, we use Lawler's modification, which 
		# might skip the first few spur nodes and starts the spurring at the spur part of prevPath 
		# (that is, the place in prevPath where /it/ spurred from /it's/ previous path.)
		prevPathSpurNodeIdx = A[k - 1][2]
		for i in range(prevPathSpurNodeIdx, len(prevPath)-1):
			# Spur node is retrieved from the previous k-shortest path, k - 1.
			spurNode = prevPath[i]

			# The sequence of nodes from the source to the spur node of the previous k-shortest path.
			rootPath = prevPath[:i+1]
			rootPath = (sum(prevPathEdgeDists[:i+1]), rootPath)
			
			edges_to_omit = set()
			for p in [x[1] for x in A]:
				if rootPath[1] == p[:i+1]:
					# Remove the links that are part of the previous shortest paths which share the same root path.
					edges_to_omit.add((p[i], p[i+1]))

			if log: printerr('k=%d, rootPath=%s, spurNode=%s -----' % (k, rootPath[1], spurNode))
			if log: printerr('omitting: %s' % edges_to_omit)
			def get_connected_vertexndists(vert__):
				r = get_connected_vertexndists_(vert__)
				if log:
					printerr('connected to %s (before omissions):' % vert__)
					for vert, dist in r:
						printerr('\t%s' % vert)
					prev_len_r = len(r)
				r = [x for x in r if (vert__, x[0]) not in edges_to_omit]

				# Omit nodes that are in the root path.  
				# This part is not in the wikipedia pseudocode but seems to be in the original paper 
				# (http://people.csail.mit.edu/minilek/yen_kth_shortest.pdf page 714 - 
				# "without passing any node that is already included in the first part of the path") 
				# and we'll get looping paths that we don't want if this code is not here. 
				r = [x for x in r if x[0] not in rootPath[1][:-1]]

				if log:
					printerr('connected to %s (after omissions):' % vert__)
					for vert, dist in r:
						printerr('\t%s' % vert)
					printerr('(omitted %d edges this time (total edges to omit: %d))' % (prev_len_r - len(r), len(edges_to_omit)))
				return r

			# Calculate the spur path from the spur node to the sink.
			spurPath = a_star(spurNode, destvertex_, all_vertexes_, get_connected_vertexndists, heuristic_cost_estimate_, 
					out_visited_vertexes=out_visited_vertexes)

			# Entire path is made up of the root path and spur path.
			if log: printerr('omitting:', edges_to_omit)
			if log: printerr('got spurPath for spurNode %s: %s' % (spurNode, spurPath))
			if spurPath[0] is not None:
				assert spurPath[1] is not None
				totalPath = (rootPath[0] + spurPath[0], rootPath[1] + spurPath[1][1:], len(rootPath[1])-1)
				# Add the potential k-shortest path to the heap.
				B.append(totalPath)

		if len(B) == 0:
			break
		# Sort the potential k-shortest paths by cost.
		B.sort(key=lambda x: x[0])
		# Add the lowest cost path becomes the k-shortest path.
		shortest_in_B = B.pop(0)
		if yen_should_stop_because_of_kfloat(A, shortest_in_B, k_):
			break
		if log: printerr('adding to A: %s' % (shortest_in_B,))
		A.append(shortest_in_B)
		k += 1

	return [x[:2] for x in A]

def is_yen_k_valid(k_):
	if k_ is None:
		return True
	else:
		r = isinstance(k_, int) or isinstance(k_, float) or is_seq_like(k_, (0, 0.0)) or is_seq_like(k_, (0, 0, 0.0, 0.0))

		def get_ints():
			rints = []
			if isinstance(k_, int):
				rints.append(k_)
			elif is_seq_like(k_, (0, 0.0)):
				rints.append(k_[0])
			elif is_seq_like(k_, (0, 0, 0.0, 0.0)):
				rints.append(k_[0])
				rints.append(k_[1])
			return rints

		def get_floats():
			rfloats = []
			if isinstance(k_, float):
				rfloats.append(k_)
			elif is_seq_like(k_, (0, 0.0)):
				rfloats.append(k_[1])
			elif is_seq_like(k_, (0, 0, 0.0, 0.0)):
				rfloats.append(k_[2])
				rfloats.append(k_[3])
			return rfloats

		r &= all(kint >= 1 for kint in get_ints()) and all(kfloat >= 1.0 for kfloat in get_floats())
			
		if r and is_seq_like(k_, (0, 0, 0.0, 0.0)):
			r &= (k_[0] >= k_[1]) and (k_[2] >= k_[3])

		return r

# 'simple' here means either an int or a float or an (int, float) pair.  Not a (int, int, float, float) tuple.
def is_yen_k_simple(k_):
	return k_ is None or isinstance(k_, int) or isinstance(k_, float) or is_seq_like(k_, (0, 0.0))

# if k_ is a 4-tuple, then we only enforce the first pass part.
def yen_should_stop_because_of_kint(distsnpaths_so_far_, k_):
	assert is_yen_k_simple(k_)
	if isinstance(k_, int) or is_seq_like(k_, (0, 0.0)) or is_seq_like(k_, (0, 0, 0.0, 0.0)):
		if isinstance(k_, int):
			kint = k_
		else:
			kint = k_[0]
		return (len(distsnpaths_so_far_) >= kint)
	else:
		return False
	
# if k_ is a 4-tuple, then we only enforce the first pass part.
def yen_should_stop_because_of_kfloat(distsnpaths_so_far_, latest_candidate_distnpath_, k_):
	assert is_yen_k_simple(k_)
	assert is_sorted(distsnpaths_so_far_, key=lambda e: e[0])
	if isinstance(k_, float) or is_seq_like(k_, (0, 0.0)) or is_seq_like(k_, (0, 0, 0.0, 0.0)):
		if isinstance(k_, float):
			kfloat = k_
		else:
			kfloat = k_[1]
		return (latest_candidate_distnpath_[0] > distsnpaths_so_far_[0][0]*kfloat)
	else:
		return False

def get_yen_k_firstpass(k_):
	assert is_yen_k_valid(k_)
	if k_ is None:
		return None
	elif is_yen_k_simple(k_):
		return k_
	else:
		return (k_[0], k_[2])

def yen_reduce_list_according_to_k(distsnpaths_, k_):
	assert is_yen_k_valid(k_)
	assert is_sorted(distsnpaths_, key=lambda e: e[0])
	if k_ is not None and len(distsnpaths_):
		kint, kfloat = get_yen_int_and_float(k_)
		shortest_dist = distsnpaths_[0][0]
		new_distsnpaths = []
		for i, (dist, path) in enumerate(distsnpaths_):
			if kint is not None and i >= kint:
				break
			elif kfloat is not None and dist > shortest_dist*kfloat:
				break
			new_distsnpaths.append((dist, path))
		distsnpaths_[:] = new_distsnpaths

def get_yen_int_and_float(k_):
	if isinstance(k_, int):
		return (k_, None)
	elif isinstance(k_, float):
		return (None, k_)
	elif is_seq_like(k_, (0, 0.0)):
		return (k_[0], k_[1])
	else:
		raise Exception('Invalid yen k: %s' % k_)

def get_dist_from_pathsteps(pathsteps_, get_connected_vertexndists_):
	r = 0.0
	for step1, step2 in hopscotch(pathsteps_):
		r += min(x[1] for x in get_connected_vertexndists_(step1) if x[0] == step2)
	return r

def graph_locs_to_json_str(locs_):
	if locs_ is None:
		return json.dumps(None)
	else:
		output_list = []
		for loc in locs_:
			if isinstance(loc, PosAddr):
				output_e = [loc.plinename, loc.ptidx, loc.pals]
			elif isinstance(loc, Vertex):
				output_e = loc.name
			else:
				raise Exception()
			output_list.append(output_e)
		return json.dumps(output_list, separators=(',',':'))

def parse_graph_locs_json_str(str_, sg_):
	obj = json.loads(str_)
	assert isinstance(obj, Sequence)
	r = []
	for e in obj:
		if isinstance(e, basestring):
			output_loc = sg_.get_vertex(e)
			if output_loc is None:
				raise Exception('vertex name %s was in graph_locs json string, but not in snapgraph.' % e)
		else:
			output_loc = PosAddr(PtAddr(e[0], e[1]), e[2])
		r.append(output_loc)
	return tuple(r)

def set_plinename_weight(plinename_, weight_):
	assert isinstance(plinename_, str) and isinstance(weight_, float) and (weight_ > 0) and (round(weight_, 2) == weight_)
	splits = plinename_.split(';')
	splits = [split for split in splits if not split.startswith('w=')]
	if weight_ != 1.0:
		splits.append('w=%.2f' % weight_)
	return ';'.join(splits)

def get_weight_from_plinename(plinename_):
	params = plinename_.split(';')[1:]
	for param in params:
		if param.startswith('w='):
			return float(param[len('w='):])
	else:
		return 1.0

def set_plinename_walking(plinename_):
	splits = plinename_.split(';')
	if 'walk' in splits:
		return plinename_
	else:
		splits.append('walk')
		return ';'.join(splits)

def add_suffix_to_plinename(plinename_, suffix_):
	splits = plinename_.split(';')
	splits[0] += suffix_
	return ';'.join(splits)

def get_base_plinename(plinename_):
	return plinename_.split(';')[0]

def has_flag(name_, flag_):
	assert len(name_) > 0 and len(flag_) == 1
	if not name_.startswith('('):
		return False
	else:
		for char in name_[1:]:
			if char == ')':
				return False
			elif char == flag_:
				return True
		assert False

def add_flag(name_, flag_):
	assert len(name_) > 0 and len(flag_) == 1
	if not name_.startswith('('):
		return '(%s)%s' % (flag_, name_)
	elif has_flag(name_, flag_):
		return name_
	else:
		return '(%s%s' % (flag_, name_[1:])

def get_vertex_limit_zones_from_yaml_file(yaml_filename_):

	with open(yaml_filename_) as fin:
		raw_zone_dict_list = yaml.load(fin)
	r = []
	for raw_zone_dict in raw_zone_dict_list:
		r.append(VertexLimitZone.from_raw_dict(raw_zone_dict))
	return r

class VertexLimitZone(object):

	def __init__(self, ideal_vert_latlng_, zone_poly_):
		assert (ideal_vert_latlng_ is None or isinstance(ideal_vert_latlng_, geom.LatLng))
		assert is_seq_of(zone_poly_, geom.LatLng)
		self.ideal_vert_latlng = ideal_vert_latlng_
		self.zone_poly = zone_poly_

	@classmethod
	def from_raw_dict(cls_, raw_dict_):
		return cls_(geom.LatLng.make(raw_dict_['ideal_vert_latlng']), [geom.LatLng(rawpt) for rawpt in raw_dict_['zone_poly']])

	def __str__(self):
		return 'VertexLimitZone(%s, %s)' % (self.ideal_vert_latlng, self.zone_poly)

	def __repr__(self):
		return self.__str__()

def parse_posaddr(str_):
	r = str_.strip()
	if r.startswith('PosAddr'):
		r = r[len('PosAddr'):]
	assert r[0] == '(' and r[-1] == ')'
	r = '[' + r[1:-1] + ']'
	r = r.replace('\'', '"');
	try:
		r = json.loads(r)
		if not is_seq_like(r, (u'', 0, 0.0)):
			return None
		if len(r[0]) == 0 or r[1] < 0 or not (0.0 <= r[2] <= 1.0):
			return None
		return PosAddr(PtAddr(str(r[0]), r[1]), r[2]) # Converting from unicode to basic string, for our convenience. 
	except ValueError:
		return None

if __name__ == '__main__':

	pass



