#!/usr/bin/env python

import sys, os, os.path, subprocess, shutil

if __name__ == '__main__':

	if len(sys.argv) == 1:
		interactive = True
	elif len(sys.argv) == 2 and sys.argv[1] == '--yes':
		interactive = False
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
		for dirpath, dirnames, filenames in os.walk('.'):
			if '.svn' in dirnames:
				shutil.rmtree(os.path.join(dirpath, '.svn'))
				dirnames.remove('.svn')

		os.remove('dev-options-for-traffic-php.txt')

