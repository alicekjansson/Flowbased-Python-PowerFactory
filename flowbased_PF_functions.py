# -*- coding: utf-8 -*-
"""
Created on Tue Jun 17 10:57:03 2025

@author: alice
"""

# Set up connection to PowerFactory
import os
os.environ["PATH"]=r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1'+os.environ["PATH"]
import sys
sys.path.append(r'C:\Program Files\DIgSILENT\PowerFactory 2025 SP1\Python\3.11')
import powerfactory as pf

#%% POWERFACTORY

#Initialize Powerfactory, defining which studycase is to be activated
#Retrieve application object and activated studycase
def set_up_pf(project,studycase,opscen='None'):
    app=pf.GetApplication()
    # app.SetUserBreakEnabled(1)
    app.ClearOutputWindow()
    app.ActivateProject(project)
    project=app.GetActiveProject()
    if project is None:
        print('Project not found')
        app.PrintError("There is no active Project")
    else:
        app.PrintPlain("Project: " + project.loc_name)
    studycasefolder= app.GetProjectFolder('study')
    studycases=studycasefolder.GetContents()
    for sc in studycases:
        if studycase in str(sc):
            sc.Activate()
            active=sc
    if opscen!='None': 
        #Select Operation Scenario 
        opfolder= app.GetProjectFolder('scen') 
        ops=opfolder.GetContents() 
        op_check=False 
        for op in ops: 
            if opscen in str(op): 
                op.Activate() 
                active=op 
                op_check=True 
        if op_check==False: 
            app.PrintError("There is no active operation scenario") 
    return app, active