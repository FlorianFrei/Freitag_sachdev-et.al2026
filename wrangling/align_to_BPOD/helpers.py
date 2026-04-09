''' 
variety of helper functions to transform raw BPOD and raw KS data to an aligned Dataframe
@author: FlorianFreitag
'''
import numpy as np
import pandas as pd
import scipy.io
from scipy.io import matlab


def load_mat(filename): #TODO NOT MY CODE NORA GAVE TO ME
    """
    This function should be called instead of direct scipy.io.loadmat
    as it cures the problem of not properly recovering python dictionaries
    from mat files. It calls the function check keys to cure all entries
    which are still mat-objects
    """

    def _check_vars(d):
        """
        Checks if entries in dictionary are mat-objects. If yes
        todict is called to change them to nested dictionaries
        """
        for key in d:
            if isinstance(d[key], matlab.mio5_params.mat_struct):
                d[key] = _todict(d[key])
            elif isinstance(d[key], np.ndarray):
                d[key] = _toarray(d[key])
        return d
    
    def _todict(matobj):
        """
        A recursive function which constructs from matobjects nested dictionaries
        """
        d = {}
        for strg in matobj._fieldnames:
            elem = matobj.__dict__[strg]
            if isinstance(elem, matlab.mio5_params.mat_struct):
                d[strg] = _todict(elem)
            elif isinstance(elem, np.ndarray):
                d[strg] = _toarray(elem)
            else:
                d[strg] = elem
        return d

    def _toarray(ndarray):
        """
        A recursive function which constructs ndarray from cellarrays
        (which are loaded as numpy ndarrays), recursing into the elements
        if they contain matobjects.
        """
        if ndarray.dtype != 'float64':
            elem_list = []
            for sub_elem in ndarray:
                if isinstance(sub_elem, matlab.mio5_params.mat_struct):
                    elem_list.append(_todict(sub_elem))
                elif isinstance(sub_elem, np.ndarray):
                    elem_list.append(_toarray(sub_elem))
                else:
                    elem_list.append(sub_elem)
            return np.array(elem_list, dtype='object')
        else:
            return ndarray

    data = scipy.io.loadmat(filename, struct_as_record=False, squeeze_me=True)
    return _check_vars(data)

def get_ITI_starts(TTL_states,TTL_sample_times, sample_nums,sample_freq):
    t1 = pd.DataFrame()
    t1['state'] = TTL_states
    t1['time'] = TTL_sample_times
    t2 = t1[t1['state'].isin([1])]
    ITI =(t2['time'] - sample_nums[0]) /  sample_freq
    ITI.reset_index(drop=True,inplace=True)
    return ITI


def BPOD_wrangle(raw_BPOD,ITI,proceed):
    #takes raw MAtlab list of lists and transforms it into a Dataframe of all trials 
    if proceed == True:
        # start and end time in same time as OE data
        start = raw_BPOD['SessionData']['TrialStartTimestamp'] +ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0] 
        end = raw_BPOD['SessionData']['TrialEndTimestamp'] + ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0] 
    
        # calculates the time between Trial end and next trial start
        dead_time=[]
        i=0
        for i in range(len(start) - 1):  # Iterate up to the second-to-last element
            diff = start[i + 1] - end[i]  # Compute the difference between the start of the next trial and the end of the current trial
            dead_time.append(diff)
    
        # Append 0 for the last trial since there's no "dead time" after the last trial
        dead_time.append(0)
                
        # list to Dataframe
        llist=[]
        i=0
        for i in range(len(raw_BPOD['SessionData']['RawEvents']['Trial'])):
            states = raw_BPOD['SessionData']['RawEvents']['Trial'][i]['States']
            hgh = pd.DataFrame.from_dict(states).transpose()
            hgh['type'] = hgh.index
            hgh['Trial'] = i
            hgh.loc[len(hgh.index)] = [hgh[1].max(),hgh[1].max() + dead_time[i],'dead_time',i]
            llist.append(hgh)
        BPOD = pd.concat(llist)
        BPOD.dropna(inplace=True)
        BPOD.reset_index(inplace=True,drop=True)
    
    
        # adds continous time for later steps
        cum =[]
        i= 0
        for i in range(len(BPOD)):
            if i == 0:
                cum.append(BPOD[1][i])
            else:
                temp = BPOD[1][i] - BPOD[0][i]
                diff = temp + cum[i-1]
                cum.append(diff) 
        BPOD['Cont_time'] = cum+ ITI[0]
        BPOD['state_len'] = BPOD[1] - BPOD[0]
        BPOD['Cont_start'] = BPOD['Cont_time']-BPOD['state_len']
        tempp = []
        for i in BPOD['Trial']:
          tempvar = raw_BPOD['SessionData']['TrialTypes'][i]
          tempp.append(tempvar)
           
        BPOD['Trialtype'] = tempp
        return BPOD
    else:
        print("Stop, this is not gonaa work ")

def adjust_BPOD_with_dead_time(BPOD, ITI):
    #makes sure that The BPOD ITI start is always aligned to the ITI TTL signal in OE
  
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
    filtered_data = pd.to_numeric(filtered_data, errors='coerce')
    max_excluded = filtered_data.nlargest(2).iloc[-1]  # Get the second largest value
    print(f"Max absolute value of dead_time2 (excluding the highest): {max_excluded}")



    return BPOD


def Ephys_wrangle(cluster_info,clust,times,sample_freq,surface_estimate):
    #takes raw KS vectos and turns them into a Dataframe  
    #selects only clusters that have the PHY good or MUA label
    low_lim = surface_estimate - 1500
    up_lim = surface_estimate + 100
    
    good_cluster = cluster_info.query('group == "good" | group == "mua"').query('depth>@low_lim').query('depth<@up_lim').loc[:,['cluster_id']]
    Ephys_raw = pd.DataFrame({'cluster_id': clust, 'times':times}, columns=['cluster_id', 'times'])
    Ephys_raw = Ephys_raw.assign(seconds = Ephys_raw['times']/sample_freq)
    Ephys_good = Ephys_raw.merge(good_cluster, on=['cluster_id'],how='inner')
    return Ephys_good

def Ephys_wrangle_bombcell(cluster_info,clust,times,sample_freq):
    #takes raw KS vectos and turns them into a Dataframe  
    #selects only clusters that have the PHY good or MUA label
    

    good_cluster = cluster_info.query('bc_unitType == "GOOD" | bc_unitType == "MUA"').loc[:,['cluster_id']]
    Ephys_raw = pd.DataFrame({'cluster_id': clust, 'times':times}, columns=['cluster_id', 'times'])
    Ephys_raw = Ephys_raw.assign(seconds = Ephys_raw['times']/sample_freq)
    Ephys_good = Ephys_raw.merge(good_cluster, on=['cluster_id'],how='inner')
    return Ephys_good

def bin_Ephys(Ephys_good,bin_size=0.01):
    # raw Kilosort has only data if a spike occoured, this transforms it into evenlz space dintervals and counts how manz spikes occoured 

    max_seconds = Ephys_good['seconds'].max()
    bin_edges = np.arange(0, max_seconds + bin_size, bin_size)

    # Create a new column with bin labels representing the end of each bin
    Ephys_good['time_bin'] = pd.cut(Ephys_good['seconds'], bins=bin_edges, right=False, labels=bin_edges[1:],observed=False)

    # Group by cluster_id and time_bin, then count the number of events
    result = Ephys_good.groupby(['cluster_id', 'time_bin']).size().reset_index(name='event_count')

    # If you want to fill in missing bins with zeros
    all_combinations = pd.MultiIndex.from_product([Ephys_good['cluster_id'].unique(), bin_edges[1:]], names=['cluster_id', 'time_bin'])
    result = result.set_index(['cluster_id', 'time_bin']).reindex(all_combinations, fill_value=0).reset_index()

    return(result)


def Add_Behv(Ephys_binned,BPOD,raw_BPOD,ITI):
    # this matches the BPOD data to the KS data by aligning their timesatamps to the shared trigger (ITI start)
    
    
    start = raw_BPOD['SessionData']['TrialStartTimestamp'] +ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0] 
    end = raw_BPOD['SessionData']['TrialEndTimestamp'] + ITI[0] - raw_BPOD['SessionData']['TrialStartTimestamp'][0] 
    
    EPHYS_trimmed = Ephys_binned.loc[(Ephys_binned['time_bin'] <= end[-1]) & (Ephys_binned['time_bin'] >= start[0])]
    # takes away all KS values before and after the behaviour session
    
    
    EPHYS_trimmed = EPHYS_trimmed.sort_values(by='time_bin').reset_index(drop=True)
    i = 0
    j = 0
    trialtype = []
    trial = []
    Behv = []
    
    while i < len(EPHYS_trimmed) and j < len(BPOD):
        if BPOD['Cont_start'][j] <= EPHYS_trimmed.iloc[i, 1] <= BPOD['Cont_time'][j]:
            trialtype.append(BPOD['type'][j])
            trial.append(BPOD['Trial'][j])
            Behv.append(BPOD['Trialtype'][j])
            i += 1
        else:
            j += 1
            print(j)
    EPHYS_trimmed['Trialtype'] = trialtype 
    EPHYS_trimmed['trial'] = trial 
    EPHYS_trimmed['Behv'] =Behv
    return(EPHYS_trimmed)

def Add_trial(EPHYS_trimmed):
    # this should not be used, just for legacy reasons 
    k=0
    trial =[]
    for i in range(len(EPHYS_trimmed)):
        # Check the condition for ITI
        if EPHYS_trimmed.iloc[i, 3] != 'ITI' and (i + 1 < len(EPHYS_trimmed) and EPHYS_trimmed.iloc[i + 1, 3] == 'ITI'):
            trial.append(k)
            print(k)
            k += 1
        else:
            trial.append(k)

    # Ensure the lengths match before assigning the trial list to the DataFrame
    if len(trial) == len(EPHYS_trimmed):
        EPHYS_trimmed['trial'] = trial
    else:
        # Handle the case where lengths do not match
        raise ValueError("Length of `trial` does not match the length of `EPHYS_trimmed`")
    return(EPHYS_trimmed)


def Raw_to_df_all(cluster_group,clust,times,TTL_states,TTL_sample_times, sample_nums,sample_freq,raw_BPOD,bin_size=0.01):
    #for the brave who trust this code completly 
    ITI = get_ITI_starts(TTL_states, TTL_sample_times, sample_nums,sample_freq)
    BPOD = BPOD_wrangle(raw_BPOD,ITI)
    adjust_BPOD_with_dead_time(BPOD,ITI)
    Ephys_good = Ephys_wrangle(cluster_group,clust,times,ITI,sample_freq)
    Ephys_binned = bin_Ephys(Ephys_good,bin_size=0.01)
    EPHYS_trimmed = Add_Behv(Ephys_binned, BPOD, raw_BPOD, ITI)
    EPHYS_trimmed2 = Add_trial(EPHYS_trimmed)
    return EPHYS_trimmed2




def check_trialnumber_matches(ITI,raw_BPOD):
    proceed = False
    print(f"ITI {len(ITI)}")
    print(f"BPOD: {len(raw_BPOD['SessionData']['TrialStartTimestamp'])}")

    if len(ITI) > len(raw_BPOD['SessionData']['TrialStartTimestamp']):
        print('length does not match, more ITI than BPOD')
        timediff = (ITI[1]-ITI[0]) - (raw_BPOD['SessionData']['TrialStartTimestamp'][1]-raw_BPOD['SessionData']['TrialStartTimestamp'][0])
        print(f'First trial time differs by {timediff}')
        if abs(timediff) < 0.01:
            proceed = True
        else:
            timediff2 = (ITI[2]-ITI[1]) - (raw_BPOD['SessionData']['TrialStartTimestamp'][1]-raw_BPOD['SessionData']['TrialStartTimestamp'][0])
            print(f'second trial time differs by {timediff2}')
            if abs(timediff2) < 0.01:
                print('take trial2')
        
    elif len(ITI) < len(raw_BPOD['SessionData']['TrialStartTimestamp']):
        print('length does not match, more  BPOD than ITI')
        print('what a fail')
    else:
        print('Lengths match.')
        timediff = (ITI[1]-ITI[0]) - (raw_BPOD['SessionData']['TrialStartTimestamp'][1]-raw_BPOD['SessionData']['TrialStartTimestamp'][0])
        print(f'First trial time differs by {timediff}')
        proceed = True
    return proceed

def is_M9_1(raw_BPOD, mat_name):
   """
   here, I started the recording after the Behaviour and by trial and error found that the 29.th ITI is the first ITI in the EphysData
    Modify raw_BPOD for the specific .mat file and reset indexes if conditions are met.
    
    Parameters:
    - raw_BPOD: dict, the BPOD data structure.
    - mat_name: str, the name of the .mat file being processed.
    
    Returns:
    - dict, the modified raw_BPOD if conditions are met; otherwise, the original raw_BPOD.
    """
   if mat_name == 'maybeM9_MA_20240919_180430.mat':
        # Slice the lists
        raw_BPOD['SessionData']['RawEvents']['Trial'] = raw_BPOD['SessionData']['RawEvents']['Trial'][29:]
        raw_BPOD['SessionData']['TrialStartTimestamp'] = raw_BPOD['SessionData']['TrialStartTimestamp'][29:]
        raw_BPOD['SessionData']['TrialEndTimestamp'] = raw_BPOD['SessionData']['TrialEndTimestamp'][29:]
        
        # Reset indexes (reinitialize the lists)
        raw_BPOD['SessionData']['RawEvents']['Trial'] = list(raw_BPOD['SessionData']['RawEvents']['Trial'])
        raw_BPOD['SessionData']['TrialStartTimestamp'] = list(raw_BPOD['SessionData']['TrialStartTimestamp'])
        raw_BPOD['SessionData']['TrialEndTimestamp'] = list(raw_BPOD['SessionData']['TrialEndTimestamp'])
        
        return raw_BPOD
   else:
       return raw_BPOD

