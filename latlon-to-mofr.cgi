#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse
import routes

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
lat = float(vars['lat'][0])
lon = float(vars['lon'][0])
fudgeroute = vars['fudgeroute'][0]
print routes.latlon_to_mofr((lat, lon), fudgeroute)

