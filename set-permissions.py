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

DIRS_TO_OMIT = ['.svn', '.idea']

os.chmod('.', stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)

for root, dirs, files in os.walk('.'):
	for dir_to_omit in DIRS_TO_OMIT:
		if dir_to_omit in dirs:
			dirs.remove(dir_to_omit)
	for directory in dirs:
		os.chmod(os.path.join(root, directory), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)
	for file in files:
		os.chmod(os.path.join(root, file), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)

