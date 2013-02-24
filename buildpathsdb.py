#!/usr/bin/python2.6

import sys, json, os.path, pprint, sqlite3, getopt
import paths
from misc import *

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['fill-in'])
	assert len(args) == 0
	paths.build_db_main(bool(get_opt(opts, 'fill-in')))


