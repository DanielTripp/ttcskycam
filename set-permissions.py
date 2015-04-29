#!/usr/bin/env python

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

