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

filename = sys.argv[1]

import xml.etree.ElementTree as ET
tree = ET.parse(filename)

# Prevent 'ns0' prefix from being inserted everywhere.  
# Thanks http://stackoverflow.com/questions/3895951/create-svg-xml-document-without-ns0-namespace-using-python-elementtree 
ET.register_namespace("","http://www.w3.org/2000/svg")

root = tree.getroot()

roots_children = list(root)
for root_child in roots_children:
	root.remove(root_child)
viewport_elem = ET.Element('g', attrib={'id': 'viewport', 'transform': 'translate(200,200)'})
for root_child in roots_children:
	viewport_elem.append(root_child)
root.append(viewport_elem)

script_elem = ET.Element('script', attrib={'xmlns:xlink': 'http://www.w3.org/1999/xlink', 'xlink:href': '../js/SVGPan.js'})
root.insert(0, script_elem)

tree.write(filename)


