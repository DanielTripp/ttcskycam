#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse
import web
from misc import *

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
whereclause = decode_url_paramval(vars.setdefault('whereclause', [''])[0])
maxrows = int(vars.setdefault('maxrows', ['10'])[0])
interpbytime = (True if vars.setdefault('interpbytime', ['false'])[0].lower() == 'true' else False)
print web.query1(whereclause, maxrows, interpbytime), 

