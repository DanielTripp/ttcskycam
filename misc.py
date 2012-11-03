#!/usr/bin/python2.6

import sys, os, time, math
from collections import MutableSequence

def em_to_str(t_):
	return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_/1000))

def em_to_str_hm(t_):
	return time.strftime('%H:%M', time.localtime(t_/1000))

def em_to_str_hms(t_):
	return time.strftime('%H:%M:%S', time.localtime(t_/1000))

def now_em():
	return int(time.time()*1000)

def frange(min_, max_, step_):
	x = min_
	while x < max_:
		yield x
		x += step_

def lrange(min_, max_, step_):
	assert step_ != 0
	x = min_
	while (x < max_ if step_ > 0 else x > max_):
		yield x
		x += step_

def m_to_str(m_):
	return '%.2f minutes' % (m_/(1000*60.0))

# eg. given [1, 2, 3, 4], this yields (1, 2), then (2, 3), then (3, 4) 
def hopscotch(iterable_):
	it = iter(iterable_)
	try:
		e1 = it.next()
		e2 = it.next()
		while True:
			yield (e1, e2)
			e3 = it.next()
			e1 = e2
			e2 = e3
	except StopIteration:
		pass

# like hopscotch but generalized. 
def windowiter(iterable_, n_):
	assert n_ >= 1
	it = iter(iterable_)
	try:
		elems = []
		for i in range(n_):
			elems.append(it.next())
		while True:
			yield tuple(elems)
			del elems[0]
			elems.append(it.next())
 	except StopIteration:
		pass

# This is the counterpart to common.js - encode_url_paramval(). 
def decode_url_paramval(str_):
	r = ''
	for i in range(0, len(str_), 2):
		group = ord(str_[i]) - ord('a')
		sub = int(str_[i+1])
		result_char = chr(group*10 + sub)
		r += result_char
	return r

def str_to_em(datetimestr_):
	def impl(format__):
		return int(time.mktime(time.strptime(datetimestr_, format__))*1000)
	try:
		return impl('%Y-%m-%d %H:%M:%S')
	except ValueError:
		return impl('%Y-%m-%d %H:%M')

def printerr(*args):
	sys.stderr.write(' '.join((str(x) for x in args)) + os.linesep)

def is_sorted(iterable_, reverse=False, key=None):
	def get_key(elem__):
		return (elem__ if key==None else key(elem__))
	for a, b in hopscotch(iterable_):
		akey = get_key(a); bkey = get_key(b)
		if (akey < bkey if reverse else akey > bkey):
			return False
	return True

def filter_in_place(list_, predicate_):
	assert isinstance(list_, MutableSequence)
	list_[:] = (e for e in list_ if predicate_(e))

def none(iterable_):
	for e in iterable_:
		if e:
			return False
	return True

def implies(a_, b_):
	return not (a_ and not b_)

def fdiv(x_, y_):
	return int((x_ - math.fmod(x_, y_))/y_)

# 'i' is for 'inclusive'
def intervalii(a_, b_):
	assert (isinstance(a_, int) or isinstance(a_, long)) and (isinstance(b_, int) or isinstance(b_, long))
	if a_ < b_:
		start = a_
		end = b_
	else:
		start = b_
		end = a_
	return range(start, end+1)


def get_range_val(p1_, p2_, domain_val_):
	x1 = float(p1_[0]); y1 = float(p1_[1])
	x2 = float(p2_[0]); y2 = float(p2_[1])
	r = (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1
	if any(type(x) == float for x in p1_ + p2_ + (domain_val_,)):
		return r
	else:
		return int(r)

def avg(lo_, hi_, ratio_):
	r = lo_ + (hi_ - lo_)*ratio_
	if type(lo_) == int and type(hi_) == int:
		return int(r)
	elif type(lo_) == long or type(hi_) == long:
		return long(r)
	else:
		return r

if __name__ == '__main__':

	print intervalii(1, -1)



