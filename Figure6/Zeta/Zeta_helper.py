# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 17:43:06 2024

@author: Florian Freitag
"""

import numpy as np
import pandas as pd
import zetapy as zp
import itertools
from tqdm import tqdm

# for single unit
#timess is just the lowest  time- value of a certain state in each Trial / the beginning of that state
# returns the unit id and a p-value
def Zetatest_unit(Data, State,unit,Plot=False, window = 0.4,lag=0.2):
    timess = np.asarray(Data.loc[Data[Data.Trialtype==str(State)].groupby('Trial')['time_bin'].idxmin()]['time_bin'])[np.newaxis].T-lag
    Spikes = np.asarray(Data.query('cluster_id=='+ str(unit)).loc[:,'time_bin'])[np.newaxis].T
    if Plot==False:
        dblZetaP = zp.zetatest(Spikes, timess,dblUseMaxDur=window, intResampNum = 1000)[0] 
    else:
        dblZetaP = zp.zetatest(Spikes, timess,dblUseMaxDur=window,boolPlot=True,intResampNum = 1000)[0] 
    return dblZetaP,unit


# loops trough all units in one recording and appplies the zetatest-unit
def Zetatest_all(Data,State,window=0.4,lag=0.2):
    if State in list(Data['Trialtype']):
        p_vals=[]
        for i in Data['cluster_id'].unique():
            temp = Zetatest_unit(Data,State,i,Plot=False,window= window,lag=lag)
            p_vals.append(temp)
        p_vals = pd.DataFrame.from_records(p_vals,columns=['p_val', 'unit'])
        return p_vals
    else: print('FU')

# loops trough all sessions and applies Zetatest_all
def ZetaMass(Data,Behv,State,lag, window = 2):
    output_data1 = []          
    unique_combinations = list(itertools.product(Data['Mouse'].unique(), Data['Day'].unique()))
    for Mouse, Day in tqdm(unique_combinations, desc="Processing Mice and Days"):
        Data2 = Data.loc[(Data['Day'] == Day) & (Data['Mouse'] == Mouse)]
        ZTd1 = Zetatest_all(Data2.loc[Data2['Behv'] == Behv], State, window=window, lag=lag)
        if ZTd1 is not None:
            for index, row in ZTd1.iterrows():
                output_data1.append([Day, Mouse, row['p_val'], row['unit']])
        else:
            print(f"No data found for Day: {Day}, Mouse: {Mouse}")

    Zetatested = pd.DataFrame(output_data1, columns=['Day', 'Mouse', 'p_val', 'unit'])
    return(Zetatested)