"""
GCNHabitatSuitability.pyt
ArcGIS Pro Python Toolbox — GCN Habitat Suitability Calculator

Lightweight wrapper. The tool implementation is in GCNHabitatSuitability.py
alongside this file in the add-in's Install directory.
"""

import arcpy
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from GCNHabitatSuitability import GCNHabitatSuitability


class Toolbox(object):
    def __init__(self):
        self.label = "GCN Habitat Suitability Calculator"
        self.alias = "GCNHabitatSuitability"
        self.tools = [GCNHabitatSuitability]
