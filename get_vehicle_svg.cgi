#!/usr/bin/python2.6

print 'Content-type: image/svg+xml\n'

import os, urlparse

def get_arg_strvals(vardict_):
	r = []
	argi = 0
	while True:
		argname='arg%d' % (argi)
		if argname not in vardict_:
			break
		r.append(vardict_[argname][0])
		argi+=1
	return r

def get_arg_objvals(vardict_):
	strvals = get_arg_strvals(vardict_)
	return [int(strvals[0]), int(strvals[1]), strvals[2], float(strvals[3])]



def get_vehicle_svg(size_, heading_, color_, opacity_):
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<g transform="rotate(%d 45 45)" >' + \
			'<polygon points="30,30, 45,15, 60,30, 60,75, 30,75" fill="%s" fill-opacity="%f" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'</g>' + \
			'</svg>') % (size_, size_, heading_, color_, opacity_)




vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
args = get_arg_objvals(vars)

print get_vehicle_svg(*args)


