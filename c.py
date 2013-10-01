#!/usr/bin/python2.6

with open('VERSION') as fin:
	VERSION = fin.read().strip()

with open('MIN_ZOOM_INCLUSIVE') as fin:
	MIN_ZOOM_INCLUSIVE = int(fin.read().strip())

with open('MAX_ZOOM_INCLUSIVE') as fin:
	MAX_ZOOM_INCLUSIVE = int(fin.read().strip())

VALID_ZOOMS = range(MIN_ZOOM_INCLUSIVE, MAX_ZOOM_INCLUSIVE+1)

REPORTS_MAX_AGE_MINS = 100

if __name__ == '__main__':

	pass




