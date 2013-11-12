#!/usr/bin/env python

import sys, os, os.path, subprocess, shutil
from misc import *

if __name__ == '__main__':

	if len(sys.argv) == 1:
		interactive = True
		write_mofrs = None
	elif len(sys.argv) == 2:
		interactive = False
		arg = sys.argv[1]
		if not (arg in ('--write-mofrs', '--no-write-mofrs')):
			raise Exception('illegal argument')
		write_mofrs = (arg == '--write-mofrs')
	else:
		raise Exception()

	def should_proceed():
		if interactive:
			print 'Are you sure?'
			if raw_input() == 'y':
				print 'Again - are you sure?'
				if raw_input() == 'y':
					return True
			return False
		else:
			return True

	if not should_proceed():
		sys.exit('We have been told not to proceed.')
	else:
		if write_mofrs is None:
			print 'Write MOFRs?'
			write_mofrs = (raw_input() == 'y')
		print 'Writing MOFRs: %s' % write_mofrs
		if write_mofrs:
			with open('WRITE_MOFRS', 'w') as fout:
				pass
		
		# The big part - deleting most of the sandbox: 
		for dirpath, dirnames, filenames in os.walk('.'):
			for dirname in [x for x in dirnames if x not in ['psycopg2', 'picklestore']]:
				shutil.rmtree(os.path.join(dirpath, dirname))
			break

		os.remove('paths.sqlitedb')

