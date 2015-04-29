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

import sys, os, argparse, subprocess

if __name__ == '__main__':

	args = sys.argv[1:]
	opt = any(arg.startswith('--prof') or arg == '-O' for arg in args) or bool(os.getenv('PROF_OPT'))
	args = [arg for arg in args if arg != '-O']
	try:
		subprocess.check_call([sys.executable] + (['-O'] if opt else []) + ['impl-calc-reports.py'] + args)
	except subprocess.CalledProcessError, e:
		# Enough info will probably already be printed to stdout / stderr by the child process.  No need to print it.
		sys.exit(e.returncode)


