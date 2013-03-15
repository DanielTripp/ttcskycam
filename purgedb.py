#!/usr/bin/python2.6

import sys, re
import db

if __name__ == '__main__':

	days_arg = sys.argv[1]
	mo = re.match(r'(\d+)d', days_arg)
	if not mo:
		raise Exception('Need a number-of-days value as argument eg. 5d')
	num_days = int(mo.group(1))
	db.purge(num_days)

