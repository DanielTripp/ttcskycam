#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse, json
import routes

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
mofr = int(vars['mofr'][0])
fudgeroute = vars['fudgeroute'][0]
print json.dumps(routes.mofr_to_latlon(fudgeroute, mofr))

