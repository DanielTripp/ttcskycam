#!/usr/bin/env python

import sys, os, pickle, threading
from misc import *

LOG = False

g_filename_to_object = {}
g_lock = threading.RLock()

def get_filename(func_, args_, kwargs_):
	assert len(args_) == 0 and len(kwargs_) == 0 # not supported yet 
	r = 'pickled_%s.%s' % (func_.__module__, func_.__name__)
	return r

def decorate(user_function_):
	def decorating_function(*args, **kwargs):
		with g_lock:
			filename = get_filename(user_function_, args, kwargs)
			full_filename = os.path.join('picklestore', filename)
			if filename in g_filename_to_object:
				if LOG: printerr('picklestore: %s: using in-process value.' % filename)
				r = g_filename_to_object[filename]
			else:
				if os.path.exists(full_filename):
					if LOG: printerr('picklestore: %s: reading pickled file.' % filename)
					with open(full_filename) as fin:
						r = pickle.load(fin)
				else:
					if LOG: printerr('picklestore: %s: calling user function.' % filename)
					r = user_function_(*args, **kwargs)
					if LOG: printerr('picklestore: %s: done calling user function.' % filename)
					if LOG: printerr('picklestore: %s: dumping to pickle file.' % filename)
					with open(full_filename, 'w') as fout:
						pickle.dump(r, fout)
					if LOG: printerr('picklestore: %s: done dumping to pickle file.' % filename)
				g_filename_to_object[filename] = r
			return r

	return decorating_function

