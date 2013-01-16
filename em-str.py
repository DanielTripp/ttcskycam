#!/usr/bin/python2.6

import sys, time, re
import misc

arg = sys.argv[1]
if re.match('^\\d+$', arg):
	print misc.em_to_str(int(arg))
else:
	print misc.str_to_em(arg)
	

