# -*- coding: utf-8 -*-
"""
Created on Mon Jul 21 13:58:01 2025

@author: alice
"""

import numpy
import json
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import matplotlib
import os
import pickle
from flowbased_RCC_functions import build_igm, reset_gridmodel
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

#%% Zone to Slack PTDF

# In PowerFactory, go to Additional Functions -> Sensitivities/ Distribution Factors to calculate zone-to-slack PTDF directly

if not os.path.exists('./PTDF results'):
    os.mkdir('./PTDF results')

# Get Sensitivities/ Distribution Factors object
ptdf = app.GetFromStudyCase("ComVstab")

ptdf.iopt_method = 0            # 0: AC Load Flow, balanced, positive sequence
ptdf.calcPtdf = 1               # Select busbars ptdf calculation
# ptdf.p_bus=[el for el in all_zones]            # Select bidding zones as busbars to consider
ptdf.calcRegionSens = 1         # Select "calculate regional sensitivities"
ptdf.calcBoundSens = 1          # Select "calculate boundary sensitivity between adjacent regions"
ptdf.calcShiftKeySens = 1       # Select "injection based on GSK"

# T-_DO Do this once per 24h time step!
# TO-DO Do this also with contingencies!

# Execute Distribution factors calculation
ptdf.Execute()

# Collect results of distribution factor calculation (via conversion to csv)
res=app.GetFromStudyCase("ComRes")
res.iopt_exp=6                         # 6: csv
res.f_name=r'C:\Users\alice\OneDrive - Lund University\Dokument\Doktorand IEA\Kurser\Flowbased\Python - Flowbased\PTDF results/ptdf.csv'
res.ExportFullRange()

ptdf_res=pd.read_csv('./PTDF results/ptdf.csv')



#%%

CNEC= pd.read_csv('./cnec results/CNEC_list.csv',index_col=0)
CNE= pd.read_csv('./cnec results/CNE_list.csv',index_col=0)
# Now we want to filter to show the CNE and CNEC elements only
ptdf_cnec=ptdf_res[CNE].iloc[1:,:].transpose()

#%% Calculate Fmax and Fref

q_share= 0.1        # The share of reactive power is assumed to be 10%

Fmax_values = []
Fref_values = []

hour = 0 
build_igm(hour, app, bidding_zones, bidding_zones_names, tso_data, boundaries)

# For each CNE, 

# After simulation, reset original load flow values
reset_gridmodel(app, bidding_zones, bidding_zones_names, tso_data)
