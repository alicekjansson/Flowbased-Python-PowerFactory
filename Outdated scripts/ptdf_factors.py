# -*- coding: utf-8 -*-
"""
Created on Mon Jul 28 09:40:38 2025

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
from flowbased_functions import get_zone, calc_ptdf, calc_F, get_ptdf, open_op, bidding_zones

# Set up connection to PowerFactory
os.environ["PATH"]=r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1'+os.environ["PATH"]
import sys
sys.path.append(r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1\Python\3.11')
import powerfactory as pf
from flowbased_PF_functions import set_up_pf


# Set up PowerFactory
# app,studycase=set_up_pf('Transmission System','01 Load Flow','Base Scenario') 
app,studycase=set_up_pf('Transmission System','02 Contingency Analysis','Base Scenario') 
app.Show()              # De-select for faster calculations

# Collect boundaries
boundaries = app.GetCalcRelevantObjects("ElmBoundary")

bidding_zones = bidding_zones(app)

#%% Load CRAC files

all_results = pd.read_csv('./cnec results/all results.csv',index_col=0)
all_results = all_results[[col for col in all_results if 'c:loading' in col]]       # Filter to only consider loading results
all_results.columns=[str(el).split('/')[2] for el in all_results.columns]           # Simplify by changing column names to element name only


CNEC= pd.read_csv('./cnec results/CNEC_df.csv',index_col=0)
# Select elements with overloads
# Index is list of outages
# Columns is list of overloaded elements during outages
CNEC = CNEC[~(CNEC == 0).all(axis=1)].drop('No Cont')
# Now create dict that for each contingency (line outage) defined the elements that should be monitored
CNEC_elements = {}
for name in CNEC.columns:
    CNEC_elements[name] = CNEC[name][CNEC[name] != 0].index.tolist()

#%%
CNE= pd.read_csv('./cnec results/CNE_list.csv',index_col=0)

# Collect loading results for all CNE(C) elements in dataframe
# CNEC_elements_all = CNE.columns.append(CNEC.columns).drop_duplicates()
# CNEC_res = all_results[[col for col in all_results if any(keyword == col for keyword in CNEC_elements_all)]]

#%%

# Create space to save ptdf results (calculated below)
if not os.path.exists('./PTDF results'):
    os.mkdir('./PTDF results')


Fmax_cne = pd.DataFrame(index=range(1,25))
Fref_cne = pd.DataFrame(index=range(1,25))
    
hour = 1
# Select and open operation scenario
open_op(app,hour)

# Collect line elements
lines = app.GetCalcRelevantObjects("ElmLne")
element_list = CNE.columns
Fref_cne, Fmax_cne = calc_F(app, hour,element_list, Fref_cne, Fmax_cne,  lines, False)
# Calculate ptdf without contingencies
calc_ptdf(app,f'{hour}')  
# Then, do this for contingencies
for cnec in CNEC_elements.keys():
    for line in lines:
            if str(cnec) == str(line.loc_name):
                line.outserv = 1    # Set line out of service
                # Calculate PTDF under this contingency
                calc_ptdf(app,f'{cnec}_{hour}')
                # Calculate values of Fref and Fmax under this contingency
                element_list = CNEC.loc[cnec][CNEC.loc[cnec] != 0].index.tolist()
                Fref_cne, Fmax_cne = calc_F(app, hour,element_list, Fref_cne, Fmax_cne,  lines, True, cnec)
                # Then put line back into service
                line.outserv = 0    
    

#%% Read ptdf calculated values for this hour


# First collect ptdf for CNE
ptdf = get_ptdf(hour, 'None', CNE, CNEC)

# Then loop through the CNEC
for cnec in CNEC_elements.keys():
    temp = get_ptdf(hour, cnec, CNE, CNEC)
    # Join on index
    ptdf = ptdf.join(temp)
