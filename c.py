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

import os

VERSION_FILENAME = 'VERSION'

with open(VERSION_FILENAME) as fin:
	VERSION = fin.read().strip()

with open('MIN_GUIZOOM') as fin:
	MIN_ZOOM = int(fin.read().strip())

with open('MAX_GUIZOOM') as fin:
	MAX_ZOOM = int(fin.read().strip())

with open(os.path.join('tracks', 'GRAPH_VERSION')) as fin:
	TRACKS_GRAPH_VERSION = int(fin.read().strip())

with open('STREETS_GRAPH_VERSION') as fin:
	STREETS_GRAPH_VERSION = int(fin.read().strip())

VALID_GUIZOOMS = range(MIN_ZOOM, MAX_ZOOM+1)

REPORTS_MAX_AGE_MINS = 100

VALID_DATAZOOMS = [0, 1, 2, 3]
GUIZOOM_TO_DATAZOOM = {19: 3, 18: 3, 17: 3, 16: 3, 15: 2, 14: 2, 13: 1, 12: 0, 11: 0, 10: 0}
DATAZOOM_TO_RDP_EPSILON = {0: 60, 1: 20, 2: 5, 3: 1}
# It might be a good idea to make sure that the values here are only even numbers.  Some arithmetic might depend on that.  (Not sure.)
DATAZOOM_TO_MOFRSTEP = {0: 560, 1: 280, 2: 140, 3: 70}
assert len(VALID_DATAZOOMS) == len(set(VALID_DATAZOOMS))
assert set(GUIZOOM_TO_DATAZOOM.values()) == set(DATAZOOM_TO_RDP_EPSILON.keys()) == set(DATAZOOM_TO_MOFRSTEP.keys()) == set(VALID_DATAZOOMS)
MIN_DATAZOOM = min(VALID_DATAZOOMS)
MAX_DATAZOOM = max(VALID_DATAZOOMS)

# In meters.  This is more or less a maximum GPS error - that is, the maximum 
# distance that there could be between a lat/lng sample and where that 
# vehicle really is.  I think that this is in the right ballpark but the 
# thinking here (and nearby) probably isn't as clear as it should be.  For 
# example, I haven't considered here the maximum distance between where I 
# think a road or streetcar track is and where it really is.  Or the vertex 
# distance tolerance that was used when building the vertex list for each 
# instance of SnapGraph - that is, the maximum distance apart two line or 
# points can be while still being considered to intersect.  Neither have I 
# considered the maximum distance that can be introduced between a polyline 
# and it's RDP-simplified version.
# 150 meters might seem high but I observed 140 before - vid 4114, 2014-01-31 11:14:47.
GRAPH_SNAP_RADIUS = 150 

USE_PATCHCACHES = os.path.exists('USE_PATCHCACHES')

if __name__ == '__main__':

	pass




