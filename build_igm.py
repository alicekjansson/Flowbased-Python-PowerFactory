# -*- coding: utf-8 -*-
"""
Created on Thu Jul 24 11:11:59 2025

@author: alice
"""

import numpy as np
import json
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import matplotlib
import os
import pickle
from flowbased_functions import get_zone

# Set up connection to PowerFactory
os.environ["PATH"]=r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1'+os.environ["PATH"]
import sys
sys.path.append(r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1\Python\3.11')
import powerfactory as pf
from flowbased_PF_functions import set_up_pf

# Set up PowerFactory
app,studycase=set_up_pf('Transmission System','01 Load Flow','Base Scenario') 
app.Show()

# Collect boundaries
boundaries = app.GetCalcRelevantObjects("ElmBoundary")

# Collect data on zones in network
all_zones=app.GetCalcRelevantObjects("ElmZone")

# Set up dictionaries with bidding zone data
bidding_zones = {}
bidding_zones_names=[]
res_elements = {}
for ElmZone in all_zones:
    name= ElmZone.loc_name
    bidding_zones_names.append(name)
    in_data,res_data = get_zone(ElmZone)
    res_elements[name] = res_data
    bidding_zones[name] = in_data
    
# Load tso_data dictionary
with open('./data/ToRCC/tso_data.pkl', 'rb') as f:
    tso_data = pickle.load(f)


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

# # Update model for each time step
for hour in range(1,25):
    opscen = f'Hour{hour}'
    #Select Operation Scenario 
    opfolder= app.GetProjectFolder('scen') 
    ops=opfolder.GetContents() 
    op_check=False 
    for op in ops: 
        op_name = str(op).split('\\')[5]
        op_name = op_name.split('.')[0]
        if opscen == op_name: 
            op.Activate() 
            active=op 
            op_check=True 
            build_igm(hour, app, bidding_zones, bidding_zones_names, tso_data, boundaries)
            print(f'IGM built for hour {hour}')
    if op_check==False: 
        print("There is no active operation scenario")
    
# After simulation, reset original load flow values
# reset_gridmodel(app, bidding_zones, bidding_zones_names, tso_data)