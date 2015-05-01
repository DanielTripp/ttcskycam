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

import sys, os, os.path, subprocess, shutil, StringIO, re
from misc import *

def partially_process_php_file(filename_):
	with open(filename_) as fin:
		in_file_contents = fin.read()
	cur_php_block_lines = None
	out_file_content = ''
	for in_line in StringIO.StringIO(in_file_contents):
		if re.match(r'.*<\?php +# *RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION.*', in_line):
			cur_php_block_lines = []
			cur_php_block_lines.append(in_line)
		elif cur_php_block_lines is not None:
			cur_php_block_lines.append(in_line)
			if re.match(r'.*\?>.*', in_line):
				proc = subprocess.Popen(['php'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
				php_block_output = proc.communicate(''.join(cur_php_block_lines))[0]
				cur_php_block_lines = None
				out_file_content += php_block_output
		else:
			out_file_content += in_line
	with open(filename_, 'w') as fout:
		fout.write(out_file_content)

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
		partially_process_php_file('traffic.php')


