#!/usr/bin/env python

import sys, os, pickle, threading, functools
from misc import *

LOG = os.path.exists('LOG_PICKLESTORE')

g_filename_to_object = {}
g_lock = threading.RLock()

def get_filename(func_, args_, kwargs_):
	funcname = '%s.%s' % (func_.__module__, func_.__name__)
	str_arg_list = [str(arg) for arg in args_] + ['%s=%s' % (kwargname, kwargs_[kwargname]) for kwargname in sorted(kwargs_.keys())]
	r = 'pickled_%s(%s)' % (funcname, ','.join(str_arg_list))
	return r

def decorate(user_function_):
	@functools.wraps(user_function_)
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

