#!/usr/bin/python2.6

import os, os.path, stat

DIRS_TO_OMIT = ['.svn', '.idea']

for root, dirs, files in os.walk('.'):
	for dir_to_omit in DIRS_TO_OMIT:
		if dir_to_omit in dirs:
			dirs.remove(dir_to_omit)
	for dir in dirs:
		os.chmod(os.path.join(root, dir), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)
	for file in files:
		os.chmod(os.path.join(root, file), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)

