# -*- coding: utf-8 -*-
"""
Created on Mon Aug  5 15:15:16 2024

@author: FlorianFreitag
"""
import os

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

import numpy as np
import pandas as pd
from helpers import*
basefolder ="D:/3198-8539_recall_g2/"
mat_name = next(file for file in os.listdir(basefolder) if file.endswith('.mat'))

#%% load data


cluster_info= pd.read_csv(basefolder + str('/sorted/phy/cluster_info.tsv'),sep = '\t')
clust = np.array (np.load(basefolder + str('/sorted/phy/spike_clusters.npy')))
times = np.array(np.load(basefolder + str('/sorted/phy/spike_times.npy')))[:,0]
ITI = pd.read_csv(basefolder + str('/Meta/threshold_crossings.csv'))
raw_BPOD = load_mat(basefolder + '/' + mat_name)
#surface_estimate = pd.read_csv(basefolder + str('/Meta/surface_estimate.csv'),header=None).iloc[0, 0]

sample_freq = 30000

#%% format ITI


ITI = ITI.iloc[:,0]
#%%
raw_BPOD = is_M9_1(raw_BPOD,mat_name)

#%%
#ITI =ITI[1:].reset_index(drop=True)
proceed = check_trialnumber_matches(ITI, raw_BPOD)

#%% wrangle BPOD
BPOD = BPOD_wrangle(raw_BPOD,ITI,proceed)

#%%
BPOD = adjust_BPOD_with_dead_time(BPOD, ITI)

#%% wrangle EPhys
Ephys_good = Ephys_wrangle_bombcell(cluster_info,clust,times,sample_freq)

#%% bin EPhys

Ephys_binned = bin_Ephys(Ephys_good,bin_size=0.01)
#%% add BEHV
EPHYS_trimmed = Add_Behv(Ephys_binned, BPOD, raw_BPOD, ITI)


#%%

from sklearn.preprocessing import LabelEncoder
import numpy as np

def encode_labels(series):
    le = LabelEncoder()
    return le.fit_transform(series), le
types_encoded, le_types = encode_labels(BPOD['type'].astype(str))
trialtypes_encoded, le_trialtypes = encode_labels(BPOD['Trialtype'].astype(str))

from numba import njit

@njit
def match_trials_numba(time_bins, cont_start, cont_end, types, trials, trialtypes):
    i = 0
    j = 0
    n = len(time_bins)
    type_out = np.full(n, -1, dtype=np.int64)
    trial_out = np.full(n, -1, dtype=np.int64)
    trialtype_out = np.full(n, -1, dtype=np.int64)

    while i < n and j < len(cont_start):
        t = time_bins[i]
        if cont_start[j] <= t <= cont_end[j]:
            type_out[i] = types[j]
            trial_out[i] = trials[j]
            trialtype_out[i] = trialtypes[j]
            i += 1
        else:
            j += 1
    return type_out, trial_out, trialtype_out

def Add_Behv_fast(Ephys_binned, BPOD, raw_BPOD, ITI):
    start = raw_BPOD['SessionData']['TrialStartTimestamp'] + ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0]
    end = raw_BPOD['SessionData']['TrialEndTimestamp'] + ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0]

    EPHYS_trimmed = Ephys_binned.loc[
        (Ephys_binned['time_bin'] <= end[-1]) &
        (Ephys_binned['time_bin'] >= start[0])
    ].sort_values(by='time_bin').reset_index(drop=True)

    time_bins = EPHYS_trimmed['time_bin'].values.astype(np.float64)
    cont_start = BPOD['Cont_start'].values.astype(np.float64)
    cont_end = BPOD['Cont_time'].values.astype(np.float64)
    trials = BPOD['Trial'].values.astype(np.int64)

    types_encoded, le_types = encode_labels(BPOD['type'].astype(str))
    trialtypes_encoded, le_trialtypes = encode_labels(BPOD['Trialtype'].astype(float))

    # Run numba-accelerated matcher
    type_out, trial_out, trialtype_out = match_trials_numba(
        time_bins, cont_start, cont_end, types_encoded, trials, trialtypes_encoded
    )

    # Decode integer labels back to strings
    EPHYS_trimmed['Trialtype'] = le_types.inverse_transform(type_out)         # from BPOD['type']
    EPHYS_trimmed['trial'] = trial_out                                        # from BPOD['Trial']
    EPHYS_trimmed['Behv'] = le_trialtypes.inverse_transform(trialtype_out)    # from BPOD['Trialtype']

    return EPHYS_trimmed

EPHYS_trimmed2 = Add_Behv_fast(Ephys_binned, BPOD, raw_BPOD, ITI)
#%% to csv

EPHYS_trimmed.to_csv(basefolder + str('/M1_recall.csv'))




#%%

ITI_idx = 0
# List to store new rows
new_rows = []

# Iterate through BPOD and identify ITI mismatches
for i in range(len(BPOD)):  # Start from 1 because we need to check the previous row
    row = BPOD.iloc[i]
    
    if row['type'] == 'ITI':
        # Find the true ITI start time
        true_iti = ITI.iloc[ITI_idx]
        ITI_idx += 1
        
        # If BPOD cont_start is earlier than true ITI, we have dead time
        if row['Cont_start'] < true_iti and BPOD.iloc[i - 1]['type'] == 'dead_time':
            dead_time2 = true_iti - row['Cont_start']
            
            # Add a 'dead_time2' row with cont_start from previous row's cont_time
            prev_row = BPOD.iloc[i - 1]
            new_row = {
                'type': 'dead_time2',
                'Cont_start': prev_row['Cont_time'],
                'Cont_time': true_iti,
                'Trial': prev_row['Trial'],   # Carry over trial from the previous row
                0: prev_row[1],           # '0' is '1' from the previous row
                1: prev_row[1] + (true_iti - prev_row['Cont_time']),  # Calculate '1' using state_len
                'state_len': true_iti - prev_row['Cont_time']  # Calculate the new state_len
            }
            new_rows.append((i, new_row))
            
            # Adjust ITI row's Cont_start and Cont_time
            BPOD.at[i, 'Cont_start'] = true_iti
            BPOD.at[i, 'Cont_time'] += dead_time2  # Adjust the Cont_time based on lost time
            BPOD.at[i, 'state_len'] = BPOD.at[i, 'Cont_time'] - BPOD.at[i, 'Cont_start']  # Update state_len
   
            # Now adjust the following rows
            for j in range(i + 1, len(BPOD)):
                BPOD.at[j, 'Cont_start'] += dead_time2
                BPOD.at[j, 'Cont_time'] += dead_time2
                BPOD.at[j, 'state_len'] = BPOD.at[j, 'Cont_time'] - BPOD.at[j, 'Cont_start']  # Update state_len
    elif row['Cont_start'] > true_iti and BPOD.iloc[i - 1]['type'] == 'dead_time':
            print(f"Warning: BPOD Cont_start ({row['Cont_start']}) is later than true ITI ({true_iti}).")
   
            # Add a 'dead_time2' row with negative state_len
            prev_row = BPOD.iloc[i - 1]
            dead_time2 = row['Cont_start'] - true_iti
            new_row = {
                'type': 'dead_time2',
                'Cont_start': true_iti,
                'Cont_time': row['Cont_start'],
                'Trial': prev_row['Trial'],
                0: prev_row[1],
                1: prev_row[1] - dead_time2,
                'state_len': -dead_time2
            }
            new_rows.append((i, new_row))
   
            # Adjust the ITI row's Cont_start to align with true ITI
            row_shift = row['Cont_start'] - true_iti
            BPOD.at[i, 'Cont_start'] = true_iti
            BPOD.at[i, 'Cont_time'] -= row_shift
            BPOD.at[i, 'state_len'] = BPOD.at[i, 'Cont_time'] - BPOD.at[i, 'Cont_start']
   
            # Update subsequent rows
            for j in range(i + 1, len(BPOD)):
                BPOD.at[j, 'Cont_start'] -= row_shift
                BPOD.at[j, 'Cont_time'] -= row_shift
                BPOD.at[j, 'state_len'] = BPOD.at[j, 'Cont_time'] - BPOD.at[j, 'Cont_start']

# Insert new 'dead_time2' rows into the BPOD dataframe
shift = 0  # Track how much we are shifting the index as rows are inserted
for idx, new_row in new_rows:
    idx += shift  # Adjust index by the shift since we're adding rows
    BPOD = pd.concat([BPOD.iloc[:idx], pd.DataFrame([new_row]), BPOD.iloc[idx:]]).reset_index(drop=True)
    shift += 1  # Increment shift since we inserted a row
print(f"Mean value of dead_time2: {BPOD[BPOD['type'] == 'dead_time2']['state_len'].mean()}")
print(f"Max absolute value of dead_time2: {BPOD[BPOD['type'] == 'dead_time2']['state_len'].abs().max()}")
filtered_data = BPOD[BPOD['type'] == 'dead_time2']['state_len'].abs()
max_excluded = filtered_data.nlargest(2).iloc[-1]  # Get the second largest value

print(f"Max absolute value of dead_time2 (excluding the highest): {max_excluded}")
