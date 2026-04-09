# -*- coding: utf-8 -*-
"""
Created on Fri Mar 14 12:49:07 2025

@author: Freitag
"""
import os
import re
import pandas as pd

import sys
sys.path.append(r"C:/Users/Freitag/Documents/GitHub/Master_thesis/OE_BPOD_to_DF")
from helpers import*

#The idea of this code is to keep only those DLC h5 that i can confidently match to a trial. the video aquistion would randomly drop videos, but sequentially name them. this only keeps until the first mismatcjh 
#%%

basefolder ="F:/Florian_paper/Florian/Data/batch3/M7_3"
mat_name = next(file for file in os.listdir(basefolder) if file.endswith('.mat'))
ITI = pd.read_csv(basefolder + str('/Meta/ttl_2.csv'))
ITI = ITI.iloc[:,0]
raw_BPOD = load_mat(basefolder + '/' + mat_name)

proceed = check_trialnumber_matches(ITI, raw_BPOD)
#proceed = True
ITI =ITI[1:].reset_index(drop=True)
BPOD = BPOD_wrangle(raw_BPOD,ITI,proceed)
mapping = {1: 'W2T', 2: 'A2L', 3: 'PC'}
BPOD['Trialtype'] = BPOD['Trialtype'].map(mapping).fillna('Unknown')

start_states = ["Airpuff", "Airpuff2", "W2T_Audio"]
end_states = ["HIT", "Miss"]

# Compute time differences for each Trial
time_differences = (
    BPOD.groupby('Trial')
    .apply(lambda df: df[df['type'].isin(end_states)]['Cont_start'].values[0] - 
                      df[df['type'].isin(start_states)]['Cont_start'].values[0])
).reset_index(name='Time_Difference')

# Merge the computed time differences back into the original DataFrame
BPOD = BPOD.merge(time_differences, on='Trial', how='left')



matchto = BPOD[[ 'Trial','Trialtype','Time_Difference']].drop_duplicates().reset_index()


#%%



# Define the base directory where the H5 files are stored
base_directory = "C:/Users/Freitag/Desktop/h5/h5/sessions/M7/M7_3"

llist = []
# Loop through all subdirectories and files
for root, _, files in os.walk(base_directory):
    for file in files:
        if file.endswith(".h5"):
            file_path = os.path.join(root, file)  # Full file path
            
            # Extract the lowest-level folder name
            lowest_level_folder = os.path.basename(root)
            
            # Extract the file number (digits before 'DLC' in the filename)
            match = re.search(r"(\d+)DLC", file)
            if match:
                file_number = match.group(1)
            else:
                print(f"Skipping {file}: Could not extract file number.")
                continue  # Skip if the filename doesn't match the pattern

            # Load HDF5 data
            data = pd.read_hdf(file_path)

            # Convert to DataFrame if needed
            if isinstance(data, pd.Series):
                df = data.to_frame()
            else:
                df = pd.DataFrame(data)

            # Handle MultiIndex columns (if present)
            if isinstance(df.columns, pd.MultiIndex):
                df = pd.concat([df.columns.to_frame().T, df]).reset_index(drop=True)

            # Drop the first row if it contains header info
            if df.iloc[0].dtype == object:  # If first row is strings, it's a header
                df = df.drop(index=0).reset_index(drop=True)

            # Convert first two rows into proper column names
            df.columns = [f"{bp}@@{cat}" for bp, cat in zip(df.iloc[0], df.iloc[1])]
            df = df.iloc[2:].reset_index(drop=True)  # Remove first two rows (header rows)

            # Add the frame number (row number) as a new column
            df['framenumber'] = df.index + 1  # Row number starts from 1
            llist.append(df)
          
#%%
if len(llist) == len(matchto):
    for i, df in enumerate(llist):
    # Create a new column 'Behv' in each dataframe
        df['Behv'] = matchto.loc[i, 'Trialtype']  # Use the value of Trialtype from matchto
        df['Trial'] = matchto.loc[i, 'Trial']
        df['Time_Difference'] = matchto.loc[i, 'Time_Difference'] 
else:
    print('problematic')
    if len(llist) > len(matchto):  
        print('maybe ok')
        llist2 = llist[:len(matchto)]  
        for i, df in enumerate(llist2):
            df['Behv'] = matchto.loc[i, 'Trialtype']  
            df['Trial'] = matchto.loc[i, 'Trial']
            df['Time_Difference'] = matchto.loc[i, 'Time_Difference']
    else:
        print('not ok, more matchto than h5')
#%%
combined_df = pd.concat(llist, ignore_index=True)
#combined_df.to_csv('C:/Users/Freitag/Desktop/M9_1.csv')
