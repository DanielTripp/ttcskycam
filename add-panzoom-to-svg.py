#!/usr/bin/env python

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

script_elem = ET.Element('script', attrib={'xmlns:xlink': 'http://www.w3.org/1999/xlink', 'xlink:href': 'js/SVGPan.js'})
root.insert(0, script_elem)

print ET.tostring(root)

