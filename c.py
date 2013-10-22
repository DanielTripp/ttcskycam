#!/usr/bin/python2.6

with open('VERSION') as fin:
	VERSION = fin.read().strip()

with open('MIN_GUIZOOM') as fin:
	MIN_ZOOM = int(fin.read().strip())

with open('MAX_GUIZOOM') as fin:
	MAX_ZOOM = int(fin.read().strip())

VALID_GUIZOOMS = range(MIN_ZOOM, MAX_ZOOM+1)

REPORTS_MAX_AGE_MINS = 100

VALID_DATAZOOMS = [0, 1, 2, 3]
GUIZOOM_TO_DATAZOOM = {19: 3, 18: 3, 17: 3, 16: 3, 15: 2, 14: 2, 13: 1, 12: 0, 11: 0, 10: 0}
DATAZOOM_TO_RSDT =     {0: 60,  1: 20,  2: 5,   3: 1}
# It might be a good idea to make sure that the values here are only even numbers.  Some arithmetic might depend on that.  (Not sure.)
DATAZOOM_TO_MOFRSTEP = {0: 560, 1: 280, 2: 140, 3: 70}
assert len(VALID_DATAZOOMS) == len(set(VALID_DATAZOOMS))
assert set(GUIZOOM_TO_DATAZOOM.values()) == set(DATAZOOM_TO_RSDT.keys()) == set(DATAZOOM_TO_MOFRSTEP.keys()) == set(VALID_DATAZOOMS)
MIN_DATAZOOM = min(VALID_DATAZOOMS)
MAX_DATAZOOM = max(VALID_DATAZOOMS)

if __name__ == '__main__':

	pass




