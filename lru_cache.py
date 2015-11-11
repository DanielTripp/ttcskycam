## {{{ http://code.activestate.com/recipes/498245/ (r6)
import os
import collections
import functools
import threading
from itertools import ifilterfalse
from heapq import nsmallest
from operator import itemgetter
from misc import *

LOG = os.path.exists('LOG_LRU_CACHE')

class Counter(dict):
		'Mapping where default values are zero'
		def __missing__(self, key):
				return 0

def lru_cache(maxsize=100, posargkeymask=None, cacheable=None):
		'''Least-recently-used cache decorator.

		Arguments to the cached function must be hashable.
		Cache performance statistics stored in f.hits and f.misses.
		Clear the cache with f.clear().
		http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used

		'''
		maxqueue = maxsize * 10
		def decorating_function(user_function,
						len=len, iter=iter, tuple=tuple, sorted=sorted, KeyError=KeyError):
				cache = {}									# mapping of args to results
				queue = collections.deque() # order that keys have been used
				refcount = Counter()				# times each key is in the queue
				sentinel = object()				 # marker for looping around the queue
				kwd_mark = object()				 # separate positional and keyword args
				rlock = threading.RLock()

				# lookup optimizations (ugly but fast)
				queue_append, queue_popleft = queue.append, queue.popleft
				queue_appendleft, queue_pop = queue.appendleft, queue.pop

				@functools.wraps(user_function)
				def wrapper(*args, **kwds):
						if (cacheable is not None and not cacheable(args, kwds)) or (maxsize == 0):
							return user_function(*args, **kwds)

						with rlock:
							# cache key records both positional and keyword args
							key = args
							if posargkeymask is not None:
								assert len(posargkeymask) == len(args)
								key = tuple(key[i] for i in range(len(key)) if posargkeymask[i])
							if kwds:
									key += (kwd_mark,) + tuple(sorted(kwds.items()))

							# record recent use of this key
							queue_append(key)
							refcount[key] += 1

							# get cache entry or compute if not found
							try:
									result = cache[key]
									if LOG: printerr('Found in lru_cache - func=%s, key=%s' % (user_function, str(key)))
									wrapper.hits += 1
							except KeyError:
									if LOG: printerr('Not found in lru_cache - func=%s, key=%s' % (user_function, str(key)))
									result = user_function(*args, **kwds)
									cache[key] = result
									wrapper.misses += 1

									# purge least recently used cache entry
									if len(cache) > maxsize:
											key = queue_popleft()
											refcount[key] -= 1
											while refcount[key]:
													key = queue_popleft()
													refcount[key] -= 1
											del cache[key], refcount[key]

							# periodically compact the queue by eliminating duplicate keys
							# while preserving order of most recent access
							if len(queue) > maxqueue:
									refcount.clear()
									queue_appendleft(sentinel)
									for key in ifilterfalse(refcount.__contains__,
																					iter(queue_pop, sentinel)):
											queue_appendleft(key)
											refcount[key] = 1

							return result

				def clear():
						with rlock:
							cache.clear()
							queue.clear()
							refcount.clear()
							wrapper.hits = wrapper.misses = 0

				wrapper.hits = wrapper.misses = 0
				wrapper.clear = clear
				return wrapper
		return decorating_function


def lfu_cache(maxsize=100):
		'''Least-frequenty-used cache decorator.

		Arguments to the cached function must be hashable.
		Cache performance statistics stored in f.hits and f.misses.
		Clear the cache with f.clear().
		http://en.wikipedia.org/wiki/Least_Frequently_Used

		'''
		def decorating_function(user_function):
				cache = {}											# mapping of args to results
				use_count = Counter()					 # times each key has been accessed
				kwd_mark = object()						 # separate positional and keyword args
				rlock = threading.RLock()

				@functools.wraps(user_function)
				def wrapper(*args, **kwds):
						with rlock:
							key = args
							if kwds:
									key += (kwd_mark,) + tuple(sorted(kwds.items()))
							use_count[key] += 1

							# get cache entry or compute if not found
							try:
									result = cache[key]
									wrapper.hits += 1
							except KeyError:
									result = user_function(*args, **kwds)
									cache[key] = result
									wrapper.misses += 1

									# purge least frequently used cache entry
									if len(cache) > maxsize:
											for key, _ in nsmallest(maxsize // 10,
																							use_count.iteritems(),
																							key=itemgetter(1)):
													del cache[key], use_count[key]

							return result

				def clear():
						with rlock:
							cache.clear()
							use_count.clear()
							wrapper.hits = wrapper.misses = 0

				wrapper.hits = wrapper.misses = 0
				wrapper.clear = clear
				return wrapper
		return decorating_function


if __name__ == '__main__':

		@lru_cache(maxsize=20)
		def f(x, y):
				return 3*x+y

		domain = range(5)
		from random import choice
		for i in range(1000):
				r = f(choice(domain), choice(domain))

		print(f.hits, f.misses)

		@lfu_cache(maxsize=20)
		def f(x, y):
				return 3*x+y

		domain = range(5)
		from random import choice
		for i in range(1000):
				r = f(choice(domain), choice(domain))

		print(f.hits, f.misses)
## end of http://code.activestate.com/recipes/498245/ }}}
