#!/usr/bin/env python -O

import sys
import tracks, streets, system, testgraph

if __name__ == '__main__':

	if len(sys.argv) == 1:
		tracks.get_snapgraph()
		streets.get_snapgraph()
		system.get_snapgraph()
		testgraph.get_snapgraph()
	elif len(sys.argv) == 2:
		sgname = sys.argv[1]
		if sgname == 'tracks':
			tracks.get_snapgraph()
		elif sgname == 'streets':
			streets.get_snapgraph()
		elif sgname == 'system':
			system.get_snapgraph()
		elif sgname == 'testgraph':
			testgraph.get_snapgraph()
		else:
			raise Exception()
	else:
		raise Exception()

			

