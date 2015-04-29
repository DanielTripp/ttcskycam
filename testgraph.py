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

import sys, json, os.path, pprint, sqlite3, multiprocessing, time, subprocess, threading
from collections import *
from lru_cache import lru_cache
import vinfo, geom, routes, predictions, mc, c, snapgraph, traffic, picklestore, streets, system
from misc import *

@lru_cache(1)
@picklestore.decorate
def get_snapgraph():
	plines = [
[(43.7892790,-79.4464360), (43.7887370,-79.4466890), (43.7880550,-79.4465780), (43.7838570,-79.4455000), (43.7774810,-79.4439290), (43.7711740,-79.4423370), (43.7665410,-79.4411520), (43.7640310,-79.4405470), (43.7587780,-79.4392770), (43.7554300,-79.4384780), (43.7520970,-79.4376370), (43.7487650,-79.4367960), (43.7405030,-79.4347740), (43.7370300,-79.4338900), (43.7335870,-79.4331130), (43.7283000,-79.4318430), (43.7240210,-79.4308510), (43.7122670,-79.4281430), (43.7052290,-79.4263580), (43.7036100,-79.4259890), (43.7024560,-79.4257050), (43.7012100,-79.4255930), (43.7006300,-79.4253960), (43.6968850,-79.4238890), (43.6919750,-79.4219110), (43.6864510,-79.4196530), (43.6830990,-79.4182760), (43.6773890,-79.4160610), (43.6741450,-79.4148120), (43.6710410,-79.4135200), (43.6669060,-79.4119550), (43.6614570,-79.4097190), (43.6471590,-79.4039420), (43.6367360,-79.3997960), (43.6366100,-79.3998780), (43.6362810,-79.4008870), (43.6360580,-79.4019560), (43.6359630,-79.4030560), (43.6359180,-79.4037330), (43.6359550,-79.4042760), (43.6360580,-79.4048510), (43.6362050,-79.4055840), (43.6363350,-79.4062960), (43.6363830,-79.4070290), (43.6363770,-79.4077780), (43.6362510,-79.4094420), (43.6362280,-79.4099550), (43.6362760,-79.4106030), (43.6365460,-79.4116170), (43.6365960,-79.4117200), (43.6368540,-79.4120480), (43.6370210,-79.4125000), (43.6370300,-79.4126670), (43.6370360,-79.4129180), (43.6368110,-79.4139380), (43.6363700,-79.4155450), (43.6356590,-79.4180680), (43.6356400,-79.4182050), (43.6356670,-79.4182920), (43.6357390,-79.4183360), (43.6357760,-79.4183530), (43.6358160,-79.4183720), (43.6358580,-79.4183710)]
	]

	#r = system.SystemSnapGraph(plines)
	r = snapgraph.SnapGraph(plines)
	return r

if __name__ == '__main__':

	get_snapgraph()



