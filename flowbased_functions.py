# -*- coding: utf-8 -*-
"""
Created on Tue Jun 24 14:27:38 2025

@author: alice
"""

import pandas as pd

# Create dictionary containing elements in zone
def get_zone(ElmZone):
    zone_nodes=[el for el in ElmZone.GetObjs("ElmTerm") if el.iUsage==0]
    zone_loads = ElmZone.GetObjs("ElmLod")
    zone_genstat = ElmZone.GetObjs("ElmGenStat")
    zone_sym = ElmZone.GetObjs("ElmSym")
    zone_line=ElmZone.GetObjs("ElmLne")
    zone_tr=ElmZone.GetObjs("ElmTr2")
    in_data={'Loads':zone_loads,'GenStat':zone_genstat,'Generators':zone_sym}
    res_data={'Buses':zone_nodes,'Loads':zone_loads,'GenStat':zone_genstat,'Generators':zone_sym,'Lines':zone_line,'Transformers':zone_tr}

    return in_data,res_data


# Update model, run load flow, collect results for each time step
def setup_igm(hour, app, results, bidding_zones, res_elements, bidding_zones_names, tso_data, boundaries, res_collect):
    print(f"Running IGM generation for hour: {hour}")
    q_share= 0.1        # The share of reactive power is assumed to be 10%
    # Update all values according to forecast
    for zone in bidding_zones_names:
        for cat, values in bidding_zones[zone].items():
            for el in values:
                name = el.loc_name
                if tso_data[zone][name]:
                    value = tso_data[zone][name]['Load curve'][hour-1]
                    if cat == 'Loads':
                        el.SetAttribute('plini',value)
                        el.SetAttribute('qlini',value*q_share)
                    else:
                        el.SetAttribute('pgini',value)
    
    # Run load flow
    ldf = app.GetFromStudyCase("ComLdf")
    ierr = ldf.Execute()
    if ierr == 0:
        print("Load Flow command returns no error")
    else:
        print("Load Flow command returns an error: " + str(ierr))   
    
    
    # Populate results dictionary with load flow results data
    for name,zone in res_elements.items():
        for catname, cat in zone.items():
            for el in cat:
                for res in res_collect[catname]:
                    results[name][catname][el.loc_name][res].append(el.GetAttribute(res))
    
    # Then also populate with boundary data
    for bound in boundaries:
        results['Boundaries'][bound.loc_name]['c:Pinter'].append(bound.GetAttribute('c:Pinter'))
        results['Boundaries'][bound.loc_name]['c:Qinter'].append(bound.GetAttribute('c:Qinter'))


# Set up dictionaries with bidding zone data
def bidding_zones(app):
    # Collect data on zones in network
    all_zones=app.GetCalcRelevantObjects("ElmZone")
    bidding_zones = {}
    bidding_zones_names=[]
    res_elements = {}
    for ElmZone in all_zones:
        name= ElmZone.loc_name
        bidding_zones_names.append(name)
        in_data,res_data = get_zone(ElmZone)
        res_elements[name] = res_data
        bidding_zones[name] = in_data
    return bidding_zones, bidding_zones_names, all_zones
    
#Select and activate Operation Scenario 
def open_op(app, hour):
    opscen = f'Hour{hour}'
    opfolder= app.GetProjectFolder('scen') 
    ops=opfolder.GetContents() 
    op_check=False
    for op in ops: 
        op_name = str(op).split('\\')[5]
        op_name = op_name.split('.')[0]
        if opscen == op_name: 
            op.Activate() 
            op_check=True 
            print(f'IGM built for hour {hour}')
    if op_check==False: 
        print("There is no active operation scenario")

# Reset operation scenario to base case        
def reset_op(app):
    opscen = 'Base Scenario'
    #Select Operation Scenario 
    op_check=False 
    opfolder= app.GetProjectFolder('scen') 
    ops=opfolder.GetContents()
    for op in ops: 
        if opscen in str(op): 
            op.Activate() 
            print(f'Activated {opscen}')
            op_check = True
    if op_check==False: 
        print("There is no active operation scenario")
        
# This function calculated ptdf, both with and without contingencies and saves the results as csv files
def calc_ptdf(app,label):
      

    # Note: In PowerFactory, go to Additional Functions -> Sensitivities/ Distribution Factors to calculate zone-to-slack PTDF directly
    # Get Sensitivities/ Distribution Factors object
    ptdf = app.GetFromStudyCase("ComVstab")

    ptdf.iopt_method = 0            # 0: AC Load Flow, balanced, positive sequence
    # OBS: These below may need to be selected manually within PowerFactory!
    ptdf.factors4bus = 1            # Select "Power change -> All buses simultaneously"
    ptdf.calcPtdf = 1               # Select busbars ptdf calculation
    ptdf.isContSens = 0             # De-select consider contingencies
    # ptdf.p_bus=[el for el in all_zones]            # Select bidding zones as busbars to consider
    ptdf.calcRegionSens = 1         # Select "calculate regional sensitivities"
    ptdf.calcBoundSens = 1          # Select "calculate boundary sensitivity between adjacent regions"
    ptdf.calcShiftKeySens = 1       # Select "injection based on GSK"

    # Execute Distribution factors calculation
    ptdf.Execute()

    # Collect results of distribution factor calculation (via conversion to csv)
    res=app.GetFromStudyCase("ComRes")
    res.iopt_exp=6                         # 6: csv
    # res.f_name=rf'C:\Users\alice\OneDrive - Lund University\Dokument\Doktorand IEA\Kurser\Flowbased\Python - Flowbased\PTDF results/ptdf_{hour}.csv'
    res.f_name=rf'C:\Users\alice\OneDrive - Lund University\Dokument\Doktorand IEA\Kurser\Flowbased\Python - Flowbased\PTDF results/ptdf_{label}.csv'
    res.ExportFullRange()
    
    
def calc_F(app, hour, element_list, Fref_cne, Fmax_cne,  lines, cont, cnec = 'None'):
    # Run load flow
    ldf = app.GetFromStudyCase("ComLdf")
    ierr = ldf.Execute()
    if ierr == 0:
        print("Load Flow command returns no error")
    else:
        print("Load Flow command returns an error: " + str(ierr)) 
    for el in element_list:
        for line2 in lines:
            
            if str(el) == str(line2.loc_name):
                F = line2.GetAttribute('m:P:bus1')
                if cont == True:
                    label = f'{el} cont: {cnec}'
                else:
                    label = f'{el}'
                Fref_cne.loc[hour, label] = F
                loading = line2.GetAttribute('c:loading')
                Fmax = F / loading * 100
                Fmax_cne.loc[hour, label] = Fmax
    return Fref_cne, Fmax_cne

def get_ptdf(hour, cnec, CNE, CNEC):
    if cnec == 'None':
        ptdf_res=pd.read_csv(f'./PTDF results/ptdf_{hour}.csv')
        ptdf_cne=ptdf_res[CNE.columns].iloc[1:,:]
        ptdf_cne = ptdf_cne.replace('   ----',0).astype(float)
        ptdf = pd.DataFrame(ptdf_cne)
    else:
        ptdf_res=pd.read_csv(f'./PTDF results/ptdf_{cnec}_{hour}.csv')
        element_list = CNEC.loc[cnec][CNEC.loc[cnec] != 0].index.tolist()
        ptdf_cne=ptdf_res[element_list].iloc[1:,:]
        ptdf_cne = ptdf_cne.replace('   ----',0).astype(float)
        ptdf = pd.DataFrame(ptdf_cne)
        ptdf.columns=[str(cnec) + ' cont: ' + str(el) for el in element_list]
    return ptdf
