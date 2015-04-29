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


