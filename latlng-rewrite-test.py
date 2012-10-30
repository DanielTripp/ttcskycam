#!/usr/bin/python2.6

import pprint
import traffic, routes, geom
from misc import *

try:
	geom.LatLng
	LATLNG_CLASS_EXISTS = True
except:
	LATLNG_CLASS_EXISTS = False

class OurPrettyPrinter(pprint.PrettyPrinter):

	def format(self, object, context, maxlevels, level):
		if LATLNG_CLASS_EXISTS and isinstance(object, geom.LatLng):
			return (str(object), True, False)
		elif isinstance(object, float):
			return ('%.4f'%(object), True, False)
		else:
			return pprint.PrettyPrinter.format(self, object, context, maxlevels, level)

pprinter = OurPrettyPrinter()

def latlng(lat_, lon_):
	if LATLNG_CLASS_EXISTS:
		return geom.LatLng(lat_, lon_)
	else:
		return (lat_, lon_)

print '--- latlon_to_mofr - cross-route:'
if 0:
	startlat = 43.63156428725445; endlat = 43.65473190497122; lon = -79.41622538765569
	for tolerance in (0, 1, 2):
		print 'tolerance', tolerance
		lat = startlat
		while lat < endlat:
			print '%.5f, %.5f   -> %d' % (lat, lon, routes.latlon_to_mofr('king', latlng(lat, lon), tolerance_=tolerance))
			lat += 0.00001
if 0:
	startlat = 43.658725; startlon = -79.343398; endlat = 43.662606; endlon = -79.351740
	for tolerance in (0, 1, 2):
		print 'tolerance', tolerance
		for ratio in frange(0.0, 1.0, 0.01):
			lat = geom.avg(startlat, endlat, ratio); lon = geom.avg(startlon, endlon, ratio)
			print '%.5f, %.5f   -> %d' % (lat, lon, routes.latlon_to_mofr('dundas', latlng(lat, lon), tolerance_=tolerance))
			lat += 0.00001
print '--- latlon_to_mofr - along route:'
if 0:
	king_pts = [ [43.656831, -79.452789],	[43.651739, -79.451132],	[43.646957, -79.449475],	[43.642671, -79.447733],	[43.639379, -79.446420],	[43.638385, -79.445793],	[43.637578, -79.443192],	[43.636646, -79.441535],	[43.636584, -79.439450],	[43.637391, -79.435132],	[43.639069, -79.427210],	[43.640870, -79.417228],	[43.642858, -79.408018],	[43.644721, -79.398980],	[43.646833, -79.388311],	[43.648944, -79.379101],	[43.651118, -79.369033],	[43.652608, -79.363085],	[43.654968, -79.359282],	[43.657017, -79.356510],	[43.657825, -79.354767],[43.658942, -79.350021],	[43.663165, -79.351711],	[43.667526, -79.353359],	[43.668923, -79.352968],	[43.669746, -79.353071],	[43.671236, -79.354547],	[43.671934, -79.354758],	[43.673455, -79.356191],	[43.675659, -79.358375],	[43.676761, -79.358886] ]
	for i, pt in enumerate(king_pts):
		print '%d: ( %.5f, %.5f ) -> %d' % (i, pt[0], pt[1], routes.latlon_to_mofr('king', latlng(pt[0], pt[1])))
	dundas_pts = [[43.657266, -79.452960],[43.649627, -79.430018],[43.651925, -79.402612],[43.657017, -79.374605],[43.662606, -79.351405],[43.675520, -79.358417]]
	for i, pt in enumerate(dundas_pts):
		print '%d: ( %.5f, %.5f ) -> %d' % (i, pt[0], pt[1], routes.latlon_to_mofr('dundas', latlng(pt[0], pt[1])))
	queen_pts = [[43.592650, -79.541280],[43.599861, -79.509754],[43.613161, -79.489902],[43.628259, -79.478632],[43.638944, -79.461526],[43.639876, -79.440300],[43.645094, -79.414353],[43.651553, -79.383514],[43.656955, -79.357910],[43.662420, -79.333852],[43.667821, -79.309793],[43.671360, -79.293460],[43.673719, -79.282791]]
	for i, pt in enumerate(queen_pts):
		print '%d: ( %.5f, %.5f ) -> %d' % (i, pt[0], pt[1], routes.latlon_to_mofr('queen', latlng(pt[0], pt[1])))
print '--- get_traffics:'
#pprinter.pprint(traffic.get_traffics('dundas', 1, True, '2012-09-24 13:20', log_=True))
print '--- get_recent_vehicle_locations:'
#pprinter.pprint(traffic.get_recent_vehicle_locations('dundas', 1, True, '2012-09-24 13:20'))
print '--- get_all_routes_latlons:'
#pprinter.pprint(routes.get_all_routes_latlons())
print '--- get_endpoint_info:'
#pprinter.pprint(routes.get_endpoint_info(43.64995004545798, -79.43073077400823, 43.65013635880088, -79.41347880562444))
#pprinter.pprint(routes.get_endpoint_info(43.64995004545798, -79.43073077400823, 43.64653419841198, -79.40824313362737))
#pprinter.pprint(routes.get_endpoint_info(43.64262126219334, -79.44798274239201, 43.63839748946205, -79.43004412850041))



