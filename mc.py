#!/usr/bin/python2.6

import memcache
import c

g_memcache_client = memcache.Client(['127.0.0.1:2029'], debug=0)

g_in_process_cache_key_to_value = {}

# Important that the return value of this is a str because that's what the memcache g_memcache_client insists on.  
# Unicode will cause an error right away. 
# Also - memcached can't handle spaces in keys, so we avoid that. 
def _make_key(func_, args_):
	name = '%s.%s' % (func_.__module__, func_.__name__)
	r = '%s-%s(%s)' % (c.VERSION, name, ','.join([str(arg) for arg in args_]))
	SPACE_REPLACER = '________'
	assert SPACE_REPLACER not in r
	r = r.replace(' ', SPACE_REPLACER)
	return r

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

def decorate(user_function_):
	def decorating_function(*args):
		return get(user_function_, args)
	
	return decorating_function


if __name__ == '__main__':

	import routes
	print _make_key(routes.routeinfo, ['dundas'])


