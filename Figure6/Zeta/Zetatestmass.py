# -*- coding: utf-8 -*-
"""
Created on Tue Feb 20 13:24:50 2024

@author: Florian Freitag
"""

import os

# this makes sure Zeta_helpers can be loaded by setting the working directory to the current folder
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

import numpy as np
import pandas as pd
from Zeta_helper import*
import itertools
import matplotlib.pyplot as plt



#%%

Data = pd.read_csv("E:/Florian_paper/Florian/Aligned_Data/otpo/wrangled_Data/Zetadata.csv")

#%% Zeta_all

# works like this:
    #in the Data, filter where the Task == 'W2T', 
    # in each Trial look for the 'HIT' state
    # do the Zeta test in a 0.3 s window after starting 10ms before HIT
W2T = ZetaMass(Data,'W2T','HIT',lag = 0.01, window = 0.3)
A2L = ZetaMass(Data,'A2L','Airpuff',lag=0.01, window = 0.3)
PC = ZetaMass(Data,'PC','Airpuff2',lag=0.01, window = 0.3)
Whisk = ZetaMass(Data,'W2T','HIT',lag=0.3, window = 0.3)


#%% save data
basefolder = "E:/Florian/Aligned_Data/Analysable_data/wrangled_Data/Zetatests"
W2T.to_csv(basefolder + str('/W2T.csv'))
A2L.to_csv(basefolder + str('/A2L.csv'))
PC.to_csv(basefolder + str('/PC.csv'))
Whisk.to_csv(basefolder + str('/Whisk.csv'))


