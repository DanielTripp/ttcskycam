#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json
from collections import defaultdict
import routes
from misc import *

class Prediction:

	def __init__(self, froute_, croute_, stoptag_, time_retrieved_, time_, vehicle_id_, is_departure_, block_, dir_tag_, trip_tag_, 
			branch_, affected_by_layover_, is_schedule_based_, delayed_):
		self.froute = froute_
		self.croute = croute_
		self.stoptag = stoptag_
		self.time_retrieved = time_retrieved_
		self.time = time_
		self.vehicle_id = vehicle_id_
		self.is_departure = is_departure_
		self.block = block_
		self.dirtag = dir_tag_
		self.triptag = trip_tag_
		self.branch = branch_
		self.affected_by_layover = affected_by_layover_
		self.is_schedule_based = is_schedule_based_
		self.delayed = delayed_

	@classmethod
	def from_xml(cls, froute_, croute_, stoptag_, time_retrieved_, xml_elem_):
		if xml_elem_.nodeName == 'prediction':

			def a(attr_name_, default_=''):
				r = xml_elem_.getAttribute(attr_name_)
				if r == '':
					r = default_
				return r
				
			return cls(froute_, croute_, stoptag_, time_retrieved_, long(a('epochTime')), a('vehicle'), a('isDeparture'), 
					a('block'), a('dirTag'), a('tripTag'), a('branch'), a('affectedByLayover', False), 
					a('isScheduleBased', False), a('delayed', False))
		else:
			raise Exception('Could not recognize prediction XML element "%s"' % xml_elem_.toxml())

	def __str__(self):
		return 'Prediction(%s(%s) stop %s retrieved %s - time=%s, vid=%s)' % (self.froute, self.croute, self.stoptag, 
			em_to_str(self.time_retrieved), em_to_str_hms(self.time), self.vehicle_id)

	def __repr__(self):
		return self.__str__()

if __name__ == '__main__':

	import pprint 

	pprint.pprint(get_predictions('queen', '6528', '6830'))


