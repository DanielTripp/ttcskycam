#!/usr/bin/python2.6

import sys, os, os.path, time, math, datetime, calendar, bisect, tempfile, subprocess, StringIO, re, multiprocessing
from collections import Sequence, MutableSequence, defaultdict, MutableSet
from itertools import *
import db, mc
from misc import *

def initializer():
	db.forget_connection()
	mc.forget_connection()

def run(n_, func_, argses_):
	pool = multiprocessing.Pool(n_, initializer=initializer)
	results = []
	for args in argses_:
		results.append(pool.apply_async(func_, args))
	returnvals = []
	for result in results:
		returnvals.append(result.get())
	pool.close()
	pool.join()
	return returnvals

# Thanks to http://stackoverflow.com/a/16618842/321556 
def include_entire_traceback(real_func_):
	@functools.wraps(real_func_)
	def decorating_function(*args, **kwds):
		try:
			return real_func_(*args, **kwds)
		except:
			raise Exception("".join(traceback.format_exception(*sys.exc_info())))
	
	return decorating_function

class ShardPool(object):

	def __init__(self, shardfunc_, processes=None):
		self.shardfunc = shardfunc_
		self.num_processes = (processes if processes is not None else multiprocessing.cpu_count())
		self.pools = tuple(multiprocessing.Pool(1, initializer=initializer) for i in xrange(self.num_processes))

	def apply_async(self, func_, args_):
		pool_idx = self.shardfunc(func_, args_) % self.num_processes
		pool = self.pools[pool_idx]
		return pool.apply_async(func_, args_)

	def map(self, func_, argses_):
		async_results = []
		exc_info = None
		for args in argses_:
			try:
				async_results.append(self.apply_async(func_, args))
			except BaseException as e:
				exc_info = sys.exc_info()
		if exc_info is not None:
			raise exc_info[0], exc_info[1], exc_info[2]
		return [async_result.get() for async_result in async_results]

if __name__ == '__main__':

	pass

