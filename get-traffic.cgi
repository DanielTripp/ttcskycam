#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse
import web

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
fudgeroute = vars['fudgeroute'][0]
direction = int(vars['direction'][0])
#print web.get_traffic(fudgeroute, direction, 1331611814197)
#print web.get_traffic(fudgeroute, direction, 1331658913000)
print web.get_traffic(fudgeroute, direction)

