#!/usr/bin/python2.6 -O

import tracks, streets, system

if __name__ == '__main__':

	tracks.get_snapgraph()
	streets.get_snapgraph()
	system.get_snapgraph()

