"""
SMART-DRI Facility Energy and PUE Dataset Processing
====================================================

Purpose
-------
Processes facility- and infrastructure-level energy measurements used to
generate the SMART-DRI energy and Power Usage Effectiveness (PUE) dataset
accompanying the associated data publication.

The workflow:
- loads and cleans energy measurements from the available metering systems;
- aggregates measurements to consistent time intervals;
- integrates IT and cooling energy data;
- removes invalid measurements and applies documented quality-control steps;
- derives facility-level energy metrics and PUE;
- produces the processed data files and supporting plots used for validation.

PUE is calculated from measured facility and IT energy over aligned time
intervals. The specific meter mappings and calculation methodology are
documented in the accompanying paper and repository README.

Inputs
------
- Facility/room electricity meter data
- IT/PDU energy data (obtained from room meter data)
- IRC/cooling energy data (obtained from Schneider's Data Center Electric's (DCE) API tool)
- Additional site-level meter data, where applicable

Outputs
-------
- Processed facility energy dataset (data_center_energy.csv)
- PUE time series (data_center_energy.csv)
- Aggregated energy summaries and validation plots

Requirements
------------
Python >= 3.12.3
pandas
numpy
matplotlib

Notes
-----
Input and output paths should be configured in the section below.
All timestamps are standardised before datasets are aligned and aggregated.

Authors
-------
Sudha Ahuja
School of Physical and Chemical Sciences
Queen Mary University of London

# ------------------------------------------------------------
# PUE calculation (formula used in the code below)
# ------------------------------------------------------------
# The room IT meter includes IRC energy. IRC energy is therefore
# subtracted before calculating the final IT energy:
#
#   IT_energy = room_IT_energy - IRC_energy
#
# Total facility energy is then:
#
#   Facility_energy = IT_energy + panel_energy + IRC_energy
#
# and:
#
#   PUE = Facility_energy / IT_energy
#
# Calculations are performed over aligned time intervals after
# quality-control filtering.

"""

import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
import os

list_dfs = []

## Input Files
# DCE data
IRC_ENERGY_GLOB = "DCE_Data/IRC_*_Unit_Energy_timeseries.csv" # N IRC files, cumulative kWh
#Room meters 
ROOM_METER_GLOB= "EnergyMeterData/EnergyConsumption_*2026.csv" # 30-min interval kWh

## Processing In-row chiller energy raw dataset - obtained from DCE
irc_files = glob.glob(IRC_ENERGY_GLOB)
irc_dfs = []
irc_dfs_gs = []
irc_dfs_its = []

for f in irc_files:
    print("IRC file: ", f)
    df = pd.read_csv(f)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    df = df.rename(columns={'value': 'irc_kwh_cum'})
    df = df.sort_index()
    ## for unplugged IRC values
    df['irc_kwh_cum'] = pd.to_numeric(df['irc_kwh_cum'], errors='coerce')
    df['irc_kwh_cum'] = df['irc_kwh_cum'].ffill()
    if df['irc_kwh_cum'].isna().all():
        df['irc_kwh_cum'] = 0.0
    df['irc_kwh'] = df['irc_kwh_cum'].diff()
    df["irc_kwh"] = df["irc_kwh"].where(df["irc_kwh"] >= 0)
    df = df.dropna(subset=['irc_kwh'])
    irc_dfs.append(df['irc_kwh'])

irc_all = pd.concat(irc_dfs, axis=1).sum(axis=1)
irc_30m = (
    irc_all
        .resample("30T")
        .sum()
        .to_frame(name='irc_kwh')
)


## Processing room meter energy data 
room_files = glob.glob(ROOM_METER_GLOB)
room_dfs = []

for file in room_files:
    print("Reading:", file)
    df = pd.read_csv(file)
    room_dfs.append(df)

room = pd.concat(room_dfs, ignore_index=True)

room["Timestamp_clean"] = (
    room["Timestamp"]
    .str.replace(r"\s+(?:BST|GMT)$", "", regex=True)
)
room['timestamp'] = pd.to_datetime(
    room['Timestamp_clean'],
    dayfirst=True,
    errors='coerce'
)

room = room.rename(columns={
    'PanelBoard30Minutes(kW-hr)': 'panel_kwh', ##Meter reading for the cooling plant energy
    'MR130Minutes(kW-hr)': 'r1_kwh', ##Meter reading for the IT systems (inclusive of IRC energy)
    'MR230Minutes(kW-hr)': 'r2_kwh', ##Meter reading for the IT systems (inclusive of IRC energy)
    'MR330Minutes(kW-hr)': 'r3_kwh' ##Meter reading for the IT systems (inclusive of IRC energy)
})

room = room.dropna(subset=["timestamp"])

room = room.drop_duplicates(subset="timestamp", keep="last")

room = (
    room
    .sort_values("timestamp")
    .set_index("timestamp")
)

print("Files merged:", len(room_files))
print("Total rows:", len(room))
print("Date range:", room.index.min(), "to", room.index.max())

room['room_it_kwh'] = room['r1_kwh'] + room['r2_kwh'] + room['r3_kwh']
room['room_total_kwh'] = room['room_it_kwh'] + room['panel_kwh']

room_30m = room[
    ['room_it_kwh', 'panel_kwh', 'room_total_kwh']
].resample("30T").sum()


#### cleaning the bump peak
series = room_30m['room_it_kwh']

Q1 = series.quantile(0.25)
Q3 = series.quantile(0.75)
IQR = Q3 - Q1
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR

# Identify outliers (optional: inspect first)
outliers = series[(series < lower) | (series > upper)]
print("Outliers detected:")
print(outliers)

room_30m_clean = room_30m[
    (series >= lower) & (series <= upper)
]


##### Comparisons #####
comparison = (
    irc_30m
        .join(room_30m_clean, how='inner')
)


############# PUE ###########
pue_df = room_30m_clean.join(irc_30m, how='inner')

print(pue_df.head(20))

pue_df['final_it_kwh'] = (
    pue_df['room_it_kwh'] - pue_df['irc_kwh']
)

pue_df['facility_kwh_final'] = pue_df['final_it_kwh'] + pue_df['panel_kwh'] + pue_df['irc_kwh']
pue_df["pue"] = np.where(
    pue_df["final_it_kwh"] > 0,
    pue_df["facility_kwh_final"] / pue_df["final_it_kwh"],
    np.nan
)

# Check outliers
pue_outliers = pue_df[
    (pue_df["pue"] < 1.0) |
    (pue_df["pue"] > 2.0)
]

print("PUE outliers:")
print(pue_outliers)

# Remove the entire outlier rows
pue_df = pue_df[
    (pue_df["pue"] >= 1.0) &
    (pue_df["pue"] <= 2.0)
].copy()

pue_df.to_csv("data_center_energy.csv")


########### Plot daily avergage/sum ####################

print(pue_df.index)
print(pue_df.index.is_monotonic_increasing)

# Daily aggregation
daily = (
    pue_df
    .resample("D")
    .agg({
        "facility_kwh_final": "sum",
        "room_it_kwh": "sum",
        "irc_kwh": "sum",
        "pue": "mean"
    })
    .reset_index()
)

fig, (ax1, ax2) = plt.subplots(
    2, 1,
    figsize=(12, 7),
    sharex=True,
    height_ratios=[2, 1]
)

ax1.plot(
    daily["timestamp"],
    daily["facility_kwh_final"],
    label="Total facility energy (IT + IRC + Cooling Plant)"
)

ax1.plot(
    daily["timestamp"],
    daily["room_it_kwh"],
    label="Room meter (IT + IRC)"
)

ax1.plot(
    daily["timestamp"],
    daily["irc_kwh"],
    label="In-Row Chillers (IRC)"
)

ax1.set_ylabel("Daily energy consumption (kWh)")
ax1.set_title("Data centre energy consumption")
ax1.legend()
ax1.grid(True, alpha=0.3)

# PUE
ax2.plot(
    daily["timestamp"],
    daily["pue"],
    label="Daily mean PUE"
)

ax2.set_ylabel("PUE")
ax2.set_xlabel("Date")
ax2.grid(True, alpha=0.3)

plt.tight_layout()

plt.savefig(
    "datacenter_energy_pue_6months.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()




