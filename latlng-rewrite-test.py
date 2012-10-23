#!/usr/bin/python2.6

import pprint
import traffic, routes

print '--- 1:'
pprint.pprint(traffic.get_traffics('dundas', 1, True, '2012-09-24 13:20'))
print '--- 2:'
pprint.pprint(traffic.get_recent_vehicle_locations('dundas', 1, True, '2012-09-24 13:20'))
print '--- 3:'
pprint.pprint(routes.get_all_routes_latlons())
print '--- 4:'
pprint.pprint(routes.get_endpoint_info(43.64995004545798, -79.43073077400823, 43.65013635880088, -79.41347880562444))
print '--- 5:'
pprint.pprint(routes.get_endpoint_info(43.64995004545798, -79.43073077400823, 43.64653419841198, -79.40824313362737))
print '--- 6:'
pprint.pprint(routes.get_endpoint_info(43.64262126219334, -79.44798274239201, 43.63839748946205, -79.43004412850041))



