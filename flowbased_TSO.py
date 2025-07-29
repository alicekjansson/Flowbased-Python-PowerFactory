# -*- coding: utf-8 -*-
"""
Created on Thu Jul 24 11:36:43 2025

@author: alice
"""

import numpy
import pickle
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import matplotlib
import os
warnings.filterwarnings('ignore')
from flowbased_functions import get_zone, setup_igm

# Create connection to data folder
if not os.path.exists('./data'):
    os.mkdir('./data')
if not os.path.exists('./data/ToRCC'):
    os.mkdir('./data/ToRCC')
if not os.path.exists('./data/IGM'):
    os.mkdir('./data/IGM')

# Create temporary storage folder for TSO
if not os.path.exists('./temp'):
    os.mkdir('./temp')

# Set up connection to PowerFactory
os.environ["PATH"]=r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1'+os.environ["PATH"]
import sys
sys.path.append(r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1\Python\3.11')
import powerfactory as pf
from flowbased_PF_functions import set_up_pf

# app,studycase=set_up_pf('Transmission System','01 Load Flow','Base Scenario') 
app,studycase=set_up_pf('Transmission System','02 Contingency Analysis','Base Scenario') 
app.Show()

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
    
# Collect boundaries
boundaries = app.GetCalcRelevantObjects("ElmBoundary")

#%%
# D-2 forecasted load and generation data
# Define relative load curves of 24 hours
data_curves={}
data_curves['Load']=[0.2, 0.2, 0.3, 0.3, 0.3, 0.3 , 0.5, 0.6, 0.8, 0.9, 0.9, 1, 1, 1 , 0.9, 0.9, 0.8, 0.9, 0.9, 0.7, 0.5, 0.4, 0.3, 0.3]
data_curves['Photovoltaic']=[0,0,0,0,0,0,0.1,0.3,0.5,0.7,0.8,0.9,1,0.9,0.8,0.7,0.5,0.3,0.1,0,0,0,0,0]
data_curves['Wind']=[0.5,0.5,0.7,0.7,0.8,0.8,0.8,0.5,0.5,0.6,0.6,0.5,0.5,0.5,0.4,0.4,0.3,0.4,0.3,0.3,0.2,0.2,0.2,0.2]
data_curves['Nuclear']=[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
data_curves['Oil']=[el*0.8 for el in data_curves['Load']]
data_curves['Coal']=[el*0.8 for el in data_curves['Load']]
data_curves['Gas']=[el*0.8 for el in data_curves['Load']]

pd.DataFrame(data_curves).to_csv(r'.\data\ToRCC\D-2data.csv')

#%% Update dictionary of TSO data

# Create table with all elements and their load curves
tso_data={}
for name,zone in bidding_zones.items():
    
    zone_dict = {}
    for key,val in zone.items():
        for el in val:
            dic = {}
            if (key == 'GenStat') | (key == 'Generators'):
                dic['Category'] = el.GetAttribute('cCategory')
                dic['Static Power (MW)'] = el.pgini
                dic['Load curve'] = [dic['Static Power (MW)'] * i for i in data_curves[dic['Category']]]
            elif key == 'Loads': 
                dic['Category'] = 'Load'
                dic['Static Power (MW)'] = el.plini
                dic['Load curve'] = [dic['Static Power (MW)'] * i for i in data_curves[dic['Category']]]
            zone_dict[el.loc_name] = dic
    tso_data[name] = zone_dict

# Save dictionary    
with open('./data/ToRCC/tso_data.pkl', 'wb') as f:
    pickle.dump(tso_data, f)
    
    
#%%
# Set up folder to store plots
if not os.path.exists('./figures'):
    os.mkdir('./figures')

# Plot forecasted values for each bidding zone
for zone, values in tso_data.items():
    fig,ax=plt.subplots(1,figsize=(8,5))
    for name, data in values.items():
        if data:
            ax.plot(data['Load curve'],label = name)
    ax.set_xlabel('Hour',fontsize='large')
    ax.set_ylabel('Load (MW)',fontsize='large')
    ax.set_title(f'Predicted values {zone}')
    # ax.set_ylim([0,16])
    plt.legend(fontsize='large')
    plt.savefig(rf'./figures/{zone} TSO Data', bbox_inches='tight')
    plt.show() 
    
#%% Define results to be stored


# First, define results to be collected
res_collect = {}
res_collect['Loads'] = ['plini','qlini']
res_collect['GenStat'] = ['pgini','qgini']
res_collect['Photovoltaic'] = ['pgini','qgini']
res_collect['Generators'] = ['pgini','qgini']
res_collect['Lines'] = ['m:P:bus1','m:Q:bus1','c:loading','n:u:bus1']
res_collect['Transformers'] = ['c:loading']
res_collect['Buses'] = ['m:u']

# Create results dictionary
results={}
for name,zone in res_elements.items():
    zone_dict = {}
    for catname, cat in zone.items():
        cat_dict = {}
        for el in cat:
            el_dict = {}
            for res in res_collect[catname]:
                el_dict[res] = []
            cat_dict[el.loc_name] = el_dict
        zone_dict[catname] = cat_dict
    results[name] = zone_dict
# Also set up boundaries results
results['Boundaries']={}
for bound in boundaries:
    results['Boundaries'][bound.loc_name]={'c:Pinter':[],'c:Qinter':[]}


#%% Update model for each time step
# This is implemented by storing each timestep in an operation scenario. Could be done in other ways
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
            setup_igm(hour, app, results, bidding_zones, res_elements, bidding_zones_names, tso_data, boundaries, res_collect)
            print(f'IGM built for hour {hour}')
    if op_check==False: 
        print("There is no active operation scenario")

#%%
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
#%% Save results for all elements in a dataframe
# Collect all columns and their data into a flat dictionary
flat_results = {}

# Loop through everything except 'Boundaries'
for zone_name, zone_data in results.items():
    if zone_name == 'Boundaries':
        continue
    for cat_name, cat_data in zone_data.items():
        for el_name, res_dict in cat_data.items():
            for res_name, res_list in res_dict.items():
                if res_name == 'm:u':
                    continue  # Skip voltages
                col_name = f"{zone_name}/{cat_name}/{el_name}/{res_name}"
                flat_results[col_name] = res_list

# Handle Boundaries separately
for bound_name, bound_data in results.get('Boundaries', {}).items():
    for res_name, res_list in bound_data.items():
        if res_name == 'M:u':
            continue  # Skip 'M:u'
        col_name = f"Boundaries/{bound_name}/{res_name}"
        flat_results[col_name] = res_list
# Create DataFrame
df_res = pd.DataFrame.from_dict(flat_results, orient='columns')
df_res.to_csv(r'./cnec results/all results.csv')

#%% Plot selected results

for item, values in results['Boundaries'].items():
    fig,ax=plt.subplots(1,figsize=(8,5))
    ax.plot(values['c:Pinter'],label = 'P')
    ax.plot(values['c:Qinter'],label = 'Q')
    ax.set_xlabel('Hour',fontsize='large')
    ax.set_ylabel('Load (MW)',fontsize='large')
    ax.set_title(f'Boundary flows: {item}')
    # ax.set_ylim([-2000,500])
    plt.legend(fontsize='large')
    plt.savefig(rf'./figures/{item} Boundary Resulting Flows', bbox_inches='tight')
    # plt.show() 
    
#%% Contingency List, Remedial Actions and Additional Constraints (CRAC)
# These would be determined by power system analysts at TSO
# Here, a list of contingencies are created based on the elements that sometime in the results are overloaded or have voltage issues

# Find and plot elements with violations

# To store violating elements
CNE = []
CNE_loading=[]

if not os.path.exists('./cnec results'):
    os.mkdir('./cnec results')


# CNE - Critical Network Element

# Set up folder to store result plots
if not os.path.exists('./figures/violations'):
    os.mkdir('./figures/violations')

# Loop through all results
for zone_name, zone_data in results.items():
    if zone_name != 'Boundaries':
        for cat_name, cat_data in zone_data.items():
            for el_name, el_data in cat_data.items():
    
                violated = False  # Flag to check if element violates any condition
    
                for res_type, values in el_data.items():
                    # Check for overload
                    if res_type == 'c:loading' and any(v > 100 for v in values) and cat_name == 'Lines':
                        CNE.append(el_name)
                        CNE_loading.append(values)
                        violated = True
    
                    # Check for voltage violation
                    if res_type == 'm:u' and any(v < 0.95 or v > 1.05 for v in values) and cat_name == 'Lines':
                        CNE.append( el_name)
                        violated = True
    
                # Only plot if this element violated
                if violated and cat_name == 'Lines':
                    plt.figure(figsize=(8, 5))
                    for res_type, values in el_data.items():
                        plt.plot(values, label=res_type)
                    plt.title(f"{zone_name} - {cat_name} - {el_name} (VIOLATION)")
                    plt.xlabel("Time Step")
                    plt.ylabel("Values")
                    plt.legend()
                    plt.grid(True)
                    plt.tight_layout()
                    plt.savefig(rf'./figures/violations/{zone_name} - {cat_name} - {el_name} (VIOLATION).jpg', bbox_inches='tight')
                    plt.show()

print (f'Critical Network Elements: {CNE}')

CNE_df=pd.DataFrame(columns=CNE)
for i,col in enumerate(CNE_loading):
    CNE_df.iloc[:,i] = col

CNE_df.to_csv(r'./cnec results/CNE_list.csv')


#%% CNEC - Critical Network Element with Contingency

CNEC= []


# Activate Contingency StudyCase
# studycases= app.GetProjectFolder('study').GetContents()
# for sc in studycases:
#     if ('Contingency') in str(sc):
#         sc.Activate()
#         active=sc

# Get element        
cont = app.GetFromStudyCase("ComSimoutage")
# Define limits
cont.SetLimits(0.95,1.05,100)
# Perform contingency analysis and return fault code
fault_check = cont.ExecuteAndCheck()
if fault_check == 0:
    print('Contingency calculation succesful')
else:
    print(f'Contingency analysis returns fault: {fault_check}')
# Collect results (via conversion to csv)
res=app.GetFromStudyCase("ComRes")
res.iopt_exp=6                         # 6: csv
res.f_name=r'C:\Users\alice\OneDrive - Lund University\Dokument\Doktorand IEA\Kurser\Flowbased\Python - Flowbased\cnec results/contingencies.csv'
res.ExportFullRange()

contingencies = pd.read_csv('./cnec results/contingencies.csv',index_col=0)
        
# # Go back to original studycase
# for sc in studycases:
#     if ('01') in str(sc):
#         sc.Activate()
#         active=sc
        
# To simplify here, I have chosen to only consider overloaded branches (not voltage issues)

# Create a boolean mask for desired columns
mask = contingencies.iloc[0].isin(["Loading in %", "Object index"])

# Use the mask to filter columns, only keeping columns containing loading
contingencies = contingencies.loc[:, mask].iloc[1:,:].replace("   ----",0).astype(float)
# Keep only columns that have contingencies (loaded above 80%)
CNEC = contingencies.loc[:, (contingencies > 80).any()].columns.tolist()

#%%
CNEC_df = contingencies[CNEC]
CNEC_df.index=[int(abs(float(el))) for el in CNEC_df.index]

CNEC_elements = pd.read_csv('./cnec results/List of contingencies (elements).csv',index_col=0).dropna()
CNEC_elements.loc['No Cont']={'Number':0}

# Change index of CNEC_df to corresponding line
number_to_index = CNEC_elements.set_index('Number').index.to_series()
CNEC_df.index = CNEC_df.index.map(lambda x: CNEC_elements[CNEC_elements["Number"] == x].index[0])

pd.DataFrame(CNEC_df).to_csv(r'./cnec results/CNEC_df.csv')
pd.DataFrame(CNEC).to_csv(r'./cnec results/CNEC_list.csv')

# CDC - Combined Dynamic Constraint. These are not calculated specifically in this code.

#%% Generation and Load Shiftkeys

GLSK_strat = 3                  # Select strategy (3: Relative participation to installed capacity)
GLSK = {}

for zone, values in tso_data.items():
    zone_dict = {}
    # Filter for generators
    gen_units = {name: data['Static Power (MW)'] for name, data in values.items() if data['Category'] != 'Load'}
    # Calculate the total generation capacity in the zone
    total_capacity = sum(gen_units.values())
    # Normalize each unit's capacity
    if total_capacity > 0:
        zone_dict = {name: capacity / total_capacity for name, capacity in gen_units.items()}
    # Store the normalized generation distribution for the zone
    GLSK[zone] = zone_dict
    
# TO-DO: IMPLEMENT THE OTHER STRATEGIES

#%% Send over information to RCC

# At this point, send over IGM, CRAC (IG-100), Bidding zone definitions (IG-101), GLSK (IG-103)
