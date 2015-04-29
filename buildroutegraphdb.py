#!/usr/bin/env python -O

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

import sys, json, os.path, pprint, sqlite3, getopt
import paths
from misc import *

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['fill-in'])
	assert len(args) == 0
	system.build_db(bool(get_opt(opts, 'fill-in')))


