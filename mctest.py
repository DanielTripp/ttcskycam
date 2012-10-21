#!/usr/bin/python2.6

import memcache

mc = memcache.Client(['127.0.0.1:112029'], debug=0)

for i in range(1, 1000):
	key = 'key4-%d' % (i)
	mc.set(key, ('skfh sdkjfh %d sjkdfh %d sjkdhf jkh %d fsjkfh skjfh%d sjkdh fjksdhf ' % (i, i, i, i))*10000)
	print mc.get(key) != None
	#if i % 500 == 0:
	print i


