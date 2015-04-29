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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random, tempfile
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph, geom
from misc import *

if __name__ == '__main__':

	import poll_locations

	croutes = '''
1S
5
6
7
8
9
10
11
12
14
15
16
17
20
21
22
23
24
25
26
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
94
95
96
97
98
99
100
101
102
103
104
105
106
107
108
109
110
111
112
113
115
116
117
120
122
123
124
125
126
127
129
130
131
132
133
134
135
139
141
142
143
144
145
160
161
162
165
167
168
169
171
172
190
191
192
195
196
198
199
224
300
301
302
303
305
306
307
308
309
310
311
312
313
316
319
320
321
322
324
329
352
353
354
385
501
502
503
504
505
506
508
509
510
511
512
	'''

	croutes = [x for x in [x.strip() for x in croutes.splitlines()] if x]

	num_vehicles_in_known_routes = 0; num_vehicles_in_unknown_routes = 0
	#for route in ['504', '191', '80', '81', '501']:
	for i, route in enumerate(croutes):
		print '%s (%d/%d)...' % (route, i, len(croutes))
		vis_filename = tempfile.mkstemp(prefix=os.path.basename(sys.argv[0]))[1]
		try:
			poll_locations.get_data_from_web_and_deal_with_it(route, 0, False, None, False, vis_filename)
			num_vehicles = count_lines(vis_filename)
			if route in routes.CONFIGROUTES:
				num_vehicles_in_known_routes += num_vehicles
			else:
				num_vehicles_in_unknown_routes += num_vehicles
		finally:
			pass # os.remove(vis_filename)
		time.sleep(1)

	print 'known: %d.  unknown: %d.' % (num_vehicles_in_known_routes, num_vehicles_in_unknown_routes)


