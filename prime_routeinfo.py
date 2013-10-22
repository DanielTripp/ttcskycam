#!/usr/bin/python2.6

import sys, os
from misc import *
import routes 

if __name__ == '__main__':

	print 'Priming route info...'

	# I tend to use these routes more during development, so I'll put them first: 
	froutes = ['dundas', 'dufferin'] + routes.FUDGEROUTES
	for froute in froutes:
		routes.routeinfo(froute)

	print '... done priming route info.'

