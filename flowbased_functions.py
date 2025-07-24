# -*- coding: utf-8 -*-
"""
Created on Tue Jun 24 14:27:38 2025

@author: alice
"""

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