#!/usr/bin/python2.6

from collections import defaultdict, Sequence
from itertools import *
import pprint
import math
import geom
from misc import *

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

# Used as a dict key in a few places, and in sets.  Relying on that default object hash() = id() behaviour. 
class Vertex(object):

	if __debug__:
		next_id = 0

	def __init__(self, snapgraph_):
		if __debug__:
			self.id = Vertex.next_id
			Vertex.next_id += 1
		self.snapgraph = snapgraph_
		self.ptaddrs = set()

	def pos(self):
		return self.snapgraph.get_point(anyelem(self.ptaddrs))

	def get_ptaddr(self, polylineidx_):
		ptaddrs = [ptaddr for ptaddr in self.ptaddrs if ptaddr.polylineidx == polylineidx_]
		if len(ptaddrs) != 1:
			raise Exception('Problem around %s, polyline %d (%s)' \
					% (self, polylineidx_, [self.snapgraph.get_point(ptaddr) for ptaddr in ptaddrs]))
		return ptaddrs[0]

	def get_ptidx(self, polylineidx_):
		return self.get_ptaddr(polylineidx_).ptidx

	# Returns any polylines that are mentioned more than once in this vertex. 
	def get_looping_polylineidxes(self):
		r = set()
		for ptaddr1 in self.ptaddrs:
			if len([ptaddr2 for ptaddr2 in self.ptaddrs if ptaddr2.polylineidx == ptaddr1.polylineidx]) > 1:
				r.add(ptaddr1.polylineidx)
		return r

	def __cmp__(self, other):
		if __debug__:
			return cmp(self.id, other.id)
		else:
			return cmp(self.ptaddrs, other.ptaddrs)

	def __str__(self):
		if __debug__:
			return 'Vertex(id:%d, %s, %s)' % (self.id, self.pos(), sorted(self.ptaddrs))
		else:
			return 'Vertex(%s, %s)' % (self.pos(), sorted(self.ptaddrs))

	def __repr__(self):
		return self.__str__()


# This can be pickled or memcached. 
class SnapGraph(object):

	# arg disttolerance: Two points need to be less than this far apart for us to consider them 
	# coincident AKA the same point, for our graph purposes. 
	def __init__(self, polylines_, forpaths=True, disttolerance=DEFAULT_GRAPH_VERTEX_DIST_TOLERANCE):
		assert isinstance(polylines_[0][0], geom.LatLng)
		self.latstep = LATSTEP; self.lngstep = LNGSTEP; self.latref = LATREF; self.lngref = LNGREF
		self.polylines = polylines_
		if forpaths:
			self.remove_useless_points_from_polylines(disttolerance)
		self.init_gridsquare_to_linesegaddrs()
		if forpaths:
			self.init_path_structures(disttolerance)
			self.init_gridsquare_to_linesegaddrs() # rebuilding it because for those linesegs that were split within init_path_structures() - 
				# say lineseg A was split into A1 and A2, and A covered the sets of gridsquares S.  
				# after init_path_structures() is done, self.gridsquare_to_linesegaddrs will be such that A1 is portrayed as covering all of S, 
				# and so does A2.  This is of course too wide a net in many cases - I think if the original start point, the original end 
				# point, and the split point, are in 3 different gridsquares.  init_path_structures() does this because the code is easier to 
				# write.  But now we can make it better by rebuilding it. 

	def find_shortest_path_by_latlngs(self, startpos_, destpos_, out_visited_vertexes=None):
		assert isinstance(startpos_, geom.LatLng) and isinstance(destpos_, geom.LatLng)
		searchradius = 500
		start_snapresult = self.snap(startpos_, 500)
		dest_snapresult = self.snap(destpos_, 500)
		if start_snapresult is None or dest_snapresult is None:
			return None
		else:
			start_vertex = self.find_nearest_vertex(start_snapresult)
			dest_vertex = self.find_nearest_vertex(dest_snapresult)
			if start_vertex is None or dest_vertex is None:
				return None
			else:
				return self.find_shortest_path_by_vertexes(start_vertex, dest_vertex, out_visited_vertexes=out_visited_vertexes)

	def find_nearest_vertex(self, snapresult_):
		snapped_pt, ptaddr, addrisline = snapresult_
		if addrisline:
			ptidxes_with_a_vert = self.polylineidx_to_ptidx_to_vertex.get(ptaddr.polylineidx, {}).keys()
			if len(ptidxes_with_a_vert) == 0:
				return None
			else:
				lo_vert_ptidx = max2(ptidx for ptidx in ptidxes_with_a_vert if ptidx <= ptaddr.ptidx)
				hi_vert_ptidx = min2(ptidx for ptidx in ptidxes_with_a_vert if ptidx > ptaddr.ptidx)
				if lo_vert_ptidx is None:
					return self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx][hi_vert_ptidx]
				elif hi_vert_ptidx is None:
					return self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx][lo_vert_ptidx]
				else:
					nearest_ptidx_with_a_vert = min((lo_vert_ptidx, hi_vert_ptidx), 
							key=lambda ptidx: self.get_point(ptaddr(ptaddr.polylineidx, ptidx)).dist_m(snapped_pt))
					return self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx][nearest_ptidx_with_a_vert]
		else:
			vertexes_on_polyline = self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx].values()
			if len(vertexes_on_polyline) > 0:
				return min(vertexes_on_polyline, \
						key=lambda vert: self.get_dist(ptaddr.polylineidx, ptaddr.ptidx, vert.get_ptidx(ptaddr.polylineidx)))
			else:
				return None

	# Thanks to http://en.wikipedia.org/wiki/Dijkstra's_algorithm 
	def find_shortest_path_by_vertexes(self, srcvertex_, destvertex_, out_visited_vertexes=None):
		class VertexInfo(object):
			def __init__(self):
				self.dist = float('inf')
				self.visited = False
				self.previous = None

		info = dict((vertex, VertexInfo()) for vertex in self.get_vertexes())
		info[srcvertex_].dist = 0.0
		q = set([srcvertex_])
		while len(q) > 0:
			u = min((vertex for vertex, info in info.iteritems() if not info.visited), key=lambda vertex: info[vertex].dist)
			if u is destvertex_:
				break
			q.remove(u)
			info[u].visited = True
			for v, vdist in self.vertex_to_connectedvertex_n_dists[u]:
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
			return (info[destvertex_].dist, path)

	def get_vertex(self, id_):
		if not __debug__:
			raise Exception()
		return first(self.get_vertexes(), lambda vertex: vertex.id == id_)

	def init_path_structures(self, disttolerance_):
		self.init_polylineidx_to_ptidx_to_vertex(disttolerance_)
		self.init_polylineidx_to_ptidx_to_mapl()
		self.init_vertex_to_connectedvertex_n_dists()

	def init_polylineidx_to_ptidx_to_vertex(self, disttolerance_):
		addr_to_vertex = self.get_addr_to_vertex(disttolerance_)
		vertexes = set(addr_to_vertex.values())
		self.polylineidx_to_ptidx_to_vertex = defaultdict(lambda: {})
		for vertex in vertexes:
			for ptaddr in vertex.ptaddrs:
				self.polylineidx_to_ptidx_to_vertex[ptaddr.polylineidx][ptaddr.ptidx] = vertex
		self.polylineidx_to_ptidx_to_vertex = dict(self.polylineidx_to_ptidx_to_vertex)

	def init_vertex_to_connectedvertex_n_dists(self):
		self.vertex_to_connectedvertex_n_dists = defaultdict(lambda: [])
		for polylineidx, ptidx_to_vertex in self.polylineidx_to_ptidx_to_vertex.iteritems():
			vertexes_in_polyline_order = (vert for ptidx, vert in iteritemssorted(ptidx_to_vertex))
			for vertex1, vertex2 in hopscotch(vertexes_in_polyline_order):
				dist = self.get_dist(polylineidx, vertex1.get_ptidx(polylineidx), vertex2.get_ptidx(polylineidx))
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

	def remove_useless_points_from_polylines(self, disttolerance_):
		for polylineidx, polyline in enumerate(self.polylines):
			startptidx = 0
			while startptidx < len(polyline)-1:
				if polyline[startptidx].dist_m(polyline[startptidx+1]) < disttolerance_:
					del polyline[startptidx+1]
				else:
					startptidx += 1

	def get_vertexes(self):
		return self.vertex_to_connectedvertex_n_dists.keys()

	# pt args are inclusive / inclusive. 
	def get_dist(self, polylineidx_, startptidx_, endptidx_):
		return abs(self.polylineidx_to_ptidx_to_mapl[polylineidx_][endptidx_] - self.polylineidx_to_ptidx_to_mapl[polylineidx_][startptidx_])

	def get_addr_to_vertex(self, disttolerance_):
		latlngid_to_ontop_latlngids = self.get_graph_latlngid_to_ontop_latlngids(disttolerance_)
		latlngid_to_addr = self.get_latlngid_to_addr(latlngid_to_ontop_latlngids)
		ptaddr_to_vertex = defaultdict(lambda: Vertex(self))

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
			if len(vertex.get_looping_polylineidxes()) > 0:
				del ptaddr_to_vertex[ptaddr]

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
			if pt1.dist_m(pt2) <= disttolerance_:
				#print '-------- adding pt/pt    ', ptaddr1, ptaddr2, pt1
				add(pt1, pt2)
		for ptaddr, linesegaddr in self.get_addr_combos_near_each_other(False, True, disttolerance_):
			pt = self.get_point(ptaddr)
			lineseg = self.get_lineseg(linesegaddr)
			t0 = time.time()

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
		if __debug__:
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

	def multisnap(self, target_, searchradius_):
		pass

	# arg searchradius_ is in metres.  None means unlimited i.e. keep looking forever.  
	# As long as this object contains some lines, something will be found and returned.  Probably quickly, too. 
	# The word 'forever' is misleading. 
	#
	# returns None, or a tuple - (geom.LatLng, PtAddr, bool)
	# if None: no line was found within the search radius.
	# if tuple:
	#	elem 0: snapped-to point.  geom.LatLng.
	# 	elem 1: reference line segment address (or point address) that the snapped-to point is on.
	#	elem 2: 'snapped-to point is along a line' flag.
	#			if True: then interpret elem 1 as the address of a line segment (not a point).  The snapped-to point
	# 				(i.e. elem 0) is somewhere along that line segment.
	# 			if False: then intepret elem 1 as the address of a point (not a line) - and the snapped-to point (elem 0)
	# 				is exactly the point referenced by elem 1.
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
		best_yet_snapresult = None; best_yet_linesegaddr = None
		for linesegaddr in self._snap_get_endgame_linesegaddrs(target_gridsquare, endgame_search_radius):
			lineseg = self.get_lineseg(linesegaddr)
			cur_snapresult = target_.snap_to_lineseg(lineseg)
			if best_yet_snapresult==None or cur_snapresult[2]<best_yet_snapresult[2]:
				best_yet_snapresult = cur_snapresult
				best_yet_linesegaddr = linesegaddr
		if (best_yet_snapresult == None) or (searchradius_ is not None and best_yet_snapresult[2] > searchradius_):
			return None
		else:
			if best_yet_snapresult[1] == None:
				return (best_yet_snapresult[0], best_yet_linesegaddr, True)
			else:
				if best_yet_snapresult[1] == 0:
					reference_point_addr = best_yet_linesegaddr
				else:
					reference_point_addr = PtAddr(best_yet_linesegaddr.polylineidx, best_yet_linesegaddr.ptidx+1)
				return (self.get_point(reference_point_addr).copy(), reference_point_addr, False)

	def _snap_get_endgame_linesegaddrs(self, target_gridsquare_, search_radius_):
		assert isinstance(target_gridsquare_, GridSquare)
		r = set()
		for linesegaddr in self.get_nearby_linesegaddrs(target_gridsquare_, search_radius_):
			r.add(linesegaddr)
		return r

	def _snap_get_endgame_search_radius(self, a_nearby_lineseg_, target_gridsquare_):
		assert isinstance(a_nearby_lineseg_, geom.LineSeg) and isinstance(target_gridsquare_, GridSquare)
		r = max(snap_result[2] for snap_result in [latlng.snap_to_lineseg(a_nearby_lineseg_) for latlng in target_gridsquare_.corner_latlngs()])
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
					if addr1.polylineidx < addr2.polylineidx:
						if not(linesforaddr2_ and addr2.ptidx == len(self.polylines[addr2.polylineidx])-1):
							yielded_addr2 = addr2.copy()
							yield (addr1, yielded_addr2)
							if addr1ptidx != addr1.ptidx:
								assert addr1polylineidx == addr1.polylineidx and addr1ptidx == addr1.ptidx-1
								addr1ptidx = addr1.ptidx
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
	

if __name__ == '__main__':

	addrs = set()
	for plineidx in range(3, -1, -1):
		for startptidx in range(3, -1, -1):
			addrs.add(PtAddr(plineidx, startptidx))
	print sorted(addrs)



