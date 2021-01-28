#!/cygdrive/c/Python27/python.exe

import sys, os, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt, tempfile
import fcntl
from collections import *
from xml.parsers.expat import ExpatError
import db, vinfo, routes, tracks, streets
from misc import *

if __name__ == '__main__':

	with open(r'C:\cygwin64\tmp\filelocktest.txt', 'a+') as fileObj:
		fcntl.lockf(fileObj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
		time.sleep(5)



