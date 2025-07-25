# -*- coding: utf-8 -*-
"""
Created on Mon Jul 21 14:18:35 2025

@author: alice
"""

import numpy
import json
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import matplotlib
import os

# Set up connection to PowerFactory
os.environ["PATH"]=r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1'+os.environ["PATH"]
import sys
sys.path.append(r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1\Python\3.11')
import powerfactory as pf
from flowbased_PF_functions import set_up_pf


# Update model to IGM
def build_igm(hour, app, bidding_zones,  bidding_zones_names, tso_data, boundaries):
    print(f"Building IGM for hour: {hour}")
    
    # Update all values according to forecast
    for zone in bidding_zones_names:
        for cat, values in bidding_zones[zone].items():
            for el in values:
                name = el.loc_name
                if tso_data[zone][name]:
                    value = tso_data[zone][name]['Load curve'][hour-1]
                    if cat == 'Loads':
                        el.SetAttribute('plini',value)
                        el.SetAttribute('qlini',value*0.1)
                    else:
                        el.SetAttribute('pgini',value)
    
    # Run load flow
    ldf = app.GetFromStudyCase("ComLdf")
    ierr = ldf.Execute()
    if ierr == 0:
        print("Load Flow command returns no error")
    else:
        print("Load Flow command returns an error: " + str(ierr))   

        
def reset_gridmodel(app, bidding_zones, bidding_zones_names, tso_data):
    print('Resetting load flow simulation')
    for zone in bidding_zones_names:
        for cat, values in bidding_zones[zone].items():
            for el in values:
                name = el.loc_name
                if tso_data[zone][name]:
                    
                    value = tso_data[zone][name]['Static Power (MW)']
                    if cat == 'Loads':
                        el.SetAttribute('plini',value)
                        el.SetAttribute('qlini',value*0.1)
                    else:
                        el.SetAttribute('pgini',value)