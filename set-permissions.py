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

import os, os.path, stat

DIRS_TO_OMIT = ['.hg', '.idea']
EXECUTABLE_EXTENSIONS = ['py', 'wsgi', 'cgi', 'bash', 'sh']

mode_for_dirs = stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH
os.chmod('.', mode_for_dirs)

for root, dirs, files in os.walk('.'):
	for dir_to_omit in DIRS_TO_OMIT:
		if dir_to_omit in dirs:
			dirs.remove(dir_to_omit)
	for directory in dirs:
		os.chmod(os.path.join(root, directory), mode_for_dirs)
	for f in (os.path.join(root, f) for f in files):
		mode = stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IROTH
		if any(f.endswith('.'+ext) for ext in EXECUTABLE_EXTENSIONS):
			mode ^= stat.S_IXUSR ^ stat.S_IXOTH
		os.chmod(f, mode)


