#!/usr/bin/env python

print 'Content-type: text/plain\n'

import sys, os, urlparse, json
import traffic

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
route = vars['route'][0]
origlat = float(vars['origlat'][0])
origlon = float(vars['origlon'][0])
destlat = float(vars['destlat'][0])
destlon = float(vars['destlon'][0])
print json.dumps(traffic.get_travel_time_info(route, (origlat, origlon), (destlat, destlon)))

