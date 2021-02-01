#!/cygdrive/c/Users/dt/AppData/Local/Programs/Python/Python38/python.exe

import os, sys, random
import psycopg2
import db

def file_to_string(filename_):
  with open(filename_) as fin:
    return fin.read()

PASSWORD = file_to_string(os.path.expanduser('~/.ttcskycam/DB_PASSWORD')).strip()

g_conn = None

def connect():
  global g_conn
  DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='dt' host='localhost' password='%s'" % PASSWORD,)
  DATABASE_CONNECT_KEYWORD_ARGS = {}
  g_conn = psycopg2.connect(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

def conn():
  if g_conn is None:
    connect()
  return g_conn

def vi_select_generator(croute_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=True, vid_=None, \
      forward_in_time_order_=False):
	# 2021: ignoring blank route 
	# 2021: including unpredictables 
	assert vid_ is None or len(vid_) > 0
	curs = (conn().cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else conn().cursor())
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir_)) if dir_ != None else ' ')
	#columns = '*'
	columns = ' graph_locs  '
	sql = 'select '+columns+' from ttc_vehicle_locations where '\
		+('route_tag = %s ')\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time_retrieved <= %s and time_retrieved > %s '\
		+(' and vehicle_id = %s ' if vid_ else ' and vehicle_id != \'\' ') \
		+ dir_clause \
		+(' order by time' if forward_in_time_order_ else ' order by time desc')
	curs.execute(sql, [croute_, end_time_em_, start_time_em_] + ([vid_] if vid_ else []))
	while True:
		row = curs.fetchone()
		if not row:
			break
		#vi = vinfo.VehicleInfo.from_db(*row)
		yield row
	curs.close()

if 0:
	end_time_em = 1611929399123
	for e in vi_select_generator('505', end_time_em, end_time_em - 1000*60*30):
		print(e)

if 1:
	num_minutes = 30
	direction = 0
	datazoom = 3
	time_window_end = 1612112400000
	log = True
	db.get_recent_vehicle_locations('dundas', num_minutes, direction, datazoom, time_window_end, log)



