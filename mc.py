#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math, threading, json, os.path 
from math import *
from collections import defaultdict
import vinfo, db, geom
from misc import *
import memcache

client = memcache.Client(['127.0.0.1:112029'], debug=0)


