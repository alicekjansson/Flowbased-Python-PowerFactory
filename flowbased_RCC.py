# -*- coding: utf-8 -*-
"""
Created on Mon Jul 21 13:58:01 2025

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

#%% Load CRAC files

all_results = pd.read_csv('./cnec results/all results.csv',index_col=0)
all_results = all_results[[col for col in all_results if 'c:loading' in col]]       # Filter to only consider loading results
all_results.columns=[str(el).split('/')[2] for el in all_results.columns]           # Simplify by changing column names to element name only


CNEC= pd.read_csv('./cnec results/CNEC_df.csv',index_col=0)
# Select elements with overloads
# Index is list of outages
# Columns is list of overloaded elements during outages
CNEC = CNEC[~(CNEC == 0).all(axis=1)].drop('No Cont')

CNE= pd.read_csv('./cnec results/CNE_list.csv',index_col=0)

# Collect loading results for all CNE(C) elements in dataframe
CNEC_elements = CNE.columns.append(CNEC.columns).drop_duplicates()
CNEC_res = all_results[[col for col in all_results if any(keyword == col for keyword in CNEC_elements)]]

#%% Calculate Fmax and Fref

# Create space to save ptdf results (calculated below)
if not os.path.exists('./PTDF results'):
    os.mkdir('./PTDF results')

q_share= 0.1        # The share of reactive power is assumed to be 10%
Fmax_cne = pd.DataFrame(columns=CNEC.columns,index=range(1,25))
Fref_cne = pd.DataFrame(columns=CNEC.columns,index=range(1,25))


# Collect line elements
lines = app.GetCalcRelevantObjects("ElmLne")

# Collect NPref, the net positions of each area
NPs = pd.DataFrame(columns=bidding_zones_names,index=range(1,25))

# Update model, run load flow, collect results for each time step
for hour in range(1,25):
    #Select Operation Scenario 
    opscen = f'Hour{hour}'
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
            print(f'IGM built for hour {hour}')
    if op_check==False: 
        print("There is no active operation scenario")
    # Run load flow
    ldf = app.GetFromStudyCase("ComLdf")
    ierr = ldf.Execute()
    if ierr == 0:
        print("Load Flow command returns no error")
    else:
        print("Load Flow command returns an error: " + str(ierr))   
    # For each CNE, calculate Fmax and collect Fref
    for cne_el, Fref in CNEC.items():
       for line in lines:
           if str(cne_el) == str(line.loc_name):
              
              F = line.GetAttribute('m:P:bus1')
              Fref_cne[cne_el][hour]=F
              loading = line.GetAttribute('c:loading')
              Fmax = F / loading * 100
              Fmax_cne[cne_el][hour] = Fmax
              
    for zone in all_zones:
        NPs[zone.loc_name][hour]=zone.GetAttribute('c:InterP')
    
    # Note: In PowerFactory, go to Additional Functions -> Sensitivities/ Distribution Factors to calculate zone-to-slack PTDF directly
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
    res.f_name=rf'C:\Users\alice\OneDrive - Lund University\Dokument\Doktorand IEA\Kurser\Flowbased\Python - Flowbased\PTDF results/ptdf_{hour}.csv'
    res.ExportFullRange()

    
# After simulation, reset original load flow values
# reset_gridmodel(app, bidding_zones, bidding_zones_names, tso_data)

# Then go back to original operation scenario
opscen = 'Base Scenario'
#Select Operation Scenario 
op_check=False 
for op in ops: 
    if opscen in str(op): 
        op.Activate() 
        print(f'Activated {opscen}')
        op_check = True
if op_check==False: 
    print("There is no active operation scenario")


#%% Calculate F0

# Transform into numpy array


F0_all = pd.DataFrame(index=range(1,25),columns=CNEC.columns)

for hour in range(1,25):
    # Read ptdf calculated values for this hour
    ptdf_res=pd.read_csv(f'./PTDF results/ptdf_{hour}.csv')
    # Now we want to filter to show the CNE and CNEC elements only
    ptdf_cnec=ptdf_res[CNEC.columns].iloc[1:,:].transpose()
    ptdf_cnec = ptdf_cnec.replace('   ----',0).astype(float)
    ptdf = np.array(ptdf_cnec)

    # Select rows for the hour and transform into numpy arrays
    Fref = np.array(Fref_cne.iloc[hour-1,:].astype(float))
    
    NP = np.array(NPs.iloc[hour-1,:].astype(float))
    
    # Calculate F0 by using matrix multiplication
    F0 = Fref - np.dot(ptdf, NP)
    F0_all.iloc[hour-1,:] = F0

F0_all = F0_all.astype(float)

#%% Calculate RAM per CNEC

# RAM = Fmax + Fra - Frm - F0 - Faac
# Fmax has been calculated above
# Fra: "Remedial action" defined by TSO. NOT IMPLEMENTED HERE.
# Frm: Flow reliability margin. Defined as to cover "95 % of all modelling errors"
# F0 has been calculated above
# Faac: "Already allocated capacity" (ancillary service/ FFR) given by TSO. NOT IMPLEMENTED HERE.

RAM_all = pd.DataFrame(index=range(1,25),columns=CNEC.columns)

for hour in range(1,25):
    Fmax = np.array(Fmax_cne.iloc[hour-1,:].astype(float))
    RAM = Fmax - F0 * 0.95          # Instead of Frm value, multiply by 0.95 to add some margin
    RAM_all.iloc[hour-1,:] = RAM
    
RAM_all = RAM_all.astype(float)

#%% Create a list of all FB domains

FB_domains = []

for hour in range(1,25):
    FB = pd.DataFrame(index=CNEC.columns)
    FB['CNEC'] = CNEC.columns
    FB['RAM'] = RAM_all.iloc[hour-1,:]
    for zone in ptdf_cnec.columns:
        FB[zone] = ptdf_cnec[zone]
    FB_domains.append(FB)

