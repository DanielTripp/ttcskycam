#!/usr/bin/python2.6

from collections import defaultdict, Sequence
from itertools import *
import pprint, math, json
from lru_cache import lru_cache
import geom, mc, c
from misc import *

# Some vocabulary: 
# A Vertex is a vertex in the graph theory sense. 
# A PosAddr represents a location on an edge of the graph.  It is represented in terms of a line segment address and a 
# 	percentage along that line segment. 
# A 'location' has no corresponding class, but is used in some function arguments to describe an object which could be a 
# 	vertex or a posaddr. 

LATSTEP = 0.00175; LNGSTEP = 0.0025

if 1: # TODO: deal with this.  make up mind.
	fact = 2
	LATSTEP /= fact
	LNGSTEP /= fact

# Grid squares are offset from a point that has no large importance, it just makes for more easily
# readable values during debugging:
LATREF = 43.62696696859263; LNGREF = -79.4579391022553

# in meters
DEFAULT_GRAPH_VERTEX_DIST_TOLERANCE = 0.5

# I got this '3' by trial and error.  It's not a precise issue, at least not at my level of understanding.  
# I tried different values for this until I got the results that I wanted. 
PATHS_GPS_ERROR_FACTOR=3

def lat_to_gridlat(lat_):
	return fdiv(lat_ - LATREF, LATSTEP)

def gridlat_to_lat(gridlat_):
	return gridlat_*LATSTEP + LATREF

def lng_to_gridlng(lng_):
	return fdiv(lng_ - LNGREF, LNGSTEP)

def gridlng_to_lng(gridlng_):
	return gridlng_*LNGSTEP + LNGREF

# Supposed to be immutable. 
class GridSquare(object):

	def __init__(self, arg_):
		if isinstance(arg_, geom.LatLng):
			self.gridlat = lat_to_gridlat(arg_.lat)
			self.gridlng = lng_to_gridlng(arg_.lng)
		else:
			self.gridlat = arg_[0]
			self.gridlng = arg_[1]

	def __eq__(self, other):
		return (self.gridlat == other.gridlat) and (self.gridlng == other.gridlng)

	def __hash__(self):
		return self.gridlat + self.gridlng

	def __str__(self):
		return '(%d,%d)' % (self.gridlat, self.gridlng)

	def __repr__(self):
		return self.__str__()

	def latlng(self):
		return geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))

	def corner_latlngs(self):
		r = []
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng+1)))
		return r

	def center_latlng(self):
		sw = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1))
		return sw.avg(ne)

	def diagonal_dist_m(self):
		sw = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1))
		return sw.dist_m(ne)

# Identifies a point or a line segment within a list of polylines - in particular, within 
# the SnapGraph.polylines field - via list indices.  
# Whether this identifies a line segment or a point will depend on the context.  
# If it addresses a line segment, then the ptidx field of this class will identify 
# the /first/ point of the line segment (as it appears in SnapGraph.polylines).  
class PtAddr(object):

	def __init__(self, polylineidx_, ptidx_):
		self.polylineidx = polylineidx_
		self.ptidx = ptidx_

	def __eq__(self, other):
		return (self.polylineidx == other.polylineidx) and (self.ptidx == other.ptidx)

	def __hash__(self):
		return self.polylineidx + self.ptidx

	def __str__(self):
		return 'PtAddr(%d,%d)' % (self.polylineidx, self.ptidx)

	def __repr__(self):
		return self.__str__()

	def __cmp__(self, other):
		cmp1 = cmp(self.polylineidx, other.polylineidx)
		if cmp1 != 0:
			return cmp1
		else:
			return cmp(self.ptidx, other.ptidx)

	def copy(self):
		return PtAddr(self.polylineidx, self.ptidx)

class Vertex(object):

	next_id = 0

	# Creating a new vertex that will very likely be added to.  
	# Could be seen as mutable. 
	@classmethod
	def create_open(cls_, snapgraph_):
		r = cls_()
		r.id = cls_.next_id
		cls_.next_id += 1
		r.snapgraph = snapgraph_
		r.ptaddrs = set() # starts off as a set, but will be a sorted list after this object is completely built. 
		r.is_closed = False
		return r

	def set_closed(self):
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

	# arg polylineidx_: None ==> first polyline appearing in this vertex.  Whatever 'first' means.  Arbitrary.  Random.  Any.
	def get_ptaddr(self, polylineidx_=None):
		if polylineidx_ is None:
			return self.ptaddrs[0]
		else:
			ptaddrs = [ptaddr for ptaddr in self.ptaddrs if ptaddr.polylineidx == polylineidx_]
			if len(ptaddrs) != 1:
				plineidxes = [ptaddr.polylineidx for ptaddr in self.ptaddrs]
				plineidx_to_pts = dict((plineidx, self.snapgraph.polylines[plineidx]) for plineidx in plineidxes)
				raise Exception('Problem around %s, polyline %d (%s) - %s, %s' \
						% (self, polylineidx_, ptaddrs, self.ptaddrs, plineidx_to_pts))
			return ptaddrs[0]

	def get_posaddr(self, plineidx_):
		return PosAddr(self.get_ptaddr(plineidx_), 0.0)

	def get_ptidx(self, polylineidx_):
		return self.get_ptaddr(polylineidx_).ptidx

	def remove_unnecessary_ptaddrs(self):
		assert isinstance(self.ptaddrs, set)
		vertex_mean_pos = geom.latlng_avg([self.snapgraph.get_latlng(ptaddr) for ptaddr in self.ptaddrs])
		assert not self.is_closed
		for plineidx in set(ptaddr.polylineidx for ptaddr in self.ptaddrs):
			ptidxes = [ptaddr.ptidx for ptaddr in self.ptaddrs if ptaddr.polylineidx == plineidx]
			if len(ptidxes) > 1:
				for ptidxgroup in get_maximal_sublists2(ptidxes, lambda ptidx1, ptidx2: abs(ptidx1-ptidx2)==1):
					dist_to_mean_pos = lambda ptidx: self.snapgraph.get_latlng(PtAddr(plineidx,ptidx)).dist_m(vertex_mean_pos)
					chosen_ptidx = min(ptidxgroup, key=dist_to_mean_pos)
					self.ptaddrs = set([ptaddr for ptaddr in self.ptaddrs if ptaddr.polylineidx != plineidx or ptaddr.ptidx == chosen_ptidx])

	# Returns any polylines that are mentioned more than once in this vertex. 
	def get_looping_polylineidxes(self):
		r = set()
		for ptaddr1 in self.ptaddrs:
			if len([ptaddr2 for ptaddr2 in self.ptaddrs if ptaddr2.polylineidx == ptaddr1.polylineidx]) > 1:
				r.add(ptaddr1.polylineidx)
		return r

	def __cmp__(self, other):
		return cmp(self.__class__.__name__, other.__class__.__name__) or cmp(self.id, other.id)

	def __hash__(self):
		return self.id

	def __eq__(self, other):
		return isinstance(other, Vertex) and (self.id == other.id)

	def __str__(self):
		return 'Vertex(id:%d)' % (self.id)

	def __repr__(self):
		return self.__str__()

	def to_json_dict(self):
		return {'id': self.id, 'pos': self.pos(), 
				'ptaddrs': [[addr.polylineidx, addr.ptidx] for addr in self.ptaddrs], 
				'connectedids': [vert_n_dist[0].id for vert_n_dist in self.snapgraph.vertex_to_connectedvertex_n_dists[self]]}

	def get_shortest_common_plineidx(self, other_):
		assert self.snapgraph is other_.snapgraph
		plineidxes = set(ptaddr.polylineidx for ptaddr in self.ptaddrs) & set(ptaddr.polylineidx for ptaddr in other_.ptaddrs)
		if len(plineidxes) == 0:
			raise Exception('No plines in common between %s and %s' % (self, other_))
		elif len(plineidxes) == 1:
			return anyelem(plineidxes)
		else:
			def key(plineidx__):
				self_ptidx = self.get_ptidx(plineidx__)
				other_ptidx = other_.get_ptidx(plineidx__)
				return self.snapgraph.get_dist_between_points(plineidx__, self_ptidx, other_ptidx)
			return min(plineidxes, key=key)

class PosAddr(object):

	def __init__(self, linesegaddr_, pals_):
		assert (isinstance(linesegaddr_, PtAddr) or is_seq_like(linesegaddr_, (0, 0))) and isinstance(pals_, float)
		linesegaddr = (linesegaddr_ if isinstance(linesegaddr_, PtAddr) else PtAddr(linesegaddr_[0], linesegaddr_[1]))
		assert 0.0 <= pals_ <= 1.0
		if pals_ == 1.0: # Normalizing so that self.pals will be between 0.0 and 1.0 inclusive / exclusive.  
			# Saves us from writing code to that effect elsewhere. 
			self.linesegaddr = PtAddr(linesegaddr.polylineidx, linesegaddr.ptidx+1)
			self.pals = 0.0
		else:
			self.linesegaddr = linesegaddr
			self.pals = pals_
		assert 0.0 <= self.pals < 1.0

	def __str__(self):
		assert 0.0 <= self.pals < 1.0
		return 'PosAddr(%s,%.3f)' % (self.linesegaddr, self.pals)

	def __hash__(self):
		return hash(self._key())

	def __eq__(self, other):
		return isinstance(other, PosAddr) and (self._key() == other._key())

	def _key(self):
		return (self.linesegaddr, self.pals)

	def __cmp__(self, other):
		return cmp(self.__class__.__name__, other.__class__.__name__) or cmp(self._key(), other._key())

	def __repr__(self):
		return self.__str__()

	def copy(self):
		return PosAddr(self.linesegaddr.copy(), self.pals)

# Vocabulary: a Path has one or more 'pieces'.  
# 	A 'piece' is a list of 'steps' (1 or more).  
#		A 'step' is a PosAddr or a Vertex. 
class Path(object):
	
	def __init__(self, piecestepses_, snapgraph_, snap_tolerance_):
		assert isinstance(piecestepses_, Sequence)
		for piecesteps in piecestepses_:
			assert self.is_piece_valid(piecesteps)
		assert isinstance(snapgraph_, SnapGraph)
		self.piecestepses = piecestepses_
		self.pieces = [None]*len(self.piecestepses)
		self.snapgraph = snapgraph_
		self.snap_tolerance = snap_tolerance_

	@staticmethod
	def is_piece_valid(steps_):
		if len(steps_) < 1:
			return False
		if not ((isinstance(e, PosAddr) or isinstance(e, Vertex) for e in steps_)):
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
			if isinstance(step1, PosAddr) and isinstance(step2, Vertex):
				plineidx = step1.linesegaddr.polylineidx
				step1_ptidx = step1.linesegaddr.ptidx
				vert_ptidx = step2.get_ptidx(plineidx)
				step1_ptidx += (1 if step1_ptidx < vert_ptidx else 0)
				r += sliceii(self.snapgraph.polylines[plineidx], step1_ptidx, vert_ptidx)[:-1] + [step2.pos()]
			elif isinstance(step1, Vertex) and isinstance(step2, Vertex):
				plineidx = step1.get_shortest_common_plineidx(step2)
				step1_ptidx = step1.get_ptidx(plineidx)
				step2_ptidx = step2.get_ptidx(plineidx)
				r += [step1.pos()] + sliceii(self.snapgraph.polylines[plineidx], step1_ptidx, step2_ptidx)[1:-1] + [step2.pos()]
			elif isinstance(step1, Vertex) and isinstance(step2, PosAddr):
				plineidx = step2.linesegaddr.polylineidx
				step2_ptidx = step2.linesegaddr.ptidx
				vert_ptidx = step1.get_ptidx(plineidx)
				step2_ptidx += (1 if step2_ptidx < vert_ptidx else 0)
				r += [step1.pos()] + sliceii(self.snapgraph.polylines[plineidx], vert_ptidx, step2_ptidx)[1:]
			elif isinstance(step1, PosAddr) and isinstance(step2, PosAddr):
				r += self.snapgraph.get_pts_between(step1, step2)
			else:
				raise Exception()
			if isinstance(step2, PosAddr):
				r += [self.snapgraph.get_latlng(step2)] 
		return uniq(r)

	def piece_latlngs(self):
		assert len(self.piecestepses) > 0
		r = []
		for piecesteps in self.piecestepses:
			assert len(piecesteps) >= 2
			curpiece_firststep = piecesteps[0]
			r.append(self.snapgraph.get_latlng(curpiece_firststep))
		lastpiece_laststep = self.piecestepses[-1][-1]
		r.append(self.snapgraph.get_latlng(lastpiece_laststep))
		return r

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

	def __init__(self, path_, pieceidx_, streetsg_):
		assert len(path_.piecestepses[pieceidx_]) > 0
		self.path = path_
		if len(self.path.piecestepses[pieceidx_]) == 1:
			self.is_zero_length = True
			self.zero_length_latlng = path_.latlngs(pieceidx_)[0]
			self.zero_length_heading = self._get_zero_length_heading(pieceidx_, streetsg_)
		else:
			self.is_zero_length = False
			self.sg = SnapGraph([path_.latlngs(pieceidx_)], forsnaps=False, forpaths=False)

	def _get_zero_length_heading(self, pieceidx_, streetsg_):
		cur_step = self.path.piecestepses[pieceidx_][0]
		cur_latlng = streetsg_.get_latlng(cur_step)

		prev_latlng = None
		for prev_pieceidx in range(pieceidx_-1, -1, -1):
			prev_piecesteps = self.path.piecestepses[prev_pieceidx]
			if len(self.path.piecestepses[prev_pieceidx]) > 1:
				prev_latlng = self.path.latlngs(prev_pieceidx)[-2]
				break

		if prev_latlng is not None:
			return prev_latlng.heading(cur_latlng)
		else:
			# If we're here then we don't have much to go on.  
			# This is a guess, and it will be wrong at least half the time. 
			if isinstance(cur_step, PosAddr):
				linesegaddr = cur_step.linesegaddr
			else:
				assert isinstance(cur_step, Vertex)
				linesegaddr = cur_step.get_ptaddr()
			return streetsg_.heading(linesegaddr, False)

	def length_m(self):
		if self.is_zero_length:
			return 0.0
		else:
			return self.sg.get_pline_len(0)

	# arg mapl_: should be a float between 0.0 and self.length_m() inclusive, or the string 'max'. 
	def mapl_to_latlonnheading(self, mapl_):
		if mapl_ == 'max':
			mapl = self.length_m()
		else:
			mapl = mapl_
		if self.is_zero_length:
			if mapl != 0.0:
				raise Exception()
			return (self.zero_length_latlng, self.zero_length_heading)
		else:
			return self.sg.mapl_to_latlonnheading(0, mapl)

# This can be pickled or memcached. 
class SnapGraph(object):

	# arg polylines_: We might modify this, if 'forpaths' is true.  We might split some line segments, where they 
	# 	intersect other line segments.  We will not join polylines or remove any points. 
	# arg forpaths_disttolerance: Two points need to be less than this far apart for us to consider them 
	# 	coincident AKA the same point, for our path-graph purposes. 
	def __init__(self, polylines_, forsnaps=True, forpaths=True, forpaths_disttolerance=DEFAULT_GRAPH_VERTEX_DIST_TOLERANCE, name=None):
		assert isinstance(polylines_[0][0], geom.LatLng)
		self.name = name
		self.latstep = LATSTEP; self.lngstep = LNGSTEP; self.latref = LATREF; self.lngref = LNGREF
		self.polylines = polylines_
		if forsnaps:
			self.init_gridsquare_to_linesegaddrs()
		if forpaths:
			self.init_path_structures(forpaths_disttolerance)
			self.init_gridsquare_to_linesegaddrs() # rebuilding it because for those 
				# linesegs that were split within init_path_structures() - 
				# say lineseg A was split into A1 and A2, and A covered the sets of 
				# gridsquares S.  after init_path_structures() is done, 
				# self.gridsquare_to_linesegaddrs will be such that A1 is portrayed as 
				# covering all of S, and so does A2.  This is of course too wide a net 
				# in many cases - I think if the original start point, the original end 
				# point, and the split point, are in 3 different gridsquares.  
				# init_path_structures() does this because the code is easier to write.  
				# But now we can make it better by rebuilding it. 
		else:
			# We want to build this even if 'forpaths' is false, because get_mapl() 
			# depends on it, and we want get_mapl() to be available even if 
			# 'forpaths' is false.  If 'forpaths' is true, then this is built at a 
			# sensitive time, elsewhere (after the intersections of line segments are 
			# found and the line segments split appropriately, but before the 
			# distance-between-vertexes info is built.)
			self.init_polylineidx_to_ptidx_to_mapl()

	def __str__(self):
		return 'SnapGraph(%s)' % (self.name if self.name is not None else id(self))

	# return list of (dist, pathsteps) pairs.  Dist is a float, in meters.   List is sorted in ascending order of dist. 
	@lru_cache(maxsize=60000, posargkeymask=[1,1,0,1,0])
	def find_paths(self, startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance=100, out_visited_vertexes=None):
		assert out_visited_vertexes is None # (temporarily?) unsupported due to caching of return value based on arguments. 

		# We could almost decorate this function with mc.decorate instead of calling mc.get() ourselves, 
		# but that's won't quite work, because we can't store anything with a reference to a SnapGraph object to in memcache, 
		# because they're large.  Vertexes have those.  So we will nullify those references before the result is put 
		# into memcache, and un-nullify them before we return from this function.
		# It probably wouldn't be that hard to make Vertex not have a reference to it's owner snapgraph.  Maybe later.

		def set_sg_of_vertexes(r__, sg__):
			for dist, pathsteps in r__:
				for pathstep in pathsteps:
					if isinstance(pathstep, Vertex):
						pathstep.snapgraph = sg__

		assert self.name is not None
		def find_paths_and_nullify_vertex_sgs(sgname__, startlatlng__, startlocs__, destlatlng__, destlocs__, snap_tolerance__=100):
			r = self.find_paths_impl(startlatlng__, startlocs__, destlatlng__, destlocs__, snap_tolerance=snap_tolerance__)
			set_sg_of_vertexes(r, None)
			return r

		r = mc.get(find_paths_and_nullify_vertex_sgs, 
				[self.name, startlatlng_, startlocs_, destlatlng_, destlocs_], {'snap_tolerance__': snap_tolerance}, posargkeymask=[1,1,0,1,0])
		set_sg_of_vertexes(r, self)
		return r

	def find_paths_impl(self, startlatlng_, startlocs_, destlatlng_, destlocs_, snap_tolerance=c.GRAPH_SNAP_RADIUS, out_visited_vertexes=None):
		assert out_visited_vertexes is None # (temporarily?) unsupported due to caching of return value based on arguments. 
		start_locs = (startlocs_ if startlocs_ is not None else self.multisnap(startlatlng_, snap_tolerance))
		dest_locs = (destlocs_ if destlocs_ is not None else self.multisnap(destlatlng_, snap_tolerance))
		if not(start_locs and dest_locs):
			return []
		else:
			dists_n_paths = []
			for start_loc, dest_loc in product(start_locs, dest_locs):
				# Multiplying these by a certain factor because otherwise some strange choices will be made for shortest path 
				# when going around corners.  I don't know how to explain this in comments, without pictures. 
				start_latlng_to_loc_dist = self.get_latlng(start_loc).dist_m(startlatlng_)*PATHS_GPS_ERROR_FACTOR
				dest_latlng_to_loc_dist = self.get_latlng(dest_loc).dist_m(destlatlng_)*PATHS_GPS_ERROR_FACTOR
				dist, path = self.find_path_by_locs(start_loc, dest_loc, out_visited_vertexes)
				if dist is not None:
					dist += start_latlng_to_loc_dist + dest_latlng_to_loc_dist
					dists_n_paths.append((dist, path))
			dists_n_paths.sort(key=lambda e: e[0])
			return dists_n_paths

	# return A (dist, Path) pair, or (None, None) if no path is possible.  'dist' is a float, in meters.   
	def find_multipath(self, latlngs_, locses=None, snap_tolerance=c.GRAPH_SNAP_RADIUS, log_=False):
		if len(latlngs_) < 2:
			raise Exception()
		our_locses = ([self.multisnap(latlng, snap_tolerance) for latlng in latlngs_] if locses is None else locses)
		assert len(our_locses) == len(latlngs_)
		if len(latlngs_) == 2:
			dists_n_pieces = self.find_paths(latlngs_[0], our_locses[0], latlngs_[1], our_locses[1])
			if len(dists_n_pieces) > 0:
				return (dists_n_pieces[0][0], Path([dists_n_pieces[0][1]], self, snap_tolerance))
			else:
				return (None, None)
		else:
			r_dist = 0
			r_pieces = []
			for idx_a, latlng_a, idx_b, latlng_b, idx_c, latlng_c in hopscotch_enumerate(latlngs_, 3):
				locs_a = our_locses[idx_a]; locs_b = our_locses[idx_b]; locs_c = our_locses[idx_c]
				if idx_a == 0:
					dists_n_pieces_ab = self.find_paths(latlng_a, locs_a, latlng_b, locs_b)
				dists_n_pieces_bc = self.find_paths(latlng_b, locs_b, latlng_c, locs_c)
				combined_dists_n_pieces = []
				for dist_n_piece_ab, dist_n_piece_bc in product(dists_n_pieces_ab, dists_n_pieces_bc):
					if dist_n_piece_ab[1][-1] == dist_n_piece_bc[1][0]:
						combined_dists_n_pieces.append((dist_n_piece_ab, dist_n_piece_bc))
				if len(combined_dists_n_pieces) == 0:
					if log_:
						printerr('Multipath not possible.')
						printerr('point a locs: %s' % locs_a)
						printerr('point b locs: %s' % locs_b)
						printerr('point c locs: %s' % locs_c)
						printerr('%d possible paths from a to b.  %d possible paths from b to c.' % (len(dists_n_pieces_ab), len(dists_n_pieces_bc)))
						printerr(latlng_a, latlng_b, latlng_c)
						printerr('a -> b')
						for dist, pieces in dists_n_pieces_ab:
							printerr(pieces)
						printerr('b -> c')
						for dist, pieces in dists_n_pieces_bc:
							printerr(pieces)
					r_pieces = None # No path possible for this part.  No path is possible at all. 
					break
				chosen_dists_n_pieces = sorted(combined_dists_n_pieces, \
						key=lambda e: self.get_combined_cost(e[0], e[1], snap_tolerance))[0]
				chosen_piece_ab = chosen_dists_n_pieces[0][1]
				r_pieces.append(chosen_piece_ab)
				r_dist += chosen_dists_n_pieces[0][0]
				chosen_loc_b = chosen_piece_ab[-1]
				# Saving these for the next time around this loop: 
				dists_n_pieces_ab = [e for e in dists_n_pieces_bc if e[1][0] == chosen_loc_b]
				if idx_c == len(latlngs_)-1:
					chosen_pathsteps_bc = chosen_dists_n_pieces[1][1]
					r_pieces.append(chosen_pathsteps_bc)
					r_dist += chosen_dists_n_pieces[1][0]
			return ((r_dist, Path(r_pieces, self, snap_tolerance)) if r_pieces is not None else (None, None))

	def get_combined_cost(self, distnpiece1_, distnpiece2_, snap_tolerance_):
		return distnpiece1_[0] + distnpiece2_[0] + self.get_doubleback_cost(distnpiece1_, distnpiece2_, snap_tolerance_)

	# Trying to strongly discourage choosing of a path that doubles back.  Can't add something silly like 9999999 because I 
	# suspect that every now and then, a vehicle will double back.  (At least it will appear to, on for example our simplified 
	# graph of streetcar tracks.)   The only reason that a doublebacking path would be incorrectly chosen is because our use of 
	# PATHS_GPS_ERROR_FACTOR sometimes causes us to choose a loc that is close to the sample latlng and suggests choosing a  
	# doubleback over a loc that is a little farther from the sample latlng and does not suggest a doubleback.  
	# So this code fudges for that.  I don't know how to describe the thinking without pictures.
	def get_doubleback_cost(self, distnpiece1_, distnpiece2_, snap_tolerance_):
		assert Path.is_piece_valid(distnpiece1_[1]) and Path.is_piece_valid(distnpiece2_[1])
		doubleback_steps = get_common_prefix(distnpiece1_[1][::-1], distnpiece2_[1])
		doubleback_dist = self.get_length_of_pathpiece(doubleback_steps)
		if doubleback_dist > 0:
			return (distnpiece1_[0]+distnpiece2_[0])*(PATHS_GPS_ERROR_FACTOR*snap_tolerance_/doubleback_dist)
		else:
			return 0.0

	def get_length_of_pathpiece(self, piecesteps_):
		r = 0.0
		for step1, step2 in hopscotch(piecesteps_):
			r += self.get_dist(step1, step2)
		return r

	def get_pts_between(self, posaddr1_, posaddr2_):
		assert posaddr1_.linesegaddr.polylineidx == posaddr2_.linesegaddr.polylineidx
		plineidx = posaddr1_.linesegaddr.polylineidx
		pos1_ptidx = posaddr1_.linesegaddr.ptidx
		pos2_ptidx = posaddr2_.linesegaddr.ptidx
		if pos1_ptidx == pos2_ptidx:
			return []
		elif pos1_ptidx < pos2_ptidx:
			return self.polylines[plineidx][pos1_ptidx+1:pos2_ptidx+1]
		else:
			return sliceii(self.polylines[plineidx], pos1_ptidx, pos2_ptidx+1)

	# return a list of Vertex, length 0, 1, or 2.  
	# If returned list has length of 2: first elem will be the 'low' vertex (by point index on the polyline), 
	# 	second elem will be the 'high' vertex. 
	# If always_return_both_ is True: then the returned list will always have a length of 2, and one or both elements might be None. 
	# 
	# If posaddr_ has a pals of 0.0 and it is right on top of a vertex, then we will act like the pals is eg. 0.00001, 
	# and return the bounding vertexes for that.  This makes some code elsewhere easier to write. 
	def get_bounding_vertexes(self, posaddr_, always_return_both_=False):
		assert isinstance(posaddr_, PosAddr)
		ptaddr = posaddr_.linesegaddr
		ptidxes_with_a_vert = self.polylineidx_to_ptidx_to_vertex.get(ptaddr.polylineidx, {}).keys()
		if len(ptidxes_with_a_vert) == 0:
			return ([None, None] if always_return_both_ else [])
		else:
			lo_vert_ptidx = max2(ptidx for ptidx in ptidxes_with_a_vert if ptidx <= ptaddr.ptidx)
			hi_vert_ptidx = min2(ptidx for ptidx in ptidxes_with_a_vert if ptidx > ptaddr.ptidx)
			lo_vert = self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx].get(lo_vert_ptidx, None)
			hi_vert = self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx].get(hi_vert_ptidx, None)
			if always_return_both_:
				return [lo_vert, hi_vert]
			else:
				return [v for v in [lo_vert, hi_vert] if v is not None]

	def get_latlng(self, loc_):
		if isinstance(loc_, PtAddr):
			return self.get_point(loc_)
		elif isinstance(loc_, PosAddr):
			assert loc_.pals < 1.0 # i.e. has been normalized.  Probably not a big deal.   
			if loc_.pals == 0.0:
				return self.get_point(loc_.linesegaddr)
			else:
				pt1 = self.get_point(loc_.linesegaddr)
				pt2 = self.get_point(PtAddr(loc_.linesegaddr.polylineidx, loc_.linesegaddr.ptidx+1))
				return pt1.avg(pt2, loc_.pals)
		elif isinstance(loc_, Vertex):
			return loc_.pos()
		else:
			raise Exception('loc arg is instance of %s' % type(loc_))

	def get_latlngs(self, locs_):
		return [self.get_latlng(loc) for loc in locs_]

	def get_mapl(self, posaddr_):
		r = self.polylineidx_to_ptidx_to_mapl[posaddr_.linesegaddr.polylineidx][posaddr_.linesegaddr.ptidx]
		r += self.get_dist_to_reference_point(posaddr_)
		return r

	def get_dist_to_reference_point(self, posaddr_):
		if posaddr_.pals == 0.0:
			return 0.0
		else:
			ptidx_to_mapl = self.polylineidx_to_ptidx_to_mapl[posaddr_.linesegaddr.polylineidx]
			ptidx = posaddr_.linesegaddr.ptidx
			dist_between_bounding_pts = ptidx_to_mapl[ptidx+1] - ptidx_to_mapl[ptidx]
			return dist_between_bounding_pts*posaddr_.pals

	# Returns shortest path, as one (dist, pathsteps) (i.e. (float, list<PosAddr|Vertex>)) pair.   If no path is possible, 
	# then both dist and path will be None. 
	# We pass a fancy 'get connected vertexes' function to dijkstra, to support path finding from somewhere along an edge 
	# (which dijkstra doesn't do) by pretending like we've inserted a temporary vertex at the start and dest positions. 
	# In the code below, 'vvert' is short for 'virtual vertex' which is a term I made up for this function, 
	# to describe something that is a vertex in the graph theory sense and from the dijkstra function's perspective, 
	# but is not necessarily one of our Vertex objects.  A virtual vertex could be a Vertex, or it could be a PosAddr. 
	def find_path_by_locs(self, startloc_, destloc_, out_visited_vertexes=None):
		assert isloc(startloc_) and isloc(destloc_)

		all_vverts = self.get_vertexes() + [loc for loc in (startloc_, destloc_) if isinstance(loc, PosAddr)]

		startisvert = isinstance(startloc_, Vertex); destisvert = isinstance(destloc_, Vertex)
		startpos_bounding_vertexes = (self.get_bounding_vertexes(startloc_, True) if not startisvert else [])
		destpos_bounding_vertexes = (self.get_bounding_vertexes(destloc_, True) if not destisvert else [])
		shared_bounding_vertexes = set(startpos_bounding_vertexes) & set(destpos_bounding_vertexes)
		def get_connected_vertexndists(vvert__):
			if (len(shared_bounding_vertexes) == 2) and (startloc_.linesegaddr.polylineidx == destloc_.linesegaddr.polylineidx):
				startpos_is_lo = (cmp(startloc_, destloc_) < 0)
				if vvert__ in (startloc_, destloc_): # going to return one vert and one posaddr.
					vert = startpos_bounding_vertexes[(not startpos_is_lo) ^ (vvert__ == destloc_)]
					thisposaddr, otherposaddr = (startloc_, destloc_)[::-1 if vvert__ == destloc_ else 1]
					r = ([(vert, self.get_dist(thisposaddr, vert))] if vert is not None else [])
					r += [(otherposaddr, self.get_dist_between_posaddrs(thisposaddr, otherposaddr))]
				else:
					assert isinstance(vvert__, Vertex)
					r = self.vertex_to_connectedvertex_n_dists[vvert__]
					if vvert__ in startpos_bounding_vertexes:
						r = [(v,d) for v,d in r if v not in shared_bounding_vertexes]
						posaddr = (startloc_, destloc_)[(not startpos_is_lo) ^ (vvert__ == startpos_bounding_vertexes[0])]
						r += [(posaddr, self.get_dist(posaddr, vvert__))]
			else:
				def default():
					return self.vertex_to_connectedvertex_n_dists[vvert__]
				if vvert__ == startloc_:	
					if startisvert:
						r = default()
						if not destisvert and startloc_ in destpos_bounding_vertexes:
							r = [(v,d) for v,d in r if v not in destpos_bounding_vertexes] + [(destloc_,self.get_dist(startloc_,destloc_))]
					else:
						r = [(vert,self.get_dist(startloc_, vert)) for vert in startpos_bounding_vertexes if vert is not None]
				elif vvert__ == destloc_:
					if destisvert:
						r = default()
						if not startisvert and destloc_ in startpos_bounding_vertexes:
							r = [(v,d) for v,d in r if v not in startpos_bounding_vertexes] + [(startloc_,self.get_dist(startloc_,destloc_))]
					else:
						r = [(vert,self.get_dist(destloc_, vert)) for vert in destpos_bounding_vertexes if vert is not None]
				else:
					assert isinstance(vvert__, Vertex)
					r = default()
					if (len(shared_bounding_vertexes) == 1) and (vvert__ == anyelem(shared_bounding_vertexes)):
						r = [(v,d) for v,d in r if v not in startpos_bounding_vertexes + destpos_bounding_vertexes]
						r += [(posaddr, self.get_dist(posaddr, vvert__)) for posaddr in (startloc_, destloc_)]
					elif vvert__ in startpos_bounding_vertexes:
						r = [(v,d) for v,d in r if v not in startpos_bounding_vertexes] + [(startloc_,self.get_dist(startloc_, vvert__))]
						if len(shared_bounding_vertexes) == 2: # but note that the start pos and dest pos are not on the same polyline, 
								# otherwise we wouldn't be here. 
							assert set(startpos_bounding_vertexes) == set(destpos_bounding_vertexes)
							r += [(destloc_,self.get_dist(destloc_, vvert__))]
					elif vvert__ in destpos_bounding_vertexes:
						r = [(v,d) for v,d in r if v not in destpos_bounding_vertexes] + [(destloc_,self.get_dist(destloc_, vvert__))]
						# if len(shared_bounding_vertexes) == 2, then that is caught 3 lines above this one.
			return r
			
		def heuristic(vvert1__, vvert2__):
			return self.get_latlng(vvert1__).dist_m(self.get_latlng(vvert2__))

		dist, pathsteps = a_star(startloc_, destloc_, all_vverts, get_connected_vertexndists, heuristic, 
				out_visited_vertexes=out_visited_vertexes)

		return (dist, pathsteps)

	# returns None if that vertex ID does not exist.
	def get_vertex(self, id_):
		return self.vertexid_to_vertex.get(id_)

	def init_path_structures(self, disttolerance_):
		self.paths_disttolerance = disttolerance_
		self.init_polylineidx_to_ptidx_to_vertex(disttolerance_)
		self.init_polylineidx_to_ptidx_to_mapl()
		self.init_vertex_to_connectedvertex_n_dists()
		self.init_plineidx_to_connected_plineidxes()
		self.vertexid_to_vertex = dict((vert.id, vert) for vert in self.get_vertexes())

	def init_plineidx_to_connected_plineidxes(self):
		self.plineidx_to_connected_plineidxes = defaultdict(lambda: set())
		for vert in self.get_vertexes():
			for ptaddr1, ptaddr2 in permutations(vert.ptaddrs, 2):
				self.plineidx_to_connected_plineidxes[ptaddr1.polylineidx].add(ptaddr2.polylineidx)
		self.plineidx_to_connected_plineidxes = dict(self.plineidx_to_connected_plineidxes)

	def init_polylineidx_to_ptidx_to_vertex(self, disttolerance_):
		addr_to_vertex = self.get_addr_to_vertex(disttolerance_)
		vertexes = set(addr_to_vertex.values())
		self.polylineidx_to_ptidx_to_vertex = defaultdict(lambda: {})
		for vertex in vertexes:
			for ptaddr in vertex.ptaddrs:
				self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx][ptaddr.ptidx] = vertex
		self.polylineidx_to_ptidx_to_vertex = dict(self.polylineidx_to_ptidx_to_vertex)

	# note 239084723 - making sure that even if there is a polyline with only one vertex on it, 
	# and the other polyline involved in this vertex has only one too, that this vertex gets a key made for 
	# it in the dict we're building here.  (i.e. if the hopscotch loop loops zero times.) 
	# So that the keys of this dict represent a complete list of the vertexes.  
	def init_vertex_to_connectedvertex_n_dists(self):
		self.vertex_to_connectedvertex_n_dists = defaultdict(lambda: [])
		for polylineidx, ptidx_to_vertex in self.polylineidx_to_ptidx_to_vertex.iteritems():
			vertexes_in_polyline_order = list(vert for ptidx, vert in iteritemssorted(ptidx_to_vertex))
			for vertex in vertexes_in_polyline_order: # see note 239084723 
				self.vertex_to_connectedvertex_n_dists[vertex]
			for vertex1, vertex2 in hopscotch(vertexes_in_polyline_order):
				dist = self.get_dist_between_points(polylineidx, vertex1.get_ptidx(polylineidx), vertex2.get_ptidx(polylineidx))
				# TODO: if unroutable pline, then multiply dist by something large here. 
				self.vertex_to_connectedvertex_n_dists[vertex1].append((vertex2, dist))
				self.vertex_to_connectedvertex_n_dists[vertex2].append((vertex1, dist))
		self.vertex_to_connectedvertex_n_dists = dict(self.vertex_to_connectedvertex_n_dists)

	def pprint(self):
		print '{'
		for polyline in self.polylines:
			print '\t%s' % polyline
		for gridsquare, linesegaddrs in self.gridsquare_to_linesegaddrs.iteritems():
			print '\t%s' % gridsquare
			for linesegaddr in linesegaddrs:
				print '\t\t%s' % linesegaddr
		for vert, connectedvert_n_dists in iteritemssorted(self.vertex_to_connectedvertex_n_dists):
			print '\t%s' % vert
			for connectedvert, dist in connectedvert_n_dists:
				print '\t\t%s' % connectedvert
		print '}'

	# mapl = 'meters along polyline' 
	def init_polylineidx_to_ptidx_to_mapl(self):
		self.polylineidx_to_ptidx_to_mapl = []
		for polylineidx, polyline in enumerate(self.polylines):
			ptidx_to_mapl = [0]
			for ptidx in range(1, len(polyline)):
				prevpt = polyline[ptidx-1]; curpt = polyline[ptidx]
				ptidx_to_mapl.append(ptidx_to_mapl[ptidx-1] + prevpt.dist_m(curpt))
			assert len(ptidx_to_mapl) == len(polyline)
			self.polylineidx_to_ptidx_to_mapl.append(ptidx_to_mapl)
		assert len(self.polylineidx_to_ptidx_to_mapl) == len(self.polylines)

	def get_vertexes(self):
		return self.vertex_to_connectedvertex_n_dists.keys()

	def get_connected_vertexes(self, vertid_):
		vert = self.vertexid_to_vertex[vertid_]
		connectedvertex_n_dists = self.vertex_to_connectedvertex_n_dists[vert]
		return [x[0] for x in connectedvertex_n_dists]

	# pt args are inclusive / inclusive. 
	def get_dist_between_points(self, polylineidx_, startptidx_, endptidx_):
		return abs(self.polylineidx_to_ptidx_to_mapl[polylineidx_][endptidx_] - self.polylineidx_to_ptidx_to_mapl[polylineidx_][startptidx_])

	def get_dist_between_posaddrs(self, posaddr1_, posaddr2_):
		if posaddr1_.linesegaddr.polylineidx != posaddr2_.linesegaddr.polylineidx:
			raise Exception()
		plineidx = posaddr1_.linesegaddr.polylineidx
		r = self.get_dist_between_points(plineidx, posaddr1_.linesegaddr.ptidx, posaddr2_.linesegaddr.ptidx)
		posaddr1_dist_to_refpt = self.get_dist_to_reference_point(posaddr1_)
		posaddr2_dist_to_refpt = self.get_dist_to_reference_point(posaddr2_)
		is_posaddr1_less_than_posaddr2 = \
				cmp([posaddr1_.linesegaddr.ptidx, posaddr1_.pals], [posaddr2_.linesegaddr.ptidx, posaddr2_.pals]) < 0
		if is_posaddr1_less_than_posaddr2:
			r -= posaddr1_dist_to_refpt
			r += posaddr2_dist_to_refpt
		else:
			r += posaddr1_dist_to_refpt
			r -= posaddr2_dist_to_refpt
		return r

	# Each arg can be either a PosAddr or a Vertex.  
	# This is meant for use in simple code dealing with paths so, if it's two vertexes, they must be (directly) connected. 
	# If it's a posaddr and a vertex, then we're more lenient.  There can be other vertexes in between but they 
	# must be on the same polyline.  
	# Likewise with two posaddrs.  They must be on the same polyline. 
	def get_dist(self, arg1_, arg2_):
		assert (isinstance(arg, PosAddr) or isinstance(arg, Vertex) for arg in (arg1_, arg2_))
		arg1isvert = isinstance(arg1_, Vertex); arg2isvert = isinstance(arg2_, Vertex)
		if not arg1isvert and not arg2isvert:
			return self.get_dist_between_posaddrs(arg1_, arg2_)
		elif arg1isvert and arg2isvert:
			return min([x[1] for x in self.vertex_to_connectedvertex_n_dists[arg1_] if x[0] == arg2_])
		else:
			posaddr, vertex = (arg1_, arg2_)[::1 if arg2isvert else -1]
			ptaddr_of_vertex_on_posaddrs_pline = vertex.get_ptaddr(posaddr.linesegaddr.polylineidx)
			posaddr_of_vertex = PosAddr(ptaddr_of_vertex_on_posaddrs_pline, 0.0)
			return self.get_dist_between_posaddrs(posaddr, posaddr_of_vertex)

	def get_addr_to_vertex(self, disttolerance_):
		latlngid_to_ontop_latlngids = self.get_graph_latlngid_to_ontop_latlngids(disttolerance_)
		latlngid_to_addr = self.get_latlngid_to_addr(latlngid_to_ontop_latlngids)
		ptaddr_to_vertex = defaultdict(lambda: Vertex.create_open(self))

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
				vertex = ptaddr_to_vertex[ptaddr1]
				vertex.ptaddrs.add(ptaddr1)
				vertex.ptaddrs.add(ptaddr2)
				ptaddr_to_vertex[ptaddr2] = vertex

		for ptaddr in ptaddr_to_vertex.keys():
			vertex = ptaddr_to_vertex[ptaddr]
			vertex.remove_unnecessary_ptaddrs()
			if len(vertex.get_looping_polylineidxes()) > 0:
				del ptaddr_to_vertex[ptaddr]

		for vertex in ptaddr_to_vertex.values():
			vertex.set_closed()

		return dict(ptaddr_to_vertex)

	def get_latlngid_to_addr(self, latlngid_to_ontop_latlngids_):
		r = {}
		for polylineidx, polyline in enumerate(self.polylines):
			for ptidx, pt in enumerate(polyline):
				r[id(pt)] = PtAddr(polylineidx, ptidx)
		return r

	# Might modify self.polylines. 
	def get_graph_latlngid_to_ontop_latlngids(self, disttolerance_):
		latlngid_to_ontop_latlngids = defaultdict(lambda: set())
		def add(pt1_, pt2_):
			assert isinstance(pt1_, geom.LatLng) and isinstance(pt2_, geom.LatLng)
			latlngid_to_ontop_latlngids[id(pt1_)].add(id(pt2_))
			latlngid_to_ontop_latlngids[id(pt2_)].add(id(pt1_))
		for ptaddr1, ptaddr2 in self.get_addr_combos_near_each_other(False, False, disttolerance_):
			pt1 = self.get_point(ptaddr1)
			pt2 = self.get_point(ptaddr2)
			#print '-------- testing pt/pt    ', ptaddr1, ptaddr2
			if pt1.dist_m(pt2) <= disttolerance_:
				#print '-------- adding pt/pt    ', ptaddr1, ptaddr2, pt1
				add(pt1, pt2)
		for ptaddr, linesegaddr in self.get_addr_combos_near_each_other(False, True, disttolerance_):
			pt = self.get_point(ptaddr)
			lineseg = self.get_lineseg(linesegaddr)
			t0 = time.time()

			#print '-------- testing pt/line  ', ptaddr, linesegaddr
			snapped_pt, dist_to_lineseg = pt.snap_to_lineseg_opt(lineseg, disttolerance_)
			if (dist_to_lineseg is not None) and (dist_to_lineseg < disttolerance_):

			#snapped_pt, snapped_to_lineseg_ptidx, dist_to_lineseg = pt.snap_to_lineseg(lineseg)
			#if dist_to_lineseg < disttolerance_ and snapped_to_lineseg_ptidx is None \
			#		and (snapped_pt.dist_m(lineseg.start) > disttolerance_ and snapped_pt.dist_m(lineseg.end) > disttolerance_):

				# The point of that last test (not being too close to either end of the lineseg) is because those cases will 
				# be picked up by the point/point combos above.  Also, splitting a lineseg that close to one end would be ridiculous. 
				#print '-------- adding pt/line  ', ptaddr, linesegaddr, pt
				self.polylines[linesegaddr.polylineidx].insert(linesegaddr.ptidx+1, snapped_pt)
				linesegaddr.ptidx += 1
				add(pt, snapped_pt)

		for linesegaddr1, linesegaddr2 in self.get_addr_combos_near_each_other(True, True, disttolerance_):
			lineseg1 = self.get_lineseg(linesegaddr1)
			lineseg2 = self.get_lineseg(linesegaddr2)
			intersection_pt = lineseg1.get_intersection(lineseg2)
			if intersection_pt is not None:
				if all(pt.dist_m(intersection_pt) > disttolerance_ for pt in lineseg1.ptlist() + lineseg2.ptlist()):
					#print '-------- adding line/line', linesegaddr1, linesegaddr2, intersection_pt
					self.polylines[linesegaddr1.polylineidx].insert(linesegaddr1.ptidx+1, intersection_pt)
					# Need to do this because we're building our maps based on object ID of the latlngs and that code 
					# doesn't handle a single LatLng object being shared between two lines. 
					intersection_pt_copy_for_line2 = intersection_pt.copy()
					self.polylines[linesegaddr2.polylineidx].insert(linesegaddr2.ptidx+1, intersection_pt_copy_for_line2)
					linesegaddr1.ptidx += 1
					linesegaddr2.ptidx += 1
					add(intersection_pt, intersection_pt_copy_for_line2)
		#self.assert_latlngid_to_ontop_latlngids_is_sane(latlngid_to_ontop_latlngids)
		return dict(latlngid_to_ontop_latlngids)

	def assert_latlngid_to_ontop_latlngids_is_sane(self, latlngid_to_ontop_latlngids_):
		def latlngid_is_in_polylines(latlngid_):
			for polyline in self.polylines:
				for pt in polyline:
					if id(pt) == latlngid_:
						return True
			return False
		for latlngid, ontop_latlngids in latlngid_to_ontop_latlngids_.iteritems():
			assert latlngid_is_in_polylines(latlngid)
			for ontop_latlngid in ontop_latlngids:
				assert latlngid_is_in_polylines(ontop_latlngid)

	def init_gridsquare_to_linesegaddrs(self):
		self.gridsquare_to_linesegaddrs = defaultdict(lambda: set()) # key: GridSquare.  value: set of PtAddr
		self.polylineidx_to_gridsquares = [set() for i in range(len(self.polylines))]
		for polylineidx, polyline in enumerate(self.polylines):
			for startptidx in range(0, len(polyline)-1):
				linesegaddr = PtAddr(polylineidx, startptidx)
				for gridsquare in get_gridsquares_touched_by_lineseg(self.get_lineseg(linesegaddr)):
					self.gridsquare_to_linesegaddrs[gridsquare].add(linesegaddr)
					self.polylineidx_to_gridsquares[polylineidx].add(gridsquare)
		self.gridsquare_to_linesegaddrs = dict(self.gridsquare_to_linesegaddrs) # b/c a defaultdict can't be pickled i.e. memcached

	def get_lineseg(self, linesegaddr_):
		polyline = self.polylines[linesegaddr_.polylineidx]
		return geom.LineSeg(polyline[linesegaddr_.ptidx], polyline[linesegaddr_.ptidx+1])

	def get_point(self, linesegaddr_):
		return self.polylines[linesegaddr_.polylineidx][linesegaddr_.ptidx]

	# returns: list, each element either a PosAddr or a Vertex, sorted by dist to target_ in increasing order. 
	# There are three stages to this.  The first stage finds all of the possible lineseg (i.e. PosAddr) snaps.  Simple.  
	# 
	# The second stage reduces that list of lineseg snaps to probably one per polyline.  The reason for doing this is because 
	# for most cases, several consecutive linesegs will be within the search radius, and we'll see a lot of useless 
	# snaps with a pals of 0 or 1.  These are not useful.  So we get the closest ones to our target only, 
	# AKA the local minima by dist to target.
	# 
	# The third stages adds all of the vertexes surrounding the posaddrs that we have.
	def multisnap(self, target_, searchradius_):
		assert searchradius_ is not None
		linesegaddr_to_lssr = {}
		for linesegaddr in self.get_nearby_linesegaddrs(GridSquare(target_), searchradius_):
			lineseg = self.get_lineseg(linesegaddr)
			lssr = target_.snap_to_lineseg(lineseg)
			if lssr.dist <= searchradius_:
				linesegaddr_to_lssr[linesegaddr] = lssr
		plineidxes = set(addr.polylineidx for addr in linesegaddr_to_lssr.keys())

		posaddr_to_dist = {}
		for plineidx in plineidxes:
			plines_linesegaddr_to_lssr = sorteddict((k, v) for k, v in linesegaddr_to_lssr.iteritems() if k.polylineidx == plineidx)
			plines_linesegaddrs = plines_linesegaddr_to_lssr.sortedkeys()
			plines_lssrs = plines_linesegaddr_to_lssr.values_sorted_by_key()
			relevant_idxes = get_local_minima_indexes(plines_lssrs, lambda lssr: lssr.dist)
			for idx in relevant_idxes:
				linesegaddr = plines_linesegaddrs[idx]
				lssr = plines_lssrs[idx]
				posaddr_to_dist[PosAddr(linesegaddr, lssr.pals)] = lssr.dist

		r = posaddr_to_dist.keys()

		vert_to_dist = {}
		for pos in r:
			for vert in self.get_bounding_vertexes(pos):
				dist = vert.pos().dist_m(target_) 
				if dist <= searchradius_:
					vert_to_dist[vert] = dist

		verts = vert_to_dist.keys()
		r = [pos for pos in r if all(self.get_latlng(pos).dist_m(vert.pos()) > 5 for vert in verts)]
		r += verts
		r.sort(key=lambda loc: posaddr_to_dist[loc] if isinstance(loc, PosAddr) else vert_to_dist[loc])
		return r

	def is_there_a_vertex_at(self, pos_):
		assert isinstance(pos_, PosAddr)
		return pos_.pals == 0.0 and pos_.linesegaddr.ptidx in self.polylineidx_to_ptidx_to_vertex[pos_.linesegaddr.polylineidx]

	def are_plines_connected(self, plineidx1_, plineidx2_):
		return plineidx2_ in self.plineidx_to_connected_plineidxes[plineidx1_]

	# arg searchradius_ is in metres.  None means unlimited i.e. keep looking forever.  
	# As long as this object contains some lines, something will be found and returned.  Probably quickly, too. 
	# The word 'forever' is misleading. 
	#
	# returns: a PosAddr, or None if no lines were found within the search radius.
	def snap(self, target_, searchradius_):
		assert isinstance(target_, geom.LatLng) and (isinstance(searchradius_, int) or searchradius_ is None)
		# Guarding against changes in LATSTEP/LNGSTEP while a SnapGraph object was sitting in memcached:
		if not (self.latstep == LATSTEP and self.lngstep == LNGSTEP and self.latref == LATREF and self.lngref == LNGREF):
			raise Exception('snapgraph\'s lat/lng step/ref changed.')
		target_gridsquare = GridSquare(target_)
		a_nearby_linesegaddr = self.get_a_nearby_linesegaddr(target_gridsquare, searchradius_)
		if a_nearby_linesegaddr is None:
			return None
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
			return None
		else:
			return PosAddr(best_yet_linesegaddr, best_yet_lssr.pals)

	def _snap_get_endgame_linesegaddrs(self, target_gridsquare_, search_radius_):
		assert isinstance(target_gridsquare_, GridSquare)
		r = set()
		for linesegaddr in self.get_nearby_linesegaddrs(target_gridsquare_, search_radius_):
			r.add(linesegaddr)
		return r

	def _snap_get_endgame_search_radius(self, a_nearby_lineseg_, target_gridsquare_):
		assert isinstance(a_nearby_lineseg_, geom.LineSeg) and isinstance(target_gridsquare_, GridSquare)
		corners = target_gridsquare_.corner_latlngs()
		r = max(sr.dist for sr in [latlng.snap_to_lineseg(a_nearby_lineseg_) for latlng in corners])
		return int(r)

	def heading(self, linesegaddr_, referencing_lineseg_aot_point_):
		assert isinstance(linesegaddr_, PtAddr)
		# TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is False.
		assert (0 <= linesegaddr_.polylineidx < len(self.polylines))
		if referencing_lineseg_aot_point_:
			assert 0 <= linesegaddr_.ptidx < len(self.polylines[linesegaddr_.polylineidx])-1
		else:
			assert 0 <= linesegaddr_.ptidx < len(self.polylines[linesegaddr_.polylineidx])
		startptidx = linesegaddr_.ptidx
		if linesegaddr_.ptidx == len(self.polylines[linesegaddr_.polylineidx])-1:
			assert not referencing_lineseg_aot_point_
			startptidx -= 1
		linesegaddr = PtAddr(linesegaddr_.polylineidx, startptidx)
		lineseg = self.get_lineseg(linesegaddr)
		return lineseg.start.heading(lineseg.end)

	# Return a linesegaddr, any linesegaddr.  It will probably be one nearby, but definitely not guaranteed to be the closest. 
	def get_a_nearby_linesegaddr(self, gridsquare_, searchradius_):
		for linesegaddr in self.get_nearby_linesegaddrs(gridsquare_, searchradius_):
			return linesegaddr
		return None

	def get_nearby_linesegaddrs(self, gridsquare_, searchradius_):
		assert isinstance(gridsquare_, GridSquare)
		for gridsquare in gridsquare_spiral_gen_by_geom_vals(gridsquare_, searchradius_):
			if gridsquare in self.gridsquare_to_linesegaddrs:
				for linesegaddr in self.gridsquare_to_linesegaddrs[gridsquare]:
					yield linesegaddr

	# If the consumer of this generator modifies the ptidx field of the 
	# yielded objects, that will be noticed by the generator and looping will be 
	# affected.   This behaviour is only supported for ptidx (not 
	# polylineidx) because that's all I need right now. 
	def get_addr_combos_near_each_other(self, linesforaddr1_, linesforaddr2_, dist_m_):
		assert not (linesforaddr1_ and not linesforaddr2_) # Not supported due to laziness. 
		if dist_m_ is None: raise Exception()  # we work with sets.  can't handle infinite search radius. 
		for addr1polylineidx in range(len(self.polylines)):
			addr1ptidx = 0
			while addr1ptidx < len(self.polylines[addr1polylineidx]) - (1 if linesforaddr1_ else 0):
				addr1 = PtAddr(addr1polylineidx, addr1ptidx)
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
					if (not linesforaddr1_ and linesforaddr2_) or (addr1.polylineidx < addr2.polylineidx):
						if not(linesforaddr2_ and addr2.ptidx == len(self.polylines[addr2.polylineidx])-1):
							yielded_addr2 = addr2.copy()
							yield (addr1, yielded_addr2)
							if addr1ptidx != addr1.ptidx:
								assert addr1polylineidx == addr1.polylineidx and addr1ptidx == addr1.ptidx-1
								addr1.ptidx -= 1
								addr2s = get_adjusted_addrs_from_polyline_split(addr1.polylineidx, addr1.ptidx, addr2s)
								self.adjust_addrs_from_polyline_split(addr1.polylineidx, addr1.ptidx)
							if addr2.ptidx != yielded_addr2.ptidx:
								assert addr2.polylineidx == yielded_addr2.polylineidx and addr2.ptidx == yielded_addr2.ptidx-1
								addr2s = get_adjusted_addrs_from_polyline_split(yielded_addr2.polylineidx, yielded_addr2.ptidx, addr2s)
								self.adjust_addrs_from_polyline_split(yielded_addr2.polylineidx, yielded_addr2.ptidx)
								addr2i += 1
					addr2i += 1
				addr1ptidx += 1

	def adjust_addrs_from_polyline_split(self, polylineidx_, newptidx_):
		for gridsquare in self.polylineidx_to_gridsquares[polylineidx_]:
			self.gridsquare_to_linesegaddrs[gridsquare] \
					= get_adjusted_addrs_from_polyline_split(polylineidx_, newptidx_, self.gridsquare_to_linesegaddrs[gridsquare])

	def get_linesegaddrs_near_lineseg(self, linesegaddr_, searchradius_):
		r = set()
		for gridsquare in self.get_gridsquares_near_lineseg(linesegaddr_, searchradius_):
			for linesegaddr in self.gridsquare_to_linesegaddrs.get(gridsquare, []):
				r.add(linesegaddr)
		return r

	def get_ptaddrs_near_lineseg(self, linesegaddr_, searchradius_):
		return self.get_ptaddrs_in_gridsquares(self.get_gridsquares_near_lineseg(linesegaddr_, searchradius_))

	def get_ptaddrs_in_gridsquares(self, gridsquares_):
		r = set()
		for gridsquare in gridsquares_:
			for ptaddr in self.gridsquare_to_linesegaddrs.get(gridsquare, []):
				r.add(ptaddr)
				if ptaddr.ptidx == len(self.polylines[ptaddr.polylineidx]) - 2:
					r.add(PtAddr(ptaddr.polylineidx, ptaddr.ptidx+1))
		return r

	def get_linesegaddrs_near_point(self, ptaddr_, searchradius_):
		r = set()
		for gridsquare in self.get_gridsquares_near_point(ptaddr_, searchradius_):
			for linesegaddr in self.gridsquare_to_linesegaddrs.get(gridsquare, []):
				r.add(linesegaddr)
		return r

	def get_ptaddrs_near_point(self, ptaddr_, searchradius_):
		return self.get_ptaddrs_in_gridsquares(self.get_gridsquares_near_point(ptaddr_, searchradius_))

	def get_gridsquares_near_point(self, ptaddr_, searchradius_):
		r = set()
		pts_gridsquare = GridSquare(self.get_point(ptaddr_))
		r.add(pts_gridsquare)
		r |= get_nearby_gridsquares(pts_gridsquare, searchradius_)
		return r

	def get_gridsquares_near_lineseg(self, linesegaddr_, searchradius_):
		r = set()
		lineseg = self.get_lineseg(linesegaddr_)
		for gridsquare in get_gridsquares_touched_by_lineseg(lineseg):
			r.add(gridsquare)
			r |= get_nearby_gridsquares(gridsquare, searchradius_)
		return r

	def get_infos_for_box(self, sw_, ne_):
		assert all(isinstance(x, geom.LatLng) for x in [sw_, ne_])
		plineidxes = self.get_plineidxes_for_box(sw_, ne_)
		vertexes = set()
		for plineidx in plineidxes:
			vertexes |= set(self.polylineidx_to_ptidx_to_vertex.get(plineidx, {}).values())
		vertexes = [vert for vert in vertexes if vert.pos().is_within_box(sw_, ne_)]

		plineidx_to_pline = dict((plineidx, self.polylines[plineidx]) for plineidx in plineidxes)
		return {'vertexid_to_info': dict((vert.id, vert.to_json_dict()) for vert in vertexes), 
				'plineidx_to_pline': plineidx_to_pline}

	def get_plineidxes_for_box(self, sw_, ne_):
		assert all(isinstance(x, geom.LatLng) for x in [sw_, ne_])
		sw_gridsquare = GridSquare(sw_); ne_gridsquare = GridSquare(ne_)
		r = set()
		for gridlat in range(sw_gridsquare.gridlat, ne_gridsquare.gridlat+1):
			for gridlng in range(sw_gridsquare.gridlng, ne_gridsquare.gridlng+1):
				gridsquare = GridSquare((gridlat, gridlng))
				for linesegaddr in self.gridsquare_to_linesegaddrs.get(gridsquare, []):
					r.add(linesegaddr.polylineidx)
		return r

	def mapl_to_latlonnheading(self, plineidx_, mapl_):
		if mapl_ < 0:
			return None
		ptidx_to_mapl = self.polylineidx_to_ptidx_to_mapl[plineidx_]
		# Writing this code this way because we might need to handle a mapl_ that 
		# is a little greater than the max mapl of this route.  Hopefully not too 
		# much - maybe a couple of meters?  I'm not sure.
		for i in range(1, len(ptidx_to_mapl)):
			if ptidx_to_mapl[i] >= mapl_:
				break
		prevpt = self.polylines[plineidx_][i-1]; curpt = self.polylines[plineidx_][i]
		prevmapl = ptidx_to_mapl[i-1]; curmapl = ptidx_to_mapl[i]
		pt = curpt.subtract(prevpt).scale((mapl_-prevmapl)/float(curmapl-prevmapl)).add(prevpt)
		return (pt, prevpt.heading(curpt))

	def get_pline_len(self, plineidx_):
		return self.polylineidx_to_ptidx_to_mapl[plineidx_][-1]

def get_adjusted_addrs_from_polyline_split(polylineidx_, newptidx_, addrs_):
	assert isinstance(polylineidx_, int) and isinstance(newptidx_, int)
	inaddrs = (addrs_ if isinstance(addrs_, Sequence) else list(addrs_))
	r = []
	for addr in inaddrs:
		if addr.polylineidx == polylineidx_ and addr.ptidx >= newptidx_:
			r.append(PtAddr(addr.polylineidx, addr.ptidx+1))
		else:
			r.append(addr)
	if PtAddr(polylineidx_, newptidx_-1) in addrs_:
		r.append(PtAddr(polylineidx_, newptidx_))
	return (r if isinstance(addrs_, Sequence) else set(r))

def get_gridsquares_touched_by_lineseg(lineseg_):
	assert isinstance(lineseg_, geom.LineSeg)
	linesegstartgridsquare = GridSquare(lineseg_.start)
	linesegendgridsquare = GridSquare(lineseg_.end)
	# TODO: be more specific in the grid squares considered touched by a line.  We are covering a whole bounding box.
	# we could narrow down that set of squares a lot.
	for gridlat in intervalii(linesegstartgridsquare.gridlat, linesegendgridsquare.gridlat):
		for gridlng in intervalii(linesegstartgridsquare.gridlng, linesegendgridsquare.gridlng):
			yield GridSquare((gridlat, gridlng))

# arg searchradius_ None means unlimited. 
def get_reaches(target_gridsquare_, searchradius_):
	assert isinstance(target_gridsquare_, GridSquare)
	if searchradius_ is None:
		return (None, None)
	else:
		lat_reach = get_reach_single(target_gridsquare_, searchradius_, True)
		lon_reach_top = get_reach_single(GridSquare((target_gridsquare_.gridlat+lat_reach+1, target_gridsquare_.gridlng)), searchradius_, False)
		lon_reach_bottom = get_reach_single(GridSquare((target_gridsquare_.gridlat-lat_reach, target_gridsquare_.gridlng)), searchradius_, False)
		return (lat_reach, max(lon_reach_top, lon_reach_bottom))

def get_reach_single(reference_gridsquare_, searchradius_, lat_aot_lng_):
	assert isinstance(reference_gridsquare_, GridSquare) and (isinstance(searchradius_, int) or isinstance(searchradius_, float)) 
	assert isinstance(lat_aot_lng_, bool)
	reference_gridsquare_latlng = reference_gridsquare_.latlng()
	r = 1
	while True:
		if lat_aot_lng_:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat + r*LATSTEP, reference_gridsquare_latlng.lng)
		else:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat, reference_gridsquare_latlng.lng + r*LNGSTEP)
		if cur_latlng.dist_m(reference_gridsquare_latlng) >= searchradius_:
			return r
		r += 1

def steps_satisfy_searchradius(target_, searchradius_):
	assert isinstance(target_, geom.LatLng) and isinstance(searchradius_, int)
	ref_gridsquare = GridSquare(target_)
	ref_gridsquare.gridlat += 2
	if ref_gridsquare.latlng().dist_m(GridSquare((ref_gridsquare.gridlat+1, ref_gridsquare.gridlng)).latlng()) < searchradius_:
		return False
	if ref_gridsquare.latlng().dist_m(GridSquare((ref_gridsquare.gridlat, ref_gridsquare.gridlng+1)).latlng()) < searchradius_:
		return False
	return True

# A list of line segments.  Line segments points are geom.LatLng.
def get_display_grid(southwest_latlng_, northeast_latlng_):
	assert isinstance(southwest_latlng_, geom.LatLng) and isinstance(northeast_latlng_, geom.LatLng)
	southwest_gridsquare = GridSquare(southwest_latlng_)
	northeast_gridsquare = GridSquare(northeast_latlng_)
	northeast_gridsquare.gridlat += 1; northeast_gridsquare.gridlng += 1
	r = []
	for gridlat in range(southwest_gridsquare.gridlat, northeast_gridsquare.gridlat+1):
		for gridlng in range(southwest_gridsquare.gridlng, northeast_gridsquare.gridlng+1):
			r.append([GridSquare((gridlat, gridlng)).latlng(), GridSquare((gridlat, gridlng+1)).latlng()])
			r.append([GridSquare((gridlat, gridlng)).latlng(), GridSquare((gridlat+1, gridlng)).latlng()])
	return r

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
	assert isinstance(center_gridsquare_, GridSquare)
	assert (latreach_ is None) == (lngreach_ is None)
	for offsetlat, offsetlng in gridsquare_offset_spiral_gen(latreach_, lngreach_):
		yield GridSquare((center_gridsquare_.gridlat + offsetlat, center_gridsquare_.gridlng + offsetlng))

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
	r = []
	def ret(x__, y__):
		r.append(GridSquare((y__, x__)))

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
	r = []

	x0 = gridsquare0_.gridlng; y0 = gridsquare0_.gridlat
	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat

	def ret(x__, y__):
		r.append(GridSquare((y__, x__)))

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
	r = []

	x1 = gridsquare1_.gridlng; y1 = gridsquare1_.gridlat
	x2 = gridsquare2_.gridlng; y2 = gridsquare2_.gridlat
	assert x1 <= x2 and y1 <= y2 and y2-y1 <= x2-x1

	def ret(x__, y__):
		r.append(GridSquare((y__, x__)))

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
def dijkstra(srcvertex_, destvertex_, all_vertexes_, get_connected_vertexndists_, out_visited_vertexes=None):
	assert srcvertex_ in all_vertexes_ and destvertex_ in all_vertexes_

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
		if u == destvertex_:
			break
		q.remove(u)
		info[u].visited = True
		for v, vdist in get_connected_vertexndists_(u):
			alt = info[u].dist + vdist
			if alt < info[v].dist and not info[v].visited:
				info[v].dist = alt
				info[v].previous = u
				q.add(v)

	if out_visited_vertexes is not None:
		out_visited_vertexes[:] = [vert for vert, vertinfo in info.iteritems() if vertinfo.visited]

	if info[destvertex_].dist == float('inf'):
		return (None, None)
	else:
		path = []
		u = destvertex_
		while info[u].previous is not None:
			path.insert(0, u)
			u = info[u].previous
		path.insert(0, srcvertex_)
		return (info[destvertex_].dist, path)

# The A* path-finding algorithm.  Thanks to http://en.wikipedia.org/wiki/A*_search_algorithm
# This version assumes, and exploits, a monotonic heuristic function. 
def a_star(srcvertex_, destvertex_, all_vertexes_, get_connected_vertexndists_, heuristic_cost_estimate_, out_visited_vertexes=None):
	closedset = set() # The set of nodes already evaluated.
	openset = set([srcvertex_]) # The set of tentative nodes to be evaluated, initially containing the start node
	came_from = {} # The map of navigated nodes.

	# Cost from start along best known path:
	g_score = {srcvertex_: 0}
	# Estimated total cost from srcvertex_ to destvertex_ through y:
	f_score = {srcvertex_: g_score[srcvertex_] + heuristic_cost_estimate_(srcvertex_, destvertex_)}

	while len(openset) > 0:
		current = min(openset, key=lambda v: f_score[v])
		if current == destvertex_:
			path = [destvertex_]
			while path[0] in came_from:
				path.insert(0, came_from[path[0]])
			return (g_score[destvertex_], path)
 
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
				if neighbor not in openset:
					openset.add(neighbor)

	return (None, None)

def isloc(obj_):
	return isinstance(obj_, Vertex) or isinstance(obj_, PosAddr)

def graph_locs_to_json_str(locs_):
	output_list = []
	for loc in locs_:
		if isinstance(loc, PosAddr):
			output_e = [loc.linesegaddr.polylineidx, loc.linesegaddr.ptidx, round(loc.pals, 4)]
		elif isinstance(loc, Vertex):
			output_e = loc.id
		else:
			raise Exception()
		output_list.append(output_e)
	return json.dumps(output_list, separators=(',',':'))

def parse_graph_locs_json_str(str_, sg_):
	obj = json.loads(str_)
	assert isinstance(obj, Sequence)
	r = []
	for e in obj:
		if isinstance(e, int):
			output_loc = sg_.get_vertex(e)
			if output_loc is None:
				raise Exception('vertex id %d was in graph_locs json string, but not in snapgraph.' % e)
		else:
			assert is_seq_like(e, [0,0,0.0])
			output_loc = PosAddr(PtAddr(e[0], e[1]), e[2])
		r.append(output_loc)
	return r

if __name__ == '__main__':

	addrs = set()
	for plineidx in range(3, -1, -1):
		for startptidx in range(3, -1, -1):
			addrs.add(PtAddr(plineidx, startptidx))
	print sorted(addrs)




