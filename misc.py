#!/usr/bin/python2.6

import sys, os, os.path, time, math, datetime, calendar, bisect, tempfile, subprocess
from collections import MutableSequence, defaultdict

def em_to_str(t_):
	if t_ is None or t_ == 0:
		return None
	else:
		return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_/1000))

def em_to_str_millis(t_):
	format = '%Y-%m-%d %H:%M:%S'
	secs_formatted = time.strftime(format, time.localtime(t_/1000))
	millis = t_ - time.mktime(time.strptime(secs_formatted, format))*1000  # Hack.
	return '%s.%03d' % (secs_formatted, millis)

def em_to_str_hm(t_):
	return time.strftime('%H:%M', time.localtime(t_/1000))

def em_to_str_hms(t_):
	return time.strftime('%H:%M:%S', time.localtime(t_/1000))

def now_em():
	return int(time.time()*1000)

def now_str():
	return em_to_str(now_em())

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
	return int((x_ - (x_ % y_))/y_)

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
	if abs(x2 - x1) < 0.000000001: # special case - would normally cause a divide-by-zero error - but we'll let the caller 
			# get away with it sometimes: 
		if abs(y2 - y1) < 0.0000000001 and abs(domain_val_ - x1) < 0.0000000001:
			return y1
		else:
			raise ZeroDivisionError()
	r = (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1
	if any(type(x) == float for x in p1_ + p2_ + (domain_val_,)): # are any arguments floats?
		return r
	elif any(type(x) == long for x in p1_ + p2_ + (domain_val_,)): # are any arguments longs?
		return long(r)
	else:
		return int(r)

def avg(lo_, hi_, ratio_=0.5):
	r = lo_ + (hi_ - lo_)*ratio_
	if type(lo_) == int and type(hi_) == int:
		return int(r)
	elif type(lo_) == long or type(hi_) == long:
		return long(r)
	else:
		return r

def average(seq_):
	num_elems = 0
	sum = 0
	for e in seq_:
		sum += e
		num_elems += 1
	return sum/float(num_elems)

def file_under_key(list_, key_, assume_no_duplicate_keys_=False):
	assert callable(key_)
	if assume_no_duplicate_keys_:
		r = {}
		for e in list_:
			key = key_(e)
			if key in r:
				raise Exception('duplicate key "%s" found' % key)
			r[key] = e
		return r
	else:
		r = defaultdict(lambda: [])
		for e in list_:
			r[key_(e)].append(e)
		return dict(r)

# Return only elements for which predicate is true.  Group them as they appeared in input list as runs of trues.
def get_maximal_sublists2(list_, predicate_):
	cur_sublist = None
	r = []
	for e1, e2 in hopscotch(list_):
		if predicate_(e1, e2):
			if cur_sublist is None:
				cur_sublist = [e1]
				r.append(cur_sublist)
			cur_sublist.append(e2)
		else:
			cur_sublist = None
	return r

# Return all input elements, but group them by runs of the same key.
def get_maximal_sublists3(list_, key_):
	assert callable(key_)
	if not list_:
		return list_
	cur_sublist = [list_[0]]
	r = [cur_sublist]
	prev_elem_key = key_(list_[0])
	for prev_elem, cur_elem in hopscotch(list_):
		cur_elem_key = key_(cur_elem)
		if prev_elem_key == cur_elem_key:
			cur_sublist.append(cur_elem)
		else:
			cur_sublist = [cur_elem]
			r.append(cur_sublist)
		prev_elem_key = cur_elem_key
	return r

def uniq(seq_):
	first_elem = True
	last_val = None
	r = []
	for e in seq_:
		if first_elem or (e != last_val):
			r.append(e)
		last_val = e
		first_elem = False
	return r

def mofrs_to_dir(start_mofr_, dest_mofr_):
	if start_mofr_ == -1 or dest_mofr_ == -1:
		return None
	elif dest_mofr_ > start_mofr_:
		return 0
	elif dest_mofr_ < start_mofr_:
		return 1
	else:
		return None

# param round_step_millis_ if 0, don't round down.  (Indeed, don't round at all.) 
def massage_time_arg(time_, round_step_millis_=0):
	if isinstance(time_, str):
		r = str_to_em(time_)
	elif time_==0:
		r = now_em()
	else:
		r = time_
	if round_step_millis_ != 0:
		r = round_down(r, round_step_millis_)
	return r

# 'off step' means 'steps shifted in phase by half the period, if you will'  
def round_up_off_step(x_, step_):
	r = round_down_off_step(x_, step_)
	return r if r == x_ else r+step_

def round_down_off_step(x_, step_):
	assert type(x_) == int and type(step_) == int
	return ((x_-step_/2)/step_)*step_ + step_/2

def round_up(x_, step_):
	r = round_down(x_, step_)
	if isinstance(x_, float):
		return r if abs(r - x_) < 0.00001 else r+step_
	else:
		return r if r == x_ else r+step_

def round_down(x_, step_):
	assert type(x_) in (int, long, float)
	if type(x_) in (int, long):
		r = (long(x_)/step_)*step_
		if type(x_) is int:
			r = int(r)
		return r
	else:
		return fdiv(x_, step_)*step_

def round(x_, step_):
	rd = round_down(x_, step_)
	ru = round_up(x_, step_)
	return (rd if x_ - rd < ru - x_ else ru)

def first(iterable_, predicate_):
	for e in iterable_:
		if predicate_(e):
			return e
	return None

def round_down_by_minute(t_em_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute) # Omitting second on purpose.  That's what
			# does the rounding down.
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def round_down_by_minute_step(t_em_, step_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, round_down(dt.minute, step_)) # Omitting second on purpose.  That's what
			# does the rounding down by minute.
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def round_up_by_minute(t_em_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
	if dt.second > 0:
		dt -= datetime.timedelta(seconds=dt.second)
		dt += datetime.timedelta(minutes=1)
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def betweenii(a_, b_, c_):
	return (a_ <= b_ <= c_) or (c_ <= b_ <= a_)

# maintains a list of sorted keys available through sortedkeys().  also a floor*() method.
class sorteddict(dict):

	_pop_default_arg_not_supplied_sentinel_object = object()

	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)
		self.refresh_sortedkeys()

	# Making this a tuple because we don't want to have to make and return a copy in sortedkeys(), 
	# because that was too slow (took cumulatively half a second in a simple path-finding test case.)
	def refresh_sortedkeys(self):
		self._sortedkeys = tuple(sorted(self.keys()))

	def __setitem__(self, key, value):
		dict.__setitem__(self, key, value)
		self.refresh_sortedkeys()

	def __delitem__(self, key):
		dict.__delitem__(self, key)
		self.refresh_sortedkeys()

	def clear(self):
		dict.clear(self)
		self.refresh_sortedkeys()

	def copy(self):
		return sorteddict([(k, v) for k, v in self.iteritems()])

	def pop(self, key, default=_pop_default_arg_not_supplied_sentinel_object):
		try:
			return dict.pop(self, key)
		finally:
			self.refresh_sortedkeys()

	def popitem(self):
		try:
			return dict.popitem(self)
		finally:
			self.refresh_sortedkeys()

	def setdefault(self, key, default=None):
		try:
			return dict.setdefault(key, default)
		finally:
			self.refresh_sortedkeys()

	def sortedkeys(self):
		return self._sortedkeys

	def ceilitem(self, key_):
		assert len(self) == len(self._sortedkeys)
		if not self:
			raise KeyError('Can\'t call ceilitem on an empty sorteddict.')
		idx = bisect.bisect_left(self._sortedkeys, key_)
		if idx == len(self):
			raise KeyError('No key greater than or equal to "%s" was found in this sorteddict.' % key_)
		rkey = self._sortedkeys[idx]
		rval = self[rkey]
		return (rkey, rval)

	def flooritem(self, key_):
		assert len(self) == len(self._sortedkeys)
		if not self:
			raise KeyError('Can\'t call flooritem on an empty sorteddict.')
		idx = bisect.bisect_right(self._sortedkeys, key_)-1
		if idx < 0:
			raise KeyError('No key less than or equal to "%s" was found in this sorteddict.' % key_)
		rkey = self._sortedkeys[idx]
		rval = self[rkey]
		return (rkey, rval)

	# Returns items in the list immediately lesser and greater than given key.
	# If key arg exists in this dict, it is not returned.
	# eg. self = {0: '', 5: '', 10: ''}. boundingitems(5) = ((0, ''), (10, '')).  boundingitems(6) = ((5, ''), (10, ''))
	# boundingitems(11) = ((10, ''), None)
	# arg itempredicate takes 2 args (key and value) and should return True if that item indicated is acceptable to
	# return from this function.  If False then this function will keep searching, upward or downward.
	def boundingitems(self, key_, itempredicate=None):
		assert len(self) == len(self._sortedkeys)
		if len(self) == 0:
			return (None, None)

		idx = bisect.bisect_left(self._sortedkeys, key_)

		def get_acceptable_key(start_key_idx__, search_upward_aot_downward__):
			if not (0 <= start_key_idx__ < len(self)):
				return None
			if itempredicate is not None:
				idx = start_key_idx__
				while 0 <= idx < len(self):
					if itempredicate(self._sortedkeys[idx], self[self._sortedkeys[idx]]):
						return self._sortedkeys[idx]
						break
					idx += (1 if search_upward_aot_downward__ else -1)
				else:
					return None
			else:
				return self._sortedkeys[start_key_idx__]

		lo_key = get_acceptable_key(idx-1, False)
		hi_key = get_acceptable_key((idx if key_ not in self else idx+1), True)

		def get_item(key__):
			return ((key__, self[key__]) if key__ is not None else None)
		return (get_item(lo_key), get_item(hi_key))

	def boundingvalues(self, key_, itempredicate=None):
		ritems = self.boundingitems(key_, itempredicate=itempredicate)
		def get_value(item__):
			return (item__[1] if item__ is not None else None)
		return (get_value(ritems[0]), get_value(ritems[1]))

def get_dir_tag_int(dir_tag_str_):
	assert isinstance(dir_tag_str_, basestring)
	is0 = '_0_' in dir_tag_str_
	is1 = '_1_' in dir_tag_str_
	if is0 and is1:
		raise Exception('dir_tag seems to indicate both directions (0 and 1).  %s' % dir_tag_str_)
	elif is0:
		return 0
	elif is1:
		return 1
	else:
		return None

def is_valid_time_em(time_em_):
	return abs(now_em() - time_em_) < 1000*60*60*24*365*20

# I checked the NextBus schedules of about 10 routes and they all had the same set of
# serviceClass values: sat, sun, and wkd.
def time_to_serviceclass(time_em_):
	assert is_valid_time_em(time_em_) # asserting a reasonable epoch-time-in-millis argument.
	dt = datetime.date.fromtimestamp(time_em_/1000.0)
	if dt.weekday() == 5:
		return 'sat'
	elif dt.weekday() == 6:
		return 'sun'
	else:
		return 'wkd'

def get_time_millis_within_day(time_em_):
	assert is_valid_time_em(time_em_)
	dt = datetime.datetime.fromtimestamp(time_em_/1000.0)
	return dt.hour*60*60*1000 + dt.minute*60*1000 + dt.second*1000

# TODO: make sure we handle daylight savings time (this was written in winter), first day of DST in the spring,
# first day of non-DST in the fall, and if really keen - the dark of night on those DST-switching days.
# (What is the TTC's policy for it?)
# I don't know what all code would need to be changed in order to handle these things.

def round_down_to_midnight(time_em_):
	assert is_valid_time_em(time_em_)
	dt = datetime.datetime.fromtimestamp(time_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day)
	return long(time.mktime(dt.timetuple())*1000)

def millis_within_day_to_str(m_):
	assert 0 <= m_ <= 1000*60*60*48 # NextBus schedules use values greater than 1000*60*60*24 for times after midnight.
		# The TTC service day seems to start around 5:00 or 6:00 AM.
	hour = m_/(1000*60*60)
	minute = (m_ - hour*1000*60*60)/(1000*60)
	second = (m_ - (hour*1000*60*60 + minute*1000*60))/(1000)
	while hour > 23:
		hour -= 24
	return '%02d:%02d:%02d' % (hour, minute, second)

def invert_dict(dict_):
	if dict_ is None:
		return None
	elif len(dict_) == 0:
		return {}
	else:
		if len(set(dict_.values())) != len(dict_):
			raise Exception('Can\'t invert dict.  Contains duplicate values.')
		return dict((v,k) for k, v in dict_.iteritems())

def get_opt(opts_, optname_):
	for e in opts_:
		if e[0] == '--'+optname_:
			if e[1] == '':
				return True
			else:
				return e[1]
	else:
		return None

def redirect_stdstreams_to_file(filename_prefix_):
	file = os.path.expanduser('~/ttc-logs/%s%s.txt' % (filename_prefix_, datetime.datetime.now().strftime('%Y-%m-%d')))
	if not os.path.exists(os.path.dirname(file)):
		os.makedirs(os.path.dirname(file))
	fout = open(file, 'a+')
	sys.stdout = fout
	sys.stderr = fout

def remove_consecutive_duplicates(list_, key=None):
	if len(list_) < 2:
		return
	def get_key(val_):
		return (val_ if key==None else key(val_))
	curkey = get_key(list_[0]); prevkey = None
	i = 1
	while i < len(list_):
		prevkey = curkey
		curkey = get_key(list_[i])
		if prevkey == curkey:
			del list_[i]
			i -= 1
			curkey = prevkey
		i += 1

def svg_to_png(svgstr_):
	tmpdir = ('/tmp/dt' if os.path.isdir('/tmp/dt') else '/tmp')
	svg_fileno, svg_filename = tempfile.mkstemp('.svg', 'ttc-temp-svg-to-png-', tmpdir)
	svg_file = os.fdopen(svg_fileno, 'w')
	svg_file.write(svgstr_)
	svg_file.close()
	subprocess.check_call(['java', '-jar', 'batik-1.7/batik-rasterizer.jar', svg_filename], \
			stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))

	assert svg_filename[-4:] == '.svg'
	png_filename = svg_filename[:-4] + '.png' # batik just created this .png file, with a name based on the svg filename. 

	with open(png_filename, 'rb') as png_fin:
		png_contents = png_fin.read()
	os.remove(svg_filename)
	os.remove(png_filename)
	return png_contents


if __name__ == '__main__':

	print invert_dict({1: 'a', 2: 'b'})

