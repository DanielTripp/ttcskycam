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

			

