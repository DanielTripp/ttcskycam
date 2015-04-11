#!/usr/bin/env python

import sys, os, os.path, subprocess, shutil, time, os
from misc import *

if __name__ == '__main__':

	for i in xrange(10, -1, -1):
		print 'Will mangle this sandbox in %d seconds...' % i
		time.sleep(1)

	for dirpath, dirnames, filenames in os.walk('.'):
		dirnames[:] = []
		for filename in filenames:
			if filename.endswith('.php') or filename.endswith('.html'):
				os.remove(os.path.join(dirpath, filename))


