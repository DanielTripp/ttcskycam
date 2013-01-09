#!/usr/bin/python2.6

import memcache
import c

g_memcache_client = memcache.Client(['127.0.0.1:%d' % (2029 if c.IS_DEV else 2030)], debug=0)

g_in_process_cache_key_to_value = {}

# Important that the return value of this is a str because that's what the memcache g_memcache_client insists on.  
# Unicode will cause an error right away. 
def _make_key(func_, args_):
	name = '%s.%s' % (func_.__module__, func_.__name__)
	return '%s-%s(%s)' % (c.SITE_VERSION, name, ','.join([str(arg) for arg in args_]))

def get(func_, args_=[]):
	args_ = args_[:]
	key = _make_key(func_, args_)
	if key in g_in_process_cache_key_to_value:
		r = g_in_process_cache_key_to_value[key]
	else:
		r = g_memcache_client.get(key)
		if r is None:
			r = func_(*args_)
			g_memcache_client.set(key, r)
		g_in_process_cache_key_to_value[key] = r
	return r


if __name__ == '__main__':

	import routes
	print _make_key(routes.routeinfo, ['dundas'])


