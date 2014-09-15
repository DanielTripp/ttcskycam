#!/usr/bin/env python

import sys, os, os.path, subprocess, shutil, time
from misc import *

if __name__ == '__main__':

	for i in xrange(10, -1, -1):
		print 'Will mangle this sandbox in %d seconds...' % i
		time.sleep(1)

	for dirpath, dirnames, filenames in os.walk('.'):
		for dirname in [x for x in dirnames if x not in ['psycopg2', 'picklestore', 'yaml']]:
			shutil.rmtree(os.path.join(dirpath, dirname))
		break


