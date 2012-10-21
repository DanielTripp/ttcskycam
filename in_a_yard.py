#!/usr/bin/env python

import sys
import db

lat = float(sys.argv[1].strip(','))
lon = float(sys.argv[2])
print db.in_a_yard_latlon((lat, lon))

