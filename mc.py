#!/usr/bin/python2.6

import memcache

client = memcache.Client(['127.0.0.1:2029'], debug=0)


