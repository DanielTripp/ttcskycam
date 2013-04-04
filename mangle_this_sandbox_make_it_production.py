#!/usr/bin/env python

import sys, os, os.path, subprocess, shutil, StringIO, re
from misc import *

def add_python_optimize_flag(file_):
	with open(file_) as fin:
		file_contents = fin.read()
	with open(file_, 'w') as fout:
		for linei, line in enumerate(StringIO.StringIO(file_contents)):
			if linei == 0:
				modified_line = re.sub('([\r\n]+)', ' -O\\1', line)
				fout.write(modified_line)
			else:
				fout.write(line)

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
		touch('GET_CURRENT_REPORTS_FROM_DB')
		touch('DISALLOW_HISTORICAL_REPORTS')

		for pyfile in [f for f in os.listdir('.') if f.endswith('.py')]:
			add_python_optimize_flag(pyfile)


