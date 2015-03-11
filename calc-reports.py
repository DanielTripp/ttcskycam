#!/usr/bin/python2.6

import sys, os, argparse, subprocess

if __name__ == '__main__':

	args = sys.argv[1:]
	opt = any(arg.startswith('--prof') for arg in args) or bool(os.getenv('PROF_OPT'))
	args = [arg for arg in args if arg != '-O']
	try:
		subprocess.check_call([sys.executable] + (['-O'] if opt else []) + ['impl-calc-reports.py'] + args)
	except subprocess.CalledProcessError, e:
		pass # Enough info will probably already be printed to stdout / stderr by the child process. 

