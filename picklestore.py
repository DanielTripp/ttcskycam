#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys, os, cPickle, threading, functools
from misc import *

LOG = os.path.exists('LOG_PICKLESTORE')

g_filename_to_object = {}
g_lock = threading.RLock()

def get_filename(func_, args_, kwargs_):
	funcname = '%s.%s' % (func_.__module__, func_.__name__)
	str_arg_list = [str(arg) for arg in args_] + ['%s=%s' % (kwargname, kwargs_[kwargname]) for kwargname in sorted(kwargs_.keys())]
	r = '%s(%s)' % (funcname, ','.join(str_arg_list))
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
						r = cPickle.load(fin)
					if LOG: printerr('picklestore: %s: finished reading pickled file.' % filename)
				else:
					if LOG: printerr('picklestore: %s: calling user function.' % filename)
					r = user_function_(*args, **kwargs)
					if LOG: printerr('picklestore: %s: done calling user function.' % filename)
					if LOG: printerr('picklestore: %s: dumping to pickle file.' % filename)
					with open(full_filename, 'wb') as fout:
						cPickle.dump(r, fout)
					if LOG: printerr('picklestore: %s: done dumping to pickle file.' % filename)
				g_filename_to_object[filename] = r
			return r

	return decorating_function

