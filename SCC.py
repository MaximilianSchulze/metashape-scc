# SCC (Sparse Cloud Cleaning) Script for Agisoft Metashape Professional.
# 
# Executing this script in Agisoft Metashape Professional allows for automated camera model optimization.
#
# The implemented cleaning steps follow the suggestions detailed in the Open-File report 2021-1039, published by Over et al. (2021):
# Over, J.-S.R., Ritchie, A.C., Kranenburg, C.J., Brown, J.A., Buscombe, D.D., Noble, T., Sherwood, C.R., Warring, J.A., Wernette, P.A., 2021.
# Processing coastal imagery with Agisoft Metashape Professional Edition, version 1.6 - Structure from motion workflow documentation. US Geological Surey.
#
# Author: Maximilian Schulze, University of Cologne, Germany
# E-Mail: maximilian.schulze@uni-koeln.de
# April 2023
# Tested on Agisoft Metashape Professional ver. 2.1.0.175730



import Metashape
from PySide2.QtWidgets import *
from PySide2 import QtGui, QtCore, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtGui import QFont, QFontDatabase


import math
import json
import os.path
import os
import datetime 

from collections import OrderedDict
from copy import deepcopy



class NewWindow(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.resize(840, 400)

        self.setWindowTitle('Sparse Cloud Cleaning')
        
        self.doc = Metashape.app.document

        self.chunk = self.doc.chunks[0]

        self.camera_check_boxes = {}
        
        self.parameters = {'Reconstruction Uncertainty' : (0, 100, 1),
                           'Projection Accuracy' : (0, 20, 1),
                           'Reprojection Error' : (0, 200, 0.01),
                           'Reprojection Error (RMSE Minimization)' : (0, 200, 0.01),
                           }

        self.camera_fit_dict = OrderedDict({"Fit f" : True, "Fit k1" : True, "Fit k2" : True, "Fit k3" : True, "Fit k4" : False, 
                                       "Fit cx, cy" : True, "Fit p1" : True, "Fit p2" : True, "Fit b1" : False, "Fit b2" : False, 
                                       "Adaptive camera model fitting" : False, "Estimate tie point covariance" : True, 
                                       "Fit additional corrections" : False})
                                       
                                       
        self.default_values = { 'Reconstruction Uncertainty':{'target_percent': 50., 'target_threshold': 10.,   'max_iter':1, 'tiepoint_accuracy':self.chunk.tiepoint_accuracy},
                                'Projection Accuracy'       :{'target_percent': 50., 'target_threshold': 3. ,   'max_iter':1, 'tiepoint_accuracy':self.chunk.tiepoint_accuracy},
                                'Reprojection Error'        :{'target_percent': 10., 'target_threshold': 0.3,   'max_iter':200, 'tiepoint_accuracy':self.chunk.tiepoint_accuracy},
                                'Reprojection Error (RMSE Minimization)'  :{'target_percent': 10., 'target_threshold': 0.18,  'max_iter':200, 'tiepoint_accuracy':self.chunk.tiepoint_accuracy},
                                
                               }
        
        # dictionary to store chunk specific settings and results
        # important to restore when user switches chunks
        self.chunk_memory = {}
          
        self.chunk_combo_box = QComboBox()
           
        # dictionary for storing the widgets to which access is needed
        self.step_widgets = {}

        self.tiepoint_ledits = {}
        self.chunk_dict = {}
        
        for chunk in self.doc.chunks:
            self.chunk_combo_box.addItem(chunk.label)
            self.addChunk(chunk)

   
        self.chunk_combo_box.currentIndexChanged.connect(self.setCurrentChunk)
        self.chunk_combo_box.currentIndexChanged.connect(self.checkIfChunkInComboBox)
        self.chunk_combo_box.currentIndexChanged.connect(self.setChunkSpecificValues)

        self.chunk_label = QLabel('Name: ')
        self.chunk_label.setStyleSheet("border: none;")
         
        chunk_group_box = QGroupBox('Chunk Selection')
        chunk_group_box.setStyleSheet("QGroupBox { border: 1px solid lightgrey;}")
        chunk_group_box_layout = QHBoxLayout()
        chunk_group_box.setLayout(chunk_group_box_layout)
        chunk_group_box_layout.addWidget(self.chunk_label)
        chunk_group_box_layout.addWidget(self.chunk_combo_box)
        
      
        

        self.tabwidget = QTabWidget()
    
        tab1 = self.makeStepWindow(step = 'Reconstruction Uncertainty', 
                                   target_percent=self.default_values['Reconstruction Uncertainty']['target_percent'], 
                                   target_threshold=self.default_values['Reconstruction Uncertainty']['target_threshold'],  
                                   max_iter=self.default_values['Reconstruction Uncertainty']['max_iter'])
                                   
                                   
        tab2 = self.makeStepWindow(step = 'Projection Accuracy', 
                                   target_percent=self.default_values['Projection Accuracy']['target_percent'],
                                   target_threshold=self.default_values['Projection Accuracy']['target_threshold'], 
                                   max_iter=self.default_values['Projection Accuracy']['max_iter'])
           
        
        tab3 = self.makeStepWindow(step = 'Reprojection Error', 
                                   target_percent=self.default_values['Reprojection Error']['target_percent'], 
                                   target_threshold=self.default_values['Reprojection Error']['target_threshold'],  
                                   max_iter=self.default_values['Reprojection Error']['max_iter'])
        
        
        tab4 = self.makeStepWindow(step = 'Reprojection Error (RMSE Minimization)', 
                                   target_percent=self.default_values['Reprojection Error (RMSE Minimization)']['target_percent'], 
                                   target_threshold=self.default_values['Reprojection Error (RMSE Minimization)']['target_threshold'],  
                                   max_iter=self.default_values['Reprojection Error (RMSE Minimization)']['max_iter'])

        sum = self.makeSummaryWindow()

        self.tabwidget.addTab(tab1, "Step 1")
        self.tabwidget.addTab(tab2, "Step 2")
        self.tabwidget.addTab(tab3, "Step 3")
        self.tabwidget.addTab(tab4, "Step 4")
       


        self.auto_run_check_boxes = {'Reconstruction Uncertainty': QCheckBox('Step 1        '),
                                     'Projection Accuracy': QCheckBox('Step 2         '),
                                     'Reprojection Error': QCheckBox('Step 3'),
                                     'Reprojection Error (RMSE Minimization)': QCheckBox('Step 4'),
                                     }


        self.auto_run_group_box =  QGroupBox('Auto. Run')
        auto_run_group_box_layout = QGridLayout()

        self.auto_run_check_boxes['Reconstruction Uncertainty'].setChecked(True)
        self.auto_run_check_boxes['Projection Accuracy'].setChecked(True)
        self.auto_run_check_boxes['Reprojection Error'].setChecked(True)


        auto_run_button = QPushButton('Run', default=False, autoDefault=False)
        auto_run_button.setFixedSize(QtCore.QSize(5, 20))

        auto_run_button.clicked.connect(self.runAllButtonClicked)


        auto_run_group_box_layout.addWidget(self.auto_run_check_boxes['Reconstruction Uncertainty'], 0, 0)
        auto_run_group_box_layout.addWidget(self.auto_run_check_boxes['Projection Accuracy'], 1, 0)
        auto_run_group_box_layout.addWidget(self.auto_run_check_boxes['Reprojection Error'], 0, 1)
        auto_run_group_box_layout.addWidget(self.auto_run_check_boxes['Reprojection Error (RMSE Minimization)'], 1, 1)
        auto_run_group_box_layout.addWidget(auto_run_button, 1, 2)

        self.auto_run_group_box.setLayout(auto_run_group_box_layout)
        self.auto_run_group_box.setStyleSheet("QGroupBox { border: 1px solid lightgrey;}")
        self.auto_run_group_box.setCheckable(True)
        self.auto_run_group_box.setChecked(True)

        self.auto_run_group_box.clicked.connect(self.switchRunButtonsEnabledDisabled)
	
        self.preferences_widget = QWidget()
        self.preferences_widget.setStyleSheet("border: none;")
     
        self.preferences_widget_layout = QGridLayout()
        
        self.preferences_widget_layout.addWidget( chunk_group_box )
        self.preferences_widget_layout.addWidget(self.auto_run_group_box )

        w = QWidget()
        w.resize(510, 210)

        self.tw = QTreeWidget(self)
     

        self.tw.resize(500, 200)
        self.tw.setColumnCount(2)
        self.tw.setHeaderLabels(["Step/Variable", "Values"])

        self.tw.header().resizeSection(0, 150)
        self.tw.header().resizeSection(1, 150)
     

        self.tree_widgets = {}

        tree_keys = ['Step 1', 'Step 2', 'Step 3', 'Step 4']
        
        for key in tree_keys:

            self.tree_widgets.update({key:{}})

            l = QTreeWidgetItem([key, ""])
            self.tw.addTopLevelItem(l)

            for label in ["Num. iterations", "Num. points", "RMSE", "SEUW", "Camera error", "Control scale error", "Check scale error", 
                          "Control point error",  "Check point error", "Level", "Num. proj. <100", "Rev. it. / pts."]:

                if key == "Step 4" and label in ["Level","Rev. it. / pts." ]:
                    continue
                
                
                child = QTreeWidgetItem([label, ""])             
                l.addChild(child)
                self.tree_widgets[key].update({label:child})       

        self.preferences_widget_layout.addWidget(self.tw)
        self.preferences_widget.setLayout(self.preferences_widget_layout)

        layout = QGridLayout()

        layout.addWidget(self.preferences_widget, 0, 0)
        layout.addWidget(self.tabwidget, 0, 1)

        self.setLayout(layout)

        self.dtime = str(datetime.datetime.now()).replace(' ','_').split('.')[0]
        
        print('TIME: ',self.dtime) 

        session_files = [f for f in os.listdir() if f.endswith('.json')]

        self.pname = str(self.doc).split()[1].replace("'",'').replace('>','').split('/')[-1].split('.')[0]
        print(self.pname)

        self.session_name = ''
       
        session_files = [f for f in os.listdir() if f.endswith('.json') and f.startswith(self.pname)]
        if len(session_files) != 0:
            self.readChunkMemoryFromFileDialog()

        else:
            self.newSessionName()
              
  
        self.exec()
        
        
    def setChunkSpecificValues(self):
    
        trans = {'Reconstruction Uncertainty': 0,
                 'Projection Accuracy': 1,
                 'Reprojection Error': 2,
                 'Reprojection Error (RMSE Minimization)': 3,
                 }
    
        cl = self.chunk.label
                       
        for step in self.step_widgets:    
        
            _, _, scale_fac = self.parameters[step]
             
            self.step_widgets[step]['target_percent_slider'].setValue(self.chunk_memory[cl]['tab_settings'][trans[step]]['target_percent'])
            self.step_widgets[step]['target_percent_ledit'].setText(str(self.chunk_memory[cl]['tab_settings'][trans[step]]['target_percent']))
            
            self.step_widgets[step]['target_threshold_slider'].setValue( self.scale_value(self.chunk_memory[cl]['tab_settings'][trans[step]]['target_threshold'], scale_fac, 'up') )
            self.step_widgets[step]['target_threshold_ledit'].setText(str(self.chunk_memory[cl]['tab_settings'][trans[step]]['target_threshold']))

            self.step_widgets[step]['max_iter_slider'].setValue(self.chunk_memory[cl]['tab_settings'][trans[step]]['num_iterations'])
            self.step_widgets[step]['max_iter_ledit'].setText(str(self.chunk_memory[cl]['tab_settings'][trans[step]]['num_iterations']))

            self.step_widgets[step]['tiepoint_accuracy_ledit'].setText(str(self.chunk_memory[cl]['tab_settings'][trans[step]]['tiepoint_accuracy']))
            
            for key in self.camera_check_boxes[step]:
                self.camera_check_boxes[step][key].setChecked(self.chunk_memory[cl]['tab_settings'][trans[step]][key]  )
                
                               
        for tab_index in range(4):
            step = 'Step ' + str(tab_index + 1)

            
            try:        
                N_iter = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Num. iterations']
                self.tree_widgets[step]["Num. iterations"].setText(1, str(N_iter)) 
            except ValueError:
                self.tree_widgets[step]["Num. iterations"].setText(1, '') 
                
            try:
                n_points_begin, n_points_left = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Num. points'].replace('-','').replace('>', '').split()
                self.tree_widgets[step]["Num. points"].setText(1, '{0: <10} ---> {1: <10}'.format(n_points_begin, n_points_left))
            except ValueError:
                self.tree_widgets[step]["Num. points"].setText(1, '')


            try:
                rms_begin, rms_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['RMSE'].replace('-','').replace('>', '').split()
                self.tree_widgets[step]["RMSE"].setText(1, '{0: <10} ---> {1: <10} (pix)'.format(round(float(rms_begin), 5), round(float(rms_final), 5)))
            except ValueError:
                self.tree_widgets[step]["RMSE"].setText(1, '')

            try:    
                seuw_begin, seuw_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['SEUW'].replace('-','').replace('>', '').split()
                self.tree_widgets[step]["SEUW"].setText(1, '{0: <10} ---> {1: <10}'.format(round(float(seuw_begin), 5), round(float(seuw_final), 5)))
            except ValueError:
                self.tree_widgets[step]["SEUW"].setText(1, '')

            try:
                cam_err_begin, cam_err_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Camera error'].replace('-','').replace('>', '').split()     
                self.tree_widgets[step]["Camera error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(float(cam_err_begin), 6), round(float(cam_err_final), 6)))
            except ValueError:
                self.tree_widgets[step]["Camera error"].setText(1, '')
                


            try:
                mark_err_check_begin, mark_err_check_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Check point error'].replace('-','').replace('>', '').split()     
                self.tree_widgets[step]['Check point error'].setText(1, '{0: <10} ---> {1: 10} (m)'.format(round(float(mark_err_check_begin), 6), round(float(mark_err_check_final), 6)))
            except ValueError:
                self.tree_widgets[step]['Check point error'].setText(1, '')


            try:
                mark_err_control_begin, mark_err_control_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Control point error'].replace('-','').replace('>', '').split()     
                self.tree_widgets[step]['Control point error'].setText(1, '{0: <10} ---> {1: 10} (m)'.format(round(float(mark_err_control_begin), 6), round(float(mark_err_control_final), 6)))
            except ValueError:
                self.tree_widgets[step]['Control point error'].setText(1, '') 


            try:     
                scale_err_control_begin, scale_err_control_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]["Control scale error"].replace('-','').replace('>', '').split()   
                self.tree_widgets[step]["Control scale error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(float(scale_err_control_begin), 6), round(float(scale_err_control_final), 6)))
            except ValueError:
                self.tree_widgets[step]["Control scale error"].setText(1, '')
                
            try:     
                scale_err_check_begin, scale_err_check_final, _ = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]["Check scale error"].replace('-','').replace('>', '').split()   
                self.tree_widgets[step]["Check scale error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(float(scale_err_check_begin), 6), round(float(scale_err_check_final), 6)))
            except ValueError:
                self.tree_widgets[step]["Check scale error"].setText(1, '')
                
            try:
                nproj_begin, nproj_final = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]["Num. proj. <100"].replace('-','').replace('>', '').split() 
                self.tree_widgets[step]["Num. proj. <100"].setText(1, '{0: <10} ---> {1: <10}'.format(int(nproj_begin), int(nproj_final)))
                
            except ValueError:
                self.tree_widgets[step]["Num. proj. <100"].setText(1, '')
                print( self.chunk_memory[self.chunk.label]['tree_results'][tab_index]["Num. proj. <100"])


            if step != "Step 4":
                try:
                    threshold_begin, threshold_final = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]["Level"].replace('-','').replace('>', '').split()   
                    self.tree_widgets[step]["Level"].setText(1, '{0: <10} ---> {1: <10}'.format(round(float(threshold_begin), 6), round(float(threshold_final), 6)))
                except ValueError:
                    self.tree_widgets[step]["Level"].setText(1, '')

                try:        
                    rev_pts = self.chunk_memory[self.chunk.label]['tree_results'][tab_index]['Rev. it. / pts.']
                    self.tree_widgets[step]['Rev. it. / pts.'].setText(1, rev_pts) 
                except ValueError:
                    self.tree_widgets[step]['Rev. it. / pts.'].setText(1, '') 
            
    
        
        
    def updateChunkMemory(self, step, kind, key, value):
    
        trans = {'Reconstruction Uncertainty': 0,
                 'Projection Accuracy': 1,
                 'Reprojection Error': 2,
                 'Reprojection Error (RMSE Minimization)': 3,
                 }
         
       
        ix = trans[step]
    
        cl = self.chunk.label
        self.chunk_memory[cl][kind][ix][key] = value
        
        self.writeChunkMemory2File()

    def checkIfChunkInComboBox(self):

        if self.chunk.label not in self.chunk_memory:
            self.addChunk(self.chunk)


    def addChunk(self, chunk):

        self.chunk_dict[chunk.label] = chunk
             
        self.chunk_memory.update({chunk.label:{ 'tab_settings':{}, 'tree_results':{} }})
             
        for tab_index in range(4):
            
            trans = {0:'Reconstruction Uncertainty',
                     1:'Projection Accuracy',
                     2:'Reprojection Error',
                     3:'Reprojection Error (RMSE Minimization)',
                 }
                 
            ix = trans[tab_index]
                 
            tp = self.default_values[ix]['target_percent']
            tt = self.default_values[ix]['target_threshold']
            ni = self.default_values[ix]['max_iter']
            ta = self.default_values[ix]['tiepoint_accuracy']
            
            self.chunk_memory[chunk.label]['tab_settings'].update({tab_index : {'target_percent':tp,
                                                                                                 'target_threshold':tt,
                                                                                                 'num_iterations':ni,
                                                                                                 'tiepoint_accuracy':ta,
                                                                                                 'Fit f': self.camera_fit_dict['Fit f'],
                                                                                                 'Fit k1':self.camera_fit_dict['Fit k1'],
                                                                                                 'Fit k2':self.camera_fit_dict['Fit k2'],
                                                                                                 'Fit k3':self.camera_fit_dict['Fit k3'],
                                                                                                 'Fit k4':self.camera_fit_dict['Fit k4'],
                                                                                                 'Fit cx, cy':self.camera_fit_dict['Fit cx, cy'],
                                                                                                 'Fit p1':self.camera_fit_dict['Fit p1'],
                                                                                                 'Fit p2':self.camera_fit_dict['Fit p2'],
                                                                                                 'Fit b1':self.camera_fit_dict['Fit b1'],
                                                                                                 'Fit b2':self.camera_fit_dict['Fit b2'],
                                                                                                 'Adaptive camera model fitting':self.camera_fit_dict['Adaptive camera model fitting'],
                                                                                                 'Estimate tie point covariance':self.camera_fit_dict['Estimate tie point covariance'],
                                                                                                 'Fit additional corrections':self.camera_fit_dict['Fit additional corrections'],
                                                                                                 },
                                                                        })
                                                                        
    
                                                                        
            self.chunk_memory[chunk.label]['tree_results'].update({tab_index : {"Num. iterations" : '',
                                                                                                "Num. points" : '',
                                                                                                 "RMSE" : '',
                                                                                                 "SEUW" : '',
                                                                                                 "Camera error" : '',
                                                                                                 "Check scale error" : '',
                                                                                                 "Control scale error" : '',
                                                                                                 "Check point error" : '',
                                                                                                 "Control point error" : '',
                                                                                                 "Num. proj. <100": '',
                                                                                                 },
                                                                        })


            if tab_index != 4:
               self.chunk_memory[chunk.label]['tree_results'][tab_index].update({ "Level" : '', "Rev. it. / pts.": ''})


       

            
    def updateChunkMemoryTree(self):
    
    
        
        for tab_index in range(4):
            key = 'Step ' + str(tab_index + 1)


                     
            self.chunk_memory[self.chunk.label]['tree_results'].update({tab_index : {"Num. iterations" : self.tree_widgets[key]["Num. iterations"].text(1),
                                                                                "Num. points" : self.tree_widgets[key]["Num. points"].text(1),
                                                                                "RMSE" : self.tree_widgets[key]["RMSE"].text(1),
                                                                                "SEUW" : self.tree_widgets[key]["SEUW"].text(1),
                                                                                "Camera error" : self.tree_widgets[key]["Camera error"].text(1),
                                                                                "Control scale error" : self.tree_widgets[key]["Control scale error"].text(1),
                                                                                "Check scale error" : self.tree_widgets[key]["Check scale error"].text(1),
                                                                                "Control point error" : self.tree_widgets[key]["Control point error"].text(1),
                                                                                "Check point error" : self.tree_widgets[key]["Check point error"].text(1),
                                                                                "Num. proj. <100" : self.tree_widgets[key]["Num. proj. <100"].text(1),
                                                                                
                                                                                                 },
                                                                        })




            if key != "Step 4":
                self.chunk_memory[self.chunk.label]['tree_results'][tab_index].update({"Level" : self.tree_widgets[key]["Level"].text(1),
                                                                                       "Rev. it. / pts." : self.tree_widgets[key]["Rev. it. / pts."].text(1),
                                                                                       })
                                                                        

            

                  
        self.writeChunkMemory2File()

    def setDefaultValues(self, step):

        
       
        _, _, scale_fac = self.parameters[step]

        self.step_widgets[step]['target_percent_ledit'].setText( str(self.default_values[step]['target_percent']) )
        self.step_widgets[step]['target_percent_slider'].setValue( self.default_values[step]['target_percent'] )

        self.step_widgets[step]['target_threshold_ledit'].setText( str(self.default_values[step]['target_threshold']) )
        self.step_widgets[step]['target_threshold_slider'].setValue( self.scale_value(self.default_values[step]['target_threshold'], scale_fac, 'up' ))

        self.step_widgets[step]['max_iter_ledit'].setText( str(self.default_values[step]['max_iter']) )
        self.step_widgets[step]['max_iter_slider'].setValue( self.default_values[step]['max_iter'] )

            
        for label in self.camera_check_boxes[step]:

            self.camera_check_boxes[step][label].setChecked( self.camera_fit_dict[label])  



    def setSliderValue(self, slider, val):
        slider.setValue(val)

    def sliderValueChanged(self, value, ledit):
        ledit.setText(str( value ))

    def scale_value(self, value, factor, direction):
        if direction == 'down':
            return round(value*factor, 3)
        elif direction == 'up':
            return round(value/factor, 3)


    def switchRunButtonsEnabledDisabled(self):


        for step in self.step_widgets:
            if self.auto_run_group_box.isChecked():
                self.step_widgets[step]['run_button'].setEnabled(False)
            else:
                self.step_widgets[step]['run_button'].setEnabled(True)


    def makeStepWindow(self, step, target_percent, target_threshold, max_iter): 

        #specific parameters for the respective window of each step
        # 1 + 2: min. and max. values of the threshold slider
        # 3    : scaling factor of threshold slider (enables usage of float numbers)  

        
        tmin, tmax, scale_fac = self.parameters[step]
                        
        camera_fit_dict = self.camera_fit_dict


        self.camera_check_boxes.update({step:{}})

        camera_widget = QWidget()
        camera_widget_layout = QVBoxLayout()
        

        camera_group_box_1 = QGroupBox('General')
        camera_group_box_1.setStyleSheet("QGroupBox { border: 1px solid lightgrey;}")

            
        for key in camera_fit_dict:
            cb = QCheckBox(key)
            cb.setChecked(camera_fit_dict[key])
            cb.setStyleSheet("border: none;")
                                           
            self.camera_check_boxes[step].update({key:cb})
                                           
         
      
        self.camera_check_boxes[step]['Fit f'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit f', self.camera_check_boxes[step]['Fit f'].isChecked() ))
                                                                
        self.camera_check_boxes[step]['Fit k1'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit k1', self.camera_check_boxes[step]['Fit k1'].isChecked() ))
                                                                
        self.camera_check_boxes[step]['Fit k2'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit k2', self.camera_check_boxes[step]['Fit k2'].isChecked() ))

        self.camera_check_boxes[step]['Fit k3'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit k3', self.camera_check_boxes[step]['Fit k3'].isChecked() ))

        self.camera_check_boxes[step]['Fit k4'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit k4', self.camera_check_boxes[step]['Fit k4'].isChecked() ))

        self.camera_check_boxes[step]['Fit cx, cy'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit cx, cy', self.camera_check_boxes[step]['Fit cx, cy'].isChecked() ))

        self.camera_check_boxes[step]['Fit p1'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit p1', self.camera_check_boxes[step]['Fit p1'].isChecked() ))

        self.camera_check_boxes[step]['Fit p2'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit p2', self.camera_check_boxes[step]['Fit p2'].isChecked() ))

        self.camera_check_boxes[step]['Fit b1'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit b1', self.camera_check_boxes[step]['Fit b1'].isChecked() ))

        self.camera_check_boxes[step]['Fit b2'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit b2', self.camera_check_boxes[step]['Fit b2'].isChecked() ))                                                                
                                        
        self.camera_check_boxes[step]['Fit b2'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit b2', self.camera_check_boxes[step]['Fit b2'].isChecked() ))   
                                                                
        self.camera_check_boxes[step]['Adaptive camera model fitting'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Adaptive camera model fitting', self.camera_check_boxes[step]['Adaptive camera model fitting'].isChecked() ))  
                                                                
        self.camera_check_boxes[step]['Estimate tie point covariance'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Estimate tie point covariance', self.camera_check_boxes[step]['Estimate tie point covariance'].isChecked() ))                                               
                                                                
        self.camera_check_boxes[step]['Fit additional corrections'].stateChanged.connect(lambda: self.updateChunkMemory(step, 'tab_settings', 
                                                                'Fit additional corrections', self.camera_check_boxes[step]['Fit additional corrections'].isChecked() ))                                  
                                                                


        camera_label = QLabel('Optimize Camera Alignment')
        camera_label.setStyleSheet("QLabel{font-size: 9pt;}")

   

        camera_group_box_1_layout = QGridLayout()
        
        labels = list(camera_fit_dict.keys())

        for i, label in enumerate(labels[:5], start=1):
             camera_group_box_1_layout.addWidget(self.camera_check_boxes[step][label], i, 0)

        for i, label in enumerate(labels[5:10], start=1):
             camera_group_box_1_layout.addWidget(self.camera_check_boxes[step][label], i, 1)

        camera_group_box_1.setLayout(camera_group_box_1_layout)
   

        camera_group_box_2 = QGroupBox('Advanced')
        camera_group_box_2.setStyleSheet("QGroupBox { border: 1px solid lightgrey;}")
        

        camera_group_box_2_layout = QVBoxLayout()

        for i, label in enumerate(labels[10:], start=6):
            camera_group_box_2_layout.addWidget(self.camera_check_boxes[step][label])

        camera_group_box_2.setLayout(camera_group_box_2_layout)

 
        camera_widget_layout.addWidget(camera_label)
        camera_widget_layout.addWidget(camera_group_box_1)
        camera_widget_layout.addWidget(camera_group_box_2)
       
        camera_widget.setLayout(camera_widget_layout)



        self.step_widgets.update( {step:{}} )



        target_percent_label = QLabel('Target percent:     ')
        target_percent_label.setStyleSheet("border: none;") 


        target_percent_ledit = QLineEdit(str(target_percent))
        target_percent_ledit.textChanged.connect(lambda: self.updateChunkMemory(step, 
                                                                                'tab_settings', 
                                                                                'target_percent', 
                                                                                float(target_percent_ledit.text()),
                                                                                ),
                                                )



        self.step_widgets[step].update({'target_percent_ledit':target_percent_ledit})
    
        if step != 'Reprojection Error (RMSE Minimization)':
            target_threshold_label = QLabel('Target threshold:  ')
        else:
            target_threshold_label = QLabel('Target RMSE:           ')


        target_threshold_label.setStyleSheet("border: none;")

        target_threshold_ledit = QLineEdit(str(target_threshold))
        target_threshold_ledit.textChanged.connect(lambda: self.updateChunkMemory(step, 
                                                                                'tab_settings', 
                                                                                'target_threshold', 
                                                                                float(target_threshold_ledit.text()),
                                                                                ),
                                                )

        self.step_widgets[step].update({'target_threshold_ledit':target_threshold_ledit})


        max_iter_label = QLabel('Num. of iterations:')
        max_iter_label.setStyleSheet("border: none;")
    
        max_iter_ledit = QLineEdit(str(max_iter))
        max_iter_ledit.textChanged.connect(lambda: self.updateChunkMemory(step, 
                                                                          'tab_settings', 
                                                                          'num_iterations', 
                                                                          float( max_iter_ledit.text()),
                                                                          ),
                                           )
        
        self.step_widgets[step].update({'max_iter_ledit':max_iter_ledit})

        target_percent_slider = QSlider(Qt.Horizontal)

        target_percent_slider.setStyleSheet("border: none;")

        

        target_percent_slider.setMinimum(0)
        target_percent_slider.setMaximum(100)

        target_percent_slider.setValue( float(self.step_widgets[step]['target_percent_ledit'].text()) )

        target_percent_slider.sliderMoved.connect(lambda: self.sliderValueChanged( float(target_percent_slider.value()), 
                                                          self.step_widgets[step]['target_percent_ledit']),
                                                  )


        self.step_widgets[step].update( {'target_percent_slider':target_percent_slider} )


        self.step_widgets[step]['target_percent_ledit'].editingFinished.connect(lambda: self.setSliderValue(self.step_widgets[step]['target_percent_slider'] , 
                                                                                                             float(self.step_widgets[step]['target_percent_ledit'].text()),
                                                                                                            ),
                                                                                )
        


        target_threshold_slider = QSlider(Qt.Horizontal)

        target_threshold_slider.setStyleSheet("border: none;")

        
        
        target_threshold_slider.setMinimum(tmin)
        target_threshold_slider.setMaximum(tmax)

        target_threshold_slider.setValue( float(self.step_widgets[step]['target_threshold_ledit'].text()) / scale_fac )

        target_threshold_slider.sliderMoved.connect(lambda: self.sliderValueChanged(  float(self.scale_value(target_threshold_slider.value(), scale_fac, 'down')), 
                                                                                      self.step_widgets[step]['target_threshold_ledit']),
                                                    )


        self.step_widgets[step].update( {'target_threshold_slider':target_threshold_slider} )


        self.step_widgets[step]['target_threshold_ledit'].editingFinished.connect(lambda: self.setSliderValue( self.step_widgets[step]['target_threshold_slider'], 
                                                                                                               self.scale_value(float(self.step_widgets[step]['target_threshold_ledit'].text()), scale_fac, 'up'),
                                                                                                              ),
                                                                                  )


        max_iter_slider = QSlider(Qt.Horizontal)

        max_iter_slider.setStyleSheet("border: none;")
        max_iter_slider.setMinimum(0)
        max_iter_slider.setMaximum(200)
        max_iter_slider.setValue( float(self.step_widgets[step]['max_iter_ledit'].text()) )

        max_iter_slider.sliderMoved.connect(lambda: self.sliderValueChanged( int(max_iter_slider.value()), 
                                                                             self.step_widgets[step]['max_iter_ledit']),
                                            )


        self.step_widgets[step].update( {'max_iter_slider':max_iter_slider} )
        self.step_widgets[step]['max_iter_ledit'].editingFinished.connect(lambda: self.setSliderValue( self.step_widgets[step]['max_iter_slider'] , 
                                                                                                       float(self.step_widgets[step]['max_iter_ledit'].text()),
                                                                                                      ),
                                                                          )

        button = QPushButton('Run', default=False, autoDefault=False)
        button.setEnabled(False)

        
        button.setFixedSize(QtCore.QSize(5, 20))


        button.clicked.connect(lambda: self.runButtonClicked(step))

                                                           
        button.clicked.connect(self.updateChunkMemoryTree)

        default_button = QPushButton('Reset', default=False, autoDefault=False)
        default_button.setFixedSize(QtCore.QSize(5, 20))


        default_button.clicked.connect(lambda: self.setDefaultValues(step) )

        self.step_widgets[step].update( {'run_button':button} )

    
        step_widget = QWidget() 
        step_widget.setStyleSheet("border: none;")
 
        step_widget_layout = QVBoxLayout()
        step_widget_layout.setSpacing(25)
        step_widget_layout.setMargin(15)

        target_percent_layout = QGridLayout()
        target_percent_layout.setSpacing(10)

        target_percent_layout.addWidget(target_percent_label, 0, 0) 
        target_percent_layout.addWidget(self.step_widgets[step]['target_percent_ledit'], 0, 1) 
        target_percent_layout.addWidget(self.step_widgets[step]['target_percent_slider'], 1, 0, 1, 2)
       
        step_widget_layout.addLayout(target_percent_layout)

         
        target_threshold_layout = QGridLayout()
        target_threshold_layout.setSpacing(10)

        target_threshold_layout.addWidget(target_threshold_label, 0, 0) 
        target_threshold_layout.addWidget(self.step_widgets[step]['target_threshold_ledit'], 0, 1) 
        target_threshold_layout.addWidget(self.step_widgets[step]['target_threshold_slider'], 1, 0, 1, 2) 

        step_widget_layout.addLayout(target_threshold_layout)


        max_iter_layout = QGridLayout()
        max_iter_layout.setSpacing(10)

        max_iter_layout.addWidget(max_iter_label, 0, 0) 
        max_iter_layout.addWidget(self.step_widgets[step]['max_iter_ledit'], 0, 1) 
        max_iter_layout.addWidget(self.step_widgets[step]['max_iter_slider'], 1, 0, 1, 2) 

        step_widget_layout.addLayout(max_iter_layout)

        emptyline = QLabel(' ')
        emptyline.setStyleSheet("border: none;")

        step_widget_layout.addWidget(emptyline) 
 
     
        headline = QLabel(step)
        headline.setStyleSheet("QLabel{font-size: 9pt;}")
       

        crd_acc_group_box =  QGroupBox('Image Coordinates Accuracy')
        crd_acc_group_box_layout = QHBoxLayout()

        crd_acc_label = QLabel('Tie point accuracy (pix):')
        crd_acc_ledit = QLineEdit(str(self.chunk.tiepoint_accuracy))
        crd_acc_ledit.textChanged.connect(lambda: self.updateChunkMemory(step, 
                                                                         'tab_settings', 
                                                                         'tiepoint_accuracy', 
                                                                          float( crd_acc_ledit.text()),
                                                                          ),
                                           )
        

    
        self.tiepoint_ledits.update({step:crd_acc_ledit})
        self.step_widgets[step].update( {'tiepoint_accuracy_ledit':crd_acc_ledit} )


        crd_acc_group_box_layout.addWidget(crd_acc_label)
        crd_acc_group_box_layout.addWidget(crd_acc_ledit)

        crd_acc_group_box.setLayout(crd_acc_group_box_layout)
        crd_acc_group_box.setStyleSheet("QGroupBox { border: 1px solid lightgrey;}")
        crd_acc_group_box.setCheckable(True)
        crd_acc_group_box.setChecked(False)

       
       
        main_widget = QWidget()

        main_layout = QHBoxLayout()
        
        left_column_layout = QVBoxLayout()
        right_column_layout = QVBoxLayout()

        right_column_layout.addWidget(camera_widget)
        right_column_layout.addWidget(crd_acc_group_box)
       

        left_column_layout.addWidget(headline)
        left_column_layout.addLayout(step_widget_layout)
        

        left_column_layout.addStretch()
        right_column_layout.addStretch()


        main_layout.addLayout(left_column_layout)
        main_layout.addLayout(right_column_layout)
        

        button_layout = QGridLayout()
        button_layout.setAlignment(Qt.AlignCenter)
   
        button_layout.addWidget(default_button, 0, 0)
        button_layout.addWidget(button, 0, 1)
        
        left_column_layout.addLayout(button_layout)

        main_widget.setLayout(main_layout)
      
        return main_widget
        
        
        
    def writeChunkMemory2File(self):

       if self.session_name == '':
           self.newSessionName()

       fname = self.session_name + '.json'

       current_doc = Metashape.app.document.path
       current_dir = os.path.dirname(current_doc)
       
       
       with open(current_dir + "/" + fname, "w") as f:
           json.dump(self.chunk_memory, f, indent=4)

           
    def readChunkMemoryFromFile(self):

        fname = self.session_name + '.json'
        with open(fname, "r") as f:
            mem = json.load(f)
            
        # json turns every key into strings
        # here the key corresponding to the tab indices are changed to integers        
        new_mem = deepcopy(mem)
        for ch in mem:
            for kind in mem[ch]:
                for key in mem[ch][kind].keys():
                    new_mem[ch][kind][int(key)] = mem[ch][kind][key]
                    del new_mem[ch][kind][key]

        self.chunk_memory = new_mem

            
        self.setChunkSpecificValues()

    def convertFromComboBox2SessionName(self, text):
        d, t = text.replace('Date:', '').replace('Time:','').split()
        
        d = d.replace('/', '-')
        t = t.replace(':', '-')

        out = self.pname + '_' + d + '_' + t 
        
        return out


    def setSessionName(self, name):
        
        self.session_name = name


    def newSessionName(self):

        dt = str(datetime.datetime.now()).replace(' ','_').split('.')[0].replace(':', '-')

        self.session_name = self.pname + '_' + dt 


    
    def readChunkMemoryFromFileDialog(self):

        session_files = [f[:-5] for f in os.listdir() if f.endswith('.json') and f.split('-')[0][:-5] == self.pname ]

        self.session_combo_box = QComboBox()

        snames = {}       
        for f in sorted(session_files, reverse=True):
        
            st = f.replace(self.pname, "")


            if st.split('_')[0] == '':
                _, date, time = st.split('_')
            else:
                date, time = st.split('_')


            date = date.replace('-', '/')
            time = time.replace('-', ':')
            
            self.session_combo_box.addItem('Date: ' + date + '     Time: ' + time)

  
    
        dlg = QDialog(self)
        dlg.setWindowTitle("Sparse Cloud Cleaning")
            
        question = QLabel('Restore previous session ?')
        yes_button = QPushButton('Yes')
        no_button = QPushButton('No')

        
        
        yes_button.clicked.connect(lambda: self.setSessionName(self.convertFromComboBox2SessionName(self.session_combo_box.currentText())))
        yes_button.clicked.connect(self.readChunkMemoryFromFile)


        yes_button.clicked.connect(dlg.close)

        no_button.clicked.connect(self.newSessionName)
        no_button.clicked.connect(self.writeChunkMemory2File)
        no_button.clicked.connect(dlg.close)
            
        layout = QGridLayout()
            
        layout.addWidget(question, 0,0, 1, 2)
        layout.addWidget(self.session_combo_box, 1,0, 1, 2)

        layout.addWidget(yes_button, 2,0)
        layout.addWidget(no_button, 2,1)

        dlg.setLayout(layout)
            
        dlg.exec()



    def setTiePointAccuracy(self, step):

        self.chunk.tiepoint_accuracy = float(self.tiepoint_ledits[step].text() )   


    def makeSummaryWindow(self):

        widget = QWidget() 
        widget.setStyleSheet("font-size: 9pt; border: none;")
 
        widget_layout = QGridLayout()
         
        l = QLabel('Summary')
        widget_layout.addWidget(l, 0, 0)

        widget.setLayout(widget_layout)

        return widget


    def calcRMS(self):

        point_cloud = self.chunk.tie_points
        points = point_cloud.points
        npoints = len(points)
        projections = self.chunk.tie_points.projections
        err_sum = 0
        num = 0
        maxe = 0

        point_ids = [-1] * len(point_cloud.tracks)
        point_errors = dict()
        for point_id in range(0, npoints):
            point_ids[points[point_id].track_id] = point_id

        for camera in self.chunk.cameras:
            if not camera.transform:
                continue

            if not camera.enabled:
                continue

            for proj in projections[camera]:
                track_id = proj.track_id
                point_id = point_ids[track_id]
                if point_id < 0:
                    continue

                point = points[point_id]
                if not point.valid:
                    continue

                error = camera.error(point.coord, proj.coord).norm() ** 2
                err_sum += error
                num += 1

                if point_id not in point_errors.keys():
                    point_errors[point_id] = [error]
                else:
                    point_errors[point_id].append(error)

                if error > maxe: maxe = error
				
        sigma = math.sqrt(err_sum / num)

        return sigma

    def askCorrectChunkWindow(self):

        def yesClicked():
            self.rval =  True
        
        def noClicked():
            self.rval = False
            

        dlg = QDialog(self)
        dlg.setWindowTitle("Sparse Cloud Cleaning")
            
        question = QLabel('Chunk selection correct?')
        yes_button = QPushButton('Yes')
        no_button = QPushButton('No')
        
        yes_button.clicked.connect(yesClicked)
        yes_button.clicked.connect(dlg.close)
        no_button.clicked.connect(noClicked)
        no_button.clicked.connect(dlg.close)
            
        layout = QGridLayout()
            
        layout.addWidget(question, 0,0, 1, 2)
        layout.addWidget(yes_button, 1,0)
        layout.addWidget(no_button, 1,1)

        dlg.setLayout(layout)

        dlg.exec()
        

    def runAllButtonClicked(self):

        self.rval = None
        self.askCorrectChunkWindow()

        if not self.rval:
            return
        
        self.runAllSteps()

    def runButtonClicked(self, step):

        self.rval = None
        self.askCorrectChunkWindow()

        if not self.rval:
            return
        
        self.executeStep(step = step,
                             target_percent = float(self.step_widgets[step]['target_percent_ledit'].text()), 
                             target_threshold = float(self.step_widgets[step]['target_threshold_ledit'].text()), 
                             max_iter = float(self.step_widgets[step]['max_iter_ledit'].text()),
                             )


    def executeStep(self, step, target_percent, target_threshold, max_iter):

     
        
        # variable to indicate, wether goal of the analysis is reached
        fin = False
        threshold = None

        npoint_list = []

        initial_tiepoint_accuracy = self.chunk.tiepoint_accuracy 

        self.chunk.tiepoint_accuracy = float(self.tiepoint_ledits[step].text())

        criteria = {'Reconstruction Uncertainty' : Metashape.TiePoints.Filter.ReconstructionUncertainty,
                    'Projection Accuracy' : Metashape.TiePoints.Filter.ProjectionAccuracy,
                    'Reprojection Error' : Metashape.TiePoints.Filter.ReprojectionError,
                    'Reprojection Error (RMSE Minimization)' : Metashape.TiePoints.Filter.ReprojectionError,
                    }

        criterion = criteria[step]



        fit_f = self.camera_check_boxes[step]['Fit f'].isChecked()
        fit_cx= self.camera_check_boxes[step]['Fit cx, cy'].isChecked() 
        fit_cy= self.camera_check_boxes[step]['Fit cx, cy'].isChecked()
        fit_b1= self.camera_check_boxes[step]['Fit b1'].isChecked() 
        fit_b2= self.camera_check_boxes[step]['Fit b2'].isChecked() 
        fit_k1= self.camera_check_boxes[step]['Fit k1'].isChecked()
        fit_k2= self.camera_check_boxes[step]['Fit k2'].isChecked() 
        fit_k3= self.camera_check_boxes[step]['Fit k3'].isChecked() 
        fit_k4= self.camera_check_boxes[step]['Fit k4'].isChecked()
        fit_p1= self.camera_check_boxes[step]['Fit p1'].isChecked()
        fit_p2= self.camera_check_boxes[step]['Fit p2'].isChecked() 
        fit_corrections= self.camera_check_boxes[step]['Fit additional corrections'].isChecked()
        adaptive_fitting= self.camera_check_boxes[step]['Adaptive camera model fitting'].isChecked() 
        tiepoint_covariance= self.camera_check_boxes[step]['Estimate tie point covariance'].isChecked()

        tf = {True:'x', False:' '}

        message = '''\nAnalyse >{}< with following values:
                    
         Target percent:   {}
         Target threshold: {}

         Optimize Camera Alignment

         [{}] Fit f     [{}] Fit cx, cy
         [{}] Fit k1    [{}] Fit p1
         [{}] Fit k2    [{}] Fit p2
         [{}] Fit k3    [{}] Fit b1
         [{}] Fit k4    [{}] Fit b2

         [{}] Adaptive camera model fitting
         [{}] Estimate tie point covariance
         [{}] Fit additional corrections    

         Tie point accuracy (pix): {}              

         '''.format(step, target_percent, target_threshold, tf[fit_f], tf[fit_cx], tf[fit_k1], 
                    tf[fit_p1], tf[fit_k2], tf[fit_p2], tf[fit_k3], tf[fit_b1], tf[fit_k4], tf[fit_b2], 
                    tf[adaptive_fitting], tf[tiepoint_covariance], tf[fit_corrections], self.chunk.tiepoint_accuracy )
                     
                     
        print(message)

        for it in range(int(max_iter)):

            points = self.chunk.tie_points.points

            f = Metashape.TiePoints.Filter()
            f.init(self.chunk, criterion = criterion) 
            list_values = f.values
            list_values_valid = list()
        
            for i in range(len(list_values)):
       
                if points[i].valid:
                    list_values_valid.append(list_values[i])

            list_values_valid.sort()

            if it == 0:
                n_points_begin = len(list_values_valid)
                rms_begin = self.calcRMS()
                seuw_begin = float(self.chunk.meta['OptimizeCameras/sigma0'])
                cam_err_begin = self.calcTotalCameraError()
                scale_err_check_begin = self.calcScaleBarErrorCheck()
                scale_err_control_begin = self.calcScaleBarErrorControl()
                nproj_begin = self.getNumProjectionsLowerThan()
                mark_err_control_begin = self.calcMarkerErrorControlPoint()
                mark_err_check_begin = self.calcMarkerErrorCheckPoint()
                
                threshold_begin = max(list_values_valid)

                # number of points above threshold at the beginning
                n_0 = len([val for val in list_values_valid if val > target_threshold])


        
            xx = len(list_values_valid)

            mfac = 100
            if step != 'Reprojection Error (RMSE Minimization)':
                
                for n in reversed(range( (100*mfac - (int(target_percent)*mfac)  ) , 100*mfac, 1)):

                    n = n / mfac
                    target = int(len(list_values_valid) * (n / 100) )

                
                    threshold = list_values_valid[target]
                
              
                    if threshold < target_threshold:

                        try:
                            target = int(len(list_values_valid) * (n+(1/mfac)) / 100)
                            threshold = list_values_valid[target]
                            print('Iteration: ', it + 1, '   Filter level before camera optimization: ', threshold)
                            fin = True
                            break

                        except IndexError:
                            threshold = None
                            fin = True

                    if n%mfac == 0: 
                        print('Iteration: ', it + 1, '   Filter level before camera optimization: ', threshold)


            else:

                rms = self.calcRMS()
 
                if rms > target_threshold:

                    target = int(len(list_values_valid) * ((100-target_percent) / 100) )
                    threshold = list_values_valid[target]

                     

            if threshold:

                f.selectPoints(threshold) 
                f.removePoints(threshold) 

                self.chunk.optimizeCameras(fit_f = self.camera_check_boxes[step]['Fit f'].isChecked(),
                                           fit_cx= self.camera_check_boxes[step]['Fit cx, cy'].isChecked(), 
                                           fit_cy= self.camera_check_boxes[step]['Fit cx, cy'].isChecked(),
                                           fit_b1= self.camera_check_boxes[step]['Fit b1'].isChecked(), 
                                           fit_b2= self.camera_check_boxes[step]['Fit b2'].isChecked(), 
                                           fit_k1= self.camera_check_boxes[step]['Fit k1'].isChecked(),
                                           fit_k2= self.camera_check_boxes[step]['Fit k2'].isChecked(), 
                                           fit_k3= self.camera_check_boxes[step]['Fit k3'].isChecked(), 
                                           fit_k4= self.camera_check_boxes[step]['Fit k4'].isChecked(),
                                           fit_p1= self.camera_check_boxes[step]['Fit p1'].isChecked(),
                                           fit_p2= self.camera_check_boxes[step]['Fit p2'].isChecked(), 
                                           fit_corrections= self.camera_check_boxes[step]['Fit additional corrections'].isChecked(),
                                           adaptive_fitting= self.camera_check_boxes[step]['Adaptive camera model fitting'].isChecked(), 
                                           tiepoint_covariance= self.camera_check_boxes[step]['Estimate tie point covariance'].isChecked())

                if fin == True:

                    f = Metashape.TiePoints.Filter()
                    f.init(self.chunk, criterion = criterion) 

                    if max(f.values) > target_threshold:

                        print('Approached filter level of current iteration: ', max(f.values))
                        fin = False


                

                #check if max. uncertainty/error increased after final camera optimization
                #if more than 10 points can be removed from the point list, the process starts anew (variable fin is set to False)
 

                list_values = f.values
                list_values_valid = list()
        
                for i in range(len(list_values)):       
                    if points[i].valid:
                        list_values_valid.append(list_values[i])

                list_values_valid.sort()
 
                if step != 'Reprojection Error (RMSE Minimization)':
                    npoints = len([val for val in list_values_valid if val > target_threshold])
                    npoint_list.append(npoints)

                    print('Number of points above target threshold: ', npoints)

                    if npoints > 10:
                        fin = False
                    else:
                        fin = True



            if step == 'Reprojection Error (RMSE Minimization)':

                f = Metashape.TiePoints.Filter()
                f.init(self.chunk, criterion = criterion) 
 
                rms = self.calcRMS()     
              
                print('Iteration: ', it + 1, '   RMSE: ', rms)
            
                            
                if rms <= target_threshold:
                     fin = True
                  
            if fin: 
                n_points_left = len([p for p in self.chunk.tie_points.points if p.valid])
                self.rms = self.calcRMS()

                threshold_final = max(f.values)#
                
                differences = [ npoint_list[i] - npoint_list[i-1] for i in range(1, len(npoint_list) )]
                n_reverse = len([ d for d in differences if d >= 0 ])

                sum_positive_diff = sum([ d for d in differences if d >= 0 ])

                rev_pts = str(n_reverse) + ' / ' + str(sum_positive_diff)

                         
                print("\nFinished {} in {} iterations".format(step, it+1))
                if step !=  'Reprojection Error (RMSE Minimization)':
                    print('Change in numbers of points above the threshold for each iteration: ', differences)
                    print('Number of reversals (iterations with >= 0 points as listed above): ', n_reverse)
                    print('Cummulative number of reversal points: ', sum_positive_diff)                    
                    print("Approached filter level: {}".format(threshold_final))
                else:
                    print("Final RMSE: {}".format(self.rms))

                print("Remaining tie points: {} out of {} ({} %)".format(n_points_left, n_points_begin, round((n_points_left/n_points_begin)*100 )))

                break


        # check if max. iteration is reached before target threshold is reached
        # if so, define the missing variables needed to stop the routine 
        
        if it == (max_iter-1) and fin == False:
            n_points_left = len([p for p in self.chunk.tie_points.points if p.valid])

            f = Metashape.TiePoints.Filter()
            f.init(self.chunk, criterion = criterion)

            threshold_final = max(f.values)
            

            differences = [ npoint_list[i] - npoint_list[i-1] for i in range(1, len(npoint_list) )]
            n_reverse = len([ d for d in differences if d >= 0 ])

            sum_positive_diff = sum([ d for d in differences if d >= 0 ])

            rev_pts = str(n_reverse) + ' / ' + str(sum_positive_diff)
                   

            self.rms = self.calcRMS()
            print('Insuffiecient number of iterations to approach target threshold.\n')

            print("\nFinished {} in {} iterations".format(step, it+1))
            if step !=  'Reprojection Error (RMSE Minimization)':
                print("Approached filter threshold: {}".format(threshold_final))
            else:
                print("Final RMSE: {}".format(self.rms))

            print("Remaing tie points: {} out of {} ({} %)".format(n_points_left, n_points_begin, round((n_points_left/n_points_begin)*100 )))

             
        # updating entries of the tree widget
        self.updateTreeEntries( step, 
                               (it+1), 
                                n_points_begin, n_points_left, 
                                rms_begin, self.rms, 
                                seuw_begin, float(self.chunk.meta['OptimizeCameras/sigma0']), 
                                cam_err_begin, self.calcTotalCameraError(),
                                nproj_begin, self.getNumProjectionsLowerThan(),
                                mark_err_control_begin, self.calcMarkerErrorControlPoint(),
                                mark_err_check_begin, self.calcMarkerErrorCheckPoint(),
                                scale_err_control_begin, self.calcScaleBarErrorControl(),
                                scale_err_check_begin, self.calcScaleBarErrorCheck(),
                                threshold_begin, threshold_final,
                                rev_pts,
                                )
 
     


    def updateTreeEntries(self, step, N_iter,
                                n_points_begin, n_points_left,
                                rms_begin, rms_final,
                                seuw_begin, seuw_final,
                                cam_err_begin, cam_err_final,
                                nproj_begin, nproj_final,
                                mark_err_control_begin, mark_err_control_final,
                                mark_err_check_begin, mark_err_check_final,
                                scale_err_control_begin, scale_err_control_final,
                                scale_err_check_begin, scale_err_check_final,
                                threshold_begin, threshold_final,
                                rev_pts,
                          ):
 
          step_translator = {'Reconstruction Uncertainty':'Step 1' ,
                             'Projection Accuracy':'Step 2',
                             'Reprojection Error': 'Step 3', 
                             'Reprojection Error (RMSE Minimization)': 'Step 4',
                             }
          

          if step[:4] != 'Step':
              key = step_translator[step]
          else:
              key = step


          self.tree_widgets[key]["Num. iterations"].setText(1, str(N_iter)) 
          self.tree_widgets[key]["Num. points"].setText(1, '{0: <10} ---> {1: <10}'.format(n_points_begin, n_points_left))

          self.tree_widgets[key]["RMSE"].setText(1, '{0: <10} ---> {1: <10} (pix)'.format(round(rms_begin, 5), round(rms_final, 5)))
          self.tree_widgets[key]["SEUW"].setText(1, '{0: <10} ---> {1: <10}.'.format(round(seuw_begin, 5), round(seuw_final, 5)))

          if cam_err_begin and cam_err_final:
              self.tree_widgets[key]["Camera error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(cam_err_begin, 5), round(cam_err_final, 5)))
          else:
              self.tree_widgets[key]["Camera error"].setText(1, '')
        
               
          if mark_err_control_begin and mark_err_control_final:
               self.tree_widgets[key]["Control point error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(mark_err_control_begin, 6), round(mark_err_control_final, 6)))
          else:
               self.tree_widgets[key]["Control point error"].setText(1, '')
               
          if mark_err_check_begin and mark_err_check_final:
               self.tree_widgets[key]["Check point error"].setText(1, '{0: <10} ---> {1: <10} (m)'.format(round(mark_err_check_begin, 6), round(mark_err_check_final, 6)))
          else:
               self.tree_widgets[key]["Check point error"].setText(1, '')
               
               
          if scale_err_check_begin and scale_err_check_final:
               self.tree_widgets[key]["Check scale error"].setText(1, '{0:f} ---> {1:f} (m)'.format(round(scale_err_check_begin, 6), round(scale_err_check_final, 6)))
          else:
               self.tree_widgets[key]["Check scale error"].setText(1, '')    

          if scale_err_control_begin and scale_err_control_final:
               self.tree_widgets[key]["Control scale error"].setText(1, '{0:f} ---> {1:f} (m)'.format(round(scale_err_control_begin, 6), round(scale_err_control_final, 6)))
          else:
               self.tree_widgets[key]["Control scale error"].setText(1, '')      

          if key != "Step 4":
          
              if threshold_begin and threshold_final:
                  self.tree_widgets[key]["Level"].setText(1, '{0:f} ---> {1:f}'.format(round(threshold_begin, 6), round(threshold_final, 6)))
              else:
                  self.tree_widgets[key]["Level"].setText(1, '')

              if rev_pts:
                  self.tree_widgets[key]["Rev. it. / pts."].setText(1, '{}'.format(rev_pts))
              else:
                  self.tree_widgets[key]["Rev. it. / pts."].setText(1, '')
               
               
          self.tree_widgets[key]["Num. proj. <100"].setText(1, '{0: <10} ---> {1: <10}'.format(round(nproj_begin, 6), round(nproj_final, 6)))

         
    
    def getNumProjectionsLowerThan(self):
        '''Getting the number of cameras with less than 100 projections
           modified after https://www.agisoft.com/forum/index.php?topic=12758.0'''
    
        chunk = self.chunk

        point_cloud = chunk.tie_points
        projections = point_cloud.projections
        points = point_cloud.points
        npoints = len(points)
        tracks = point_cloud.tracks
        point_ids = [-1] * len(point_cloud.tracks)
        
        sums = 0

        for point_id in range(0, npoints):
            point_ids[points[point_id].track_id] = point_id


        cameras_with_proj = 0
        for camera in chunk.cameras: 
            nprojections = 0
            if camera.type == Metashape.Camera.Type.Keyframe:
                continue # skipping Keyframes
            if not camera.transform:
                continue
            
            cameras_with_proj+=1  
            for proj in projections[camera]:
                track_id = proj.track_id
                point_id = point_ids[track_id]
                if point_id < 0:
                    continue
                if not points[point_id].valid:
                    continue
                    
                nprojections += 1
            
            if nprojections < 100:
                sums+=1

        # to also consider cameras without projections:
        cameras_without_proj = (len(chunk.cameras)-cameras_with_proj)
        sums += cameras_without_proj
  
                
        return sums

    def calcTotalCameraError(self):
        '''calculating the total camera error as shown  
           modified after https://www.agisoft.com/forum/index.php?topic=11077.0'''


        
        chunk = self.chunk
        T = chunk.transform.matrix
        crs = chunk.crs

        sums = 0
        num = 0
        for camera in chunk.cameras:
            
        
            if not camera.transform:
                continue
            if not camera.reference.location:
                continue
                
            if camera.reference.enabled:

                estimated_geoc = chunk.transform.matrix.mulp(camera.center)

                if chunk.camera_crs == None:
                    error =  chunk.crs.unproject(camera.reference.location) - estimated_geoc
                else:
                    error = chunk.camera_crs.unproject(camera.reference.location) - estimated_geoc

                error = error.norm()
                sums += error**2
                num += 1
            
        try:  
            return math.sqrt(sums / num)
        except:
            return None
        
        
    def calcScaleBarErrorControl(self):

        '''calculating the scale bar error in meter as shown in the reference window of the main program
           modified after https://www.agisoft.com/forum/index.php?topic=6147.0'''
    
        chunk = self.chunk #active chunk
        s, n = 0, 0
        for scalebar in chunk.scalebars:
            dist_source = scalebar.reference.distance
            if not dist_source:
                continue #skipping scalebars without source values
                
            if scalebar.reference.enabled:
                
                if type(scalebar.point0) == Metashape.Camera:
                    if not (scalebar.point0.center and scalebar.point1.center):
                        continue #skipping scalebars with undefined ends
                    dist_estimated = (scalebar.point0.center - scalebar.point1.center).norm() * chunk.transform.scale
                else:
                    if not (scalebar.point0.position and scalebar.point1.position):
                        continue #skipping scalebars with undefined ends
                    dist_estimated = (scalebar.point0.position - scalebar.point1.position).norm() * chunk.transform.scale
                dist_error = dist_estimated - dist_source
            
                s= s + dist_error**2
                n+=1
                     
        if n > 0:        
            return math.sqrt(s/n)
        else:
            return None
            
            
    def calcScaleBarErrorCheck(self):
        '''calculating the scale bar error in meter as shown in the reference window of the main program
           modified after https://www.agisoft.com/forum/index.php?topic=6147.0'''
    
        chunk = self.chunk #active chunk
        s, n = 0, 0
        for scalebar in chunk.scalebars:
            dist_source = scalebar.reference.distance
            if not dist_source:
                continue #skipping scalebars without source values
                
            if not scalebar.reference.enabled:
                
                if type(scalebar.point0) == Metashape.Camera:
                    if not (scalebar.point0.center and scalebar.point1.center):
                        continue #skipping scalebars with undefined ends
                    dist_estimated = (scalebar.point0.center - scalebar.point1.center).norm() * chunk.transform.scale
                else:
                    if not (scalebar.point0.position and scalebar.point1.position):
                        continue #skipping scalebars with undefined ends
                    dist_estimated = (scalebar.point0.position - scalebar.point1.position).norm() * chunk.transform.scale
                dist_error = dist_estimated - dist_source
            
                s= s + dist_error**2
                n+=1
                     
        if n > 0:        
            return math.sqrt(s/n)
        else:
            return None



    def calcMarkerErrorControlPoint(self):
        '''calculating the marker error in meter as shown in the reference window of the main program
           modified after https://github.com/agisoft-llc/metashape-scripts/blob/master/src/save_estimated_reference.py'''

        def getCartesianCrs(crs):
            ecef_crs = crs.geoccs
            if ecef_crs is None:
                 ecef_crs = Metashape.CoordinateSystem('LOCAL')

            return ecef_crs



        self.estimated_location = None
        self.reference_location = None
        self.error_location = None
        self.sigma_location = None

        chunk = self.chunk
        s, n = 0, 0

        for marker in chunk.markers:

            if not marker.position:
                continue
                
            if marker.reference.enabled:


                transform = chunk.transform.matrix
                crs = chunk.crs

                if chunk.marker_crs:
                    transform = Metashape.CoordinateSystem.datumTransform(crs, chunk.marker_crs) * transform
                    crs = chunk.marker_crs

                ecef_crs = getCartesianCrs(crs)

                location_ecef = transform.mulp(marker.position)

                self.estimated_location = Metashape.CoordinateSystem.transform(location_ecef, ecef_crs, crs)
                if marker.reference.location:
                    self.reference_location = marker.reference.location
                    self.error_location = Metashape.CoordinateSystem.transform(self.estimated_location, crs, ecef_crs) - Metashape.CoordinateSystem.transform(self.reference_location, crs, ecef_crs)
                    self.error_location = crs.localframe(location_ecef).rotation() * self.error_location

                    s +=  self.error_location.norm()**2
                    n+=1

        try:
            return math.sqrt(s / n)
        except:
            return None
            
            
    def calcMarkerErrorCheckPoint(self):
        '''calculating the marker error in meter as shown in the reference window of the main program
           modified after https://github.com/agisoft-llc/metashape-scripts/blob/master/src/save_estimated_reference.py'''

        def getCartesianCrs(crs):
            ecef_crs = crs.geoccs
            if ecef_crs is None:
                 ecef_crs = Metashape.CoordinateSystem('LOCAL')

            return ecef_crs



        self.estimated_location = None
        self.reference_location = None
        self.error_location = None
        self.sigma_location = None

        chunk = self.chunk
        s, n = 0, 0

        for marker in chunk.markers:
             
            if not marker.position:
                continue
      
          
            if not marker.reference.enabled:
            
             
                transform = chunk.transform.matrix
                crs = chunk.crs

                if chunk.marker_crs:
                    transform = Metashape.CoordinateSystem.datumTransform(crs, chunk.marker_crs) * transform
                    crs = chunk.marker_crs

                ecef_crs = getCartesianCrs(crs)

                location_ecef = transform.mulp(marker.position)

                self.estimated_location = Metashape.CoordinateSystem.transform(location_ecef, ecef_crs, crs)
                if marker.reference.location:
                    self.reference_location = marker.reference.location
                    self.error_location = Metashape.CoordinateSystem.transform(self.estimated_location, crs, ecef_crs) - Metashape.CoordinateSystem.transform(self.reference_location, crs, ecef_crs)
                    self.error_location = crs.localframe(location_ecef).rotation() * self.error_location

                    s +=  self.error_location.norm()**2
                    n+=1

        try:
            return math.sqrt(s / n)
        except:
            return None
  

    def runAllSteps(self):
        ''' Method for automatic execution of all steps in a series marked in the "Automatic execution" field '''

        for index, step in enumerate( self.auto_run_check_boxes.keys() , start=0):

            if self.auto_run_check_boxes[step].isChecked():

                self.tabwidget.setCurrentIndex(index)

                self.executeStep(step = step,
                                    target_percent = float(self.step_widgets[step]['target_percent_ledit'].text()), 
                                    target_threshold = float(self.step_widgets[step]['target_threshold_ledit'].text()), 
                                    max_iter = float(self.step_widgets[step]['max_iter_ledit'].text()),
                                    )
                                    
                self.updateChunkMemoryTree()

            
    

    def setCurrentChunk(self):

        chunk_name = self.chunk_combo_box.currentText()
        self.chunk = self.chunk_dict[chunk_name]

     

    def set_all_points_to_valid(self):
        for p in self.chunk.point_cloud.points:
            p.selected = False

        print(len(self.chunk.point_cloud.points))
        
 
  

def show_window():
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    dlg = NewWindow(parent)
    
    
label = 'SCC'
Metashape.app.addMenuItem(label, show_window)
