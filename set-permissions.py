#!/usr/bin/python2.6

import os, os.path, stat

for root, dirs, files in os.walk('.'):
	for dir in dirs:
		os.chmod(os.path.join(root, dir), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)
	for file in files:
		if file.endswith('.py') or file.endswith('.pyc'):
			os.chmod(os.path.join(root, file), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR)
		else:
			os.chmod(os.path.join(root, file), stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IXUSR ^ stat.S_IROTH ^ stat.S_IXOTH)

#		public:
#		json
#		html
#		js
#		cgi
#		gif
#		png
#		css


#os.chmod(path, 
#stat.S_IRUSR
#stat.S_IWUSR
#stat.S_IXUSR
#stat.S_IROTH
#stat.S_IWOTH
#stat.S_IXOTH
#
#)
