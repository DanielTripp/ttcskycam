#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, StringIO, signal
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, picklestore, streets, testgraph

SANDBOX_REPORT_TIME_EM = str_to_em('2030-01-01 12:00')

ASSUMING_NEVER_A_FUDGEROUTE_PREFIX = ('vid', 'mof', 'dir')

for froute in routes.FUDGEROUTES:
	if any(froute.startswith(prefix) for prefix in ASSUMING_NEVER_A_FUDGEROUTE_PREFIX):
		raise Exception()

def get_model_from_raw_string(str_):
	vis = []; matching_lines = []
	for line in StringIO.StringIO(str_):
		mo = re.match(r'.*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:.\d{3})?).*(43\.\d{3,}).*(-79\.\d{3,}).*', line)
		if mo:
			vis.append((mo.group(1), (float(mo.group(2)), float(mo.group(3)))))
			matching_lines.append(line)
	vis = [(str_to_em(x[0]), x[1]) for x in vis]
	vis.sort(key=lambda x: x[0])
	vis = [((0.0 if i == 0 else (vis[i][0] - vis[i-1][0])/1000.0), vis[i][1]) for i in range(len(vis))]
	vis = [{'time_secs': x[0], 'latlng': x[1]} for x in vis]
	r = {'vis': vis, 'fudgeroute': get_fudgeroute(matching_lines), 'vehicle_type': get_vehicle_type(matching_lines)}
	return r

def get_fudgeroute(lines_):
	froute_to_count = defaultdict(int)
	for line in lines_:
		for prefix in re.findall(r'\b[a-zA-Z]{3}', line):
			if prefix in ASSUMING_NEVER_A_FUDGEROUTE_PREFIX:
				continue
			froute = first(froute for froute in routes.NON_SUBWAY_FUDGEROUTES if froute.startswith(prefix))
			if froute is not None:
				froute_to_count[froute] += 1
	return sorted(froute_to_count.items(), key=lambda x: x[1], reverse=True)[0][0]
	
def get_vehicle_type(lines_):
	return ('streetcar' if vinfo.is_a_streetcar(get_vid(lines_)) else 'bus')

def get_vid(lines_):
	vid_to_count = defaultdict(int)
	for line in lines_:
		for vid in re.findall(r'\b\d{4}\b(?!-)', line):
		#                                 ^^^ years tend to have a dash after them. 
			vid_to_count[vid] += 1
	return sorted(vid_to_count.items(), key=lambda x: x[1], reverse=True)[0][0]

def write_to_file(filename_, model_json_str_):
	if ('/' in filename_) or ('..' in filename_) or (not filename_.startswith('d-model-')) or filename_.endswith('.py'):
		raise Exception('Invalid filename for debug_reports file.')
	with open(filename_, 'w') as fout:
		fout.write(model_json_str_)

def read_from_file(filename_):
	with open(filename_) as fin:
		return json.load(fin)

def write_to_db(model_json_str_):
	model = json.loads(model_json_str_)
	vid = ('4999' if model['vehicle_type'] == 'streetcar' else '1999')
	if vinfo.is_a_streetcar(vid) != (model['vehicle_type'] == 'streetcar'):
		raise Exception()
	db.delete_debug_reports_locations(SANDBOX_REPORT_TIME_EM)
	db.delete_debug_reports_reports(SANDBOX_REPORT_TIME_EM)
	froute = model['fudgeroute']
	croute = routes.FUDGEROUTE_TO_CONFIGROUTES[froute][0]
	vis = []
	prev_time_em = SANDBOX_REPORT_TIME_EM - 1000*60*30
	for model_vi in model['vis']:
		time_em = prev_time_em + int(model_vi['time_secs']*1000)
		prev_time_em = time_em
		if db.SECSSINCEREPORT_BUG_WORKAROUND_ENABLED:
			time_em += db.SECSSINCEREPORT_BUG_WORKAROUND_CONSTANT*1000
		vi = vinfo.VehicleInfo('', 0, vid, model_vi['latlng'][0], model_vi['latlng'][1], True, 
				froute, croute, 0, time_em, time_em, None, None, None, None, None)
		db.insert_vehicle_info(vi)
	reports.make_reports_single_route(SANDBOX_REPORT_TIME_EM, froute, True)

def restart_memcache_and_wsgi():
	mc.restart()
	restart_wsgi_process()

def restart_wsgi_process():
	# This 'kill' doesn't kill the current process right away, but waits up to 5 seconds for this function to exit, 
	# as per https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives > shutdown-timeout.
	os.kill(os.getpid(), signal.SIGINT)

def get_froute_and_dir_and_datetimestr():
	froute_and_dir = db.get_debug_reports_froute_and_dir(SANDBOX_REPORT_TIME_EM)
	if froute_and_dir is None:
		return None
	else:
		return list(froute_and_dir) + [em_to_str_ymdhm(SANDBOX_REPORT_TIME_EM)]

if __name__ == '__main__':

	pass

