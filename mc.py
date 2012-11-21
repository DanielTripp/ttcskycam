#!/usr/bin/python2.6

import memcache
import c

client = memcache.Client(['127.0.0.1:%d' % (2029 if c.IS_DEV else 2030)], debug=0)

# Important that we cast to the return value of this is a str because that's what the memcache client insists on.  
# Unicode will cause an error right away. 
def make_key(name_, *args):
	return '%s-%s(%s)' % (c.SITE_VERSION, name_, ','.join([str(arg) for arg in args]))

if __name__ == '__main__':

	key = make_key('RouteInfo', 1, 'a', 3)
	print key
	print isinstance(key, str)

