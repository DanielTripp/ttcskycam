#!/usr/bin/python2.6

import sys, os, os.path, time, math, datetime, calendar, bisect, tempfile, subprocess, StringIO, re, multiprocessing
from collections import Sequence, MutableSequence, defaultdict, MutableSet
from itertools import *
import db, mc

def initializer():
	db.forget_connection()
	mc.forget_connection()

def run(n_, func_, argses_):
	pool = multiprocessing.Pool(n_, initializer=initializer)
	results = []
	for args in argses_:
		results.append(pool.apply_async(func_, args))
	returnvals = []
	for result in results:
		returnvals.append(result.get())
	pool.close()
	pool.join()
	return returnvals

if __name__ == '__main__':

	pass

