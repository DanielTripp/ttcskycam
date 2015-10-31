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

import sys
from misc import *

if __name__ == '__main__':

	args = sys.argv[1:]
	if args:
		print [decode_url_paramval(v) for v in encoded_vals]
	else:
		for line in sys.stdin:
			decoded_args = []
			for space_split in line.split(' '):
				for ampersand_split in space_split.split('&'):
					if '=' in ampersand_split:
						possible_arg = ampersand_split.split('=')[1]
						try:
							decoded_args.append(decode_url_paramval(possible_arg))
						except:
							pass
			print decoded_args

