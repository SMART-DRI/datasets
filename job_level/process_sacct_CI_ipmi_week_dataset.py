"""
Please refer to the year-long processing for additional details.

This workflow generates the week-long integrated dataset and combines
Slurm workload records, CPU/resource information, carbon-intensity data
and IPMI-derived energy information at job level.

Unlike the year-long dataset, IPMI telemetry is available for this
measurement period and is therefore incorporated into the processing.

Outputs                                                                                          
-------                                                                                            
- jobs_CI_ipmi_energy_dataset.csv                                                                  
                                                                                                   
Requirements
------------                                                                                       
Python >= 3.12.3                                                                                   
pandas                                                                                             
numpy                                                                                              
matplotlib                                                                                         
collections                                                                                        
                                                                                                   
Usage                                                                                              
-----                                                                                              
python3 process_sacct_CI_ipmi_dataset.py
  
Notes                                                                                              
-----                                                                                              
Input/output paths may need to be configured in the section below.

Authors                                                                                            
-------                                                                                            
Dr. Sudha Ahuja                                                                                    
School of Physical and Chemical Sciences                                                          
Queen Mary University of London             

"""

import pandas as pd
import numpy as np
import glob
from collections import defaultdict

# INPUT FILES
SACCT_FILE = "SACCT_dataset/sacctlog_april.csv" 
IPMI_FILE_GLOB = "IPMI_dataset/Nodes_Rack*_power.csv"

usecols = [
    "JobID", "Submit", "Eligible", "Start", "End",
    "NodeList", "State", "Elapsed", "Planned",
    "AllocCPUS", "NNodes", "ConsumedEnergy"
]

dfs = []

chunks = pd.read_csv(
    SACCT_FILE,
    sep="|",
    usecols=usecols,
    dtype=str,
    chunksize=50000,
    engine="python"
)

for chunk in chunks:
    chunk = chunk[chunk["State"] == "COMPLETED"]
    chunk = chunk[~chunk["JobID"].str.contains("\\.", na=False)]
    dfs.append(chunk)

sacct_df = pd.concat(dfs, ignore_index=True)

# CLEAN SACCT OUTPUT
sacct_df["submit_time"] = pd.to_datetime(sacct_df["Submit"], errors="coerce")
sacct_df["Planned_time"] = pd.to_timedelta(sacct_df["Planned"], errors="coerce")
sacct_df["start_time"] = pd.to_datetime(sacct_df["Start"], errors="coerce")
sacct_df["end_time"] = pd.to_datetime(sacct_df["End"], errors="coerce")

sacct_df["runtime_sec"] = (sacct_df["end_time"] - sacct_df["start_time"]).dt.total_seconds()
sacct_df["waitingtime_sec"] = (sacct_df["Planned_time"]).dt.total_seconds()

# extract node id
sacct_df["node_id"] = sacct_df["NodeList"].str.extract(r'(\d+)')

node_int = sacct_df["node_id"].astype(int)
sacct_df["MAXCPU"] = 96
sacct_df.loc[node_int.between(301, 321), "MAXCPU"] = 256

def convert_energy(val):
    if isinstance(val, str):
        val = val.strip()
        if val.endswith("K"):
            return float(val[:-1]) * 1e3
        elif val.endswith("M"):
            return float(val[:-1]) * 1e6
        elif val.endswith("G"):
            return float(val[:-1]) * 1e9
    return pd.to_numeric(val, errors="coerce")

sacct_df["energy_j"] = sacct_df["ConsumedEnergy"].apply(convert_energy)
sacct_df["energy_kwh"] = sacct_df["energy_j"] / (1000 * 3600)

sacct_df["AllocCPUS"] = pd.to_numeric(sacct_df["AllocCPUS"], errors="coerce")
sacct_df["MAXCPU"] = pd.to_numeric(sacct_df["MAXCPU"], errors="coerce")

sacct_df["energy_j_job"] = sacct_df["energy_j"] * (sacct_df["AllocCPUS"]/sacct_df["MAXCPU"])
sacct_df["energy_kwh_job"] = sacct_df["energy_j_job"] / (1000 * 3600)

# remove invalid rows
sacct_df = sacct_df.dropna(subset=[
    "start_time", "end_time", "energy_j", "node_id"
])

# sanity filters
sacct_df = sacct_df[
    (sacct_df["energy_j"] > 0) &
    (sacct_df["runtime_sec"] > 0)
]

print("✅ Jobs loaded:", len(sacct_df))

#########################################
## Workload charateristic distributions##
#########################################


## Job energy vs job runtime
import matplotlib.pyplot as plt
plt.figure(figsize=(6,4))
plt.scatter(
    sacct_df["runtime_sec"],
    sacct_df["energy_kwh"],
    alpha=0.5
)
plt.xlabel("Runtime (sec)")
plt.ylabel("Energy (kWh)")
plt.title("Runtime vs Energy")
plt.grid(True)
plt.savefig("runtime_vs_energy.png")
plt.close()


## Job count vs job runtime
plt.figure(figsize=(6,4))
plt.hist(
    sacct_df["runtime_sec"],
    bins=50,
    alpha=0.7
)
plt.xlabel("Runtime (sec)")
plt.ylabel("Number of Jobs")
plt.title("Job Count vs Runtime")
plt.grid(True)
plt.savefig("runtime_vs_njobs.png")
plt.close()


## Number of job submissions per day
daily_submissions = (
    sacct_df
    .dropna(subset=["submit_time"])
    .assign(submit_date=lambda df: df["submit_time"].dt.date)
    .groupby("submit_date")
    .size()
    .reset_index(name="job_count")
)

print(daily_submissions)

plt.figure(figsize=(10, 5))

plt.plot(
    daily_submissions["submit_date"],
    daily_submissions["job_count"],
    marker="o"
)

plt.xlabel("Submission date")
plt.ylabel("Number of jobs submitted")
plt.title("Daily job submissions")
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()

plt.savefig(
    "job_submissions_per_day.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


##Distribution of nodes allocated per job
sacct_df["NNodes"] = pd.to_numeric(
    sacct_df["NNodes"],
    errors="coerce"
)

nodes_per_job = (
    sacct_df
    .dropna(subset=["NNodes"])
    .groupby("NNodes")
    .size()
    .reset_index(name="job_count")
    .sort_values("NNodes")
)

print("Jobs by number of allocated nodes:")
print(nodes_per_job)

plt.figure(figsize=(8, 5))

plt.bar(
    nodes_per_job["NNodes"].astype(int).astype(str),
    nodes_per_job["job_count"]
)

plt.xlabel("Number of nodes allocated")
plt.ylabel("Number of jobs")
plt.title("Distribution of nodes allocated per job")
plt.tight_layout()

plt.savefig(
    "nodes_allocated_per_job.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# ============================================================
## Distribution of job runtimes
# ============================================================

## normal scale
sacct_df["runtime_min"] = sacct_df["runtime_sec"] / 60

runtime_data = sacct_df.loc[
    sacct_df["runtime_min"] > 0,
    "runtime_min"
].dropna()

plt.figure(figsize=(8, 5))

plt.hist(
    runtime_data,
    bins=50
)

plt.xlabel("Job runtime (minutes)")
plt.ylabel("Number of jobs")
plt.title("Distribution of job runtimes")
plt.grid(True)
plt.tight_layout()

plt.savefig(
    "job_runtime_distribution_minutes.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

## log scale 
plt.figure(figsize=(8, 5))

plt.hist(
    runtime_data,
    bins=50
)

plt.xscale("log")
plt.yscale("log")

plt.xlabel("Job runtime (minutes, log scale)")
plt.ylabel("Number of jobs (log scale)")
plt.title("Distribution of job runtimes")
plt.grid(True)
plt.tight_layout()

plt.savefig(
    "job_runtime_distribution_minutes_log.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

## runtime by time groups
runtime_bins = [
    0,
    1,
    5,
    15,
    30,
    60,
    180,
    360,
    720,
    1440,
    float("inf")
]

runtime_labels = [
    "<1 min",
    "1–5 min",
    "5–15 min",
    "15–30 min",
    "30–60 min",
    "1–3 hr",
    "3–6 hr",
    "6–12 hr",
    "12–24 hr",
    ">24 hr"
]

sacct_df["runtime_group"] = pd.cut(
    sacct_df["runtime_min"],
    bins=runtime_bins,
    labels=runtime_labels,
    right=False
)

runtime_groups = (
    sacct_df["runtime_group"]
    .value_counts(sort=False)
    .reset_index()
)

runtime_groups.columns = ["runtime_group", "job_count"]

plt.figure(figsize=(10, 5))

plt.bar(
    runtime_groups["runtime_group"].astype(str),
    runtime_groups["job_count"]
)

plt.xlabel("Job runtime group")
plt.ylabel("Number of jobs")
plt.title("Jobs by runtime category")
plt.xticks(rotation=45)
plt.tight_layout()

plt.savefig(
    "jobs_by_runtime_category.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# ============================================================
##### Intergrating Carbon Intensity data in the dataset
# ============================================================

ci_df = pd.read_csv("CI_data/Carbon_Intensity_Data.csv")

ci_df.columns = ci_df.columns.str.strip()
ci_df = ci_df.rename(columns={
    "Datetime (UTC)": "timestamp",
    "Actual Carbon Intensity (gCO2/kWh)": "CI"})
ci_df["timestamp"] = pd.to_datetime(ci_df["timestamp"])
ci_df = ci_df.sort_values("timestamp")

ci_df = ci_df[["timestamp", "CI"]]

ci_df["timestamp"] = pd.to_datetime(ci_df["timestamp"], utc=True)

sacct_df["start_time"] = pd.to_datetime(sacct_df["start_time"])
sacct_df["start_time_utc"] = (
    sacct_df["start_time"]
    .dt.tz_localize("UTC")             
)

sacct_df["end_time"] = pd.to_datetime(sacct_df["end_time"])
sacct_df["end_time_utc"] = (
    sacct_df["end_time"]
    .dt.tz_localize("UTC") 
)

sacct_df = sacct_df.sort_values("start_time_utc")
ci_df = ci_df.sort_values("timestamp")

start = ci_df["timestamp"].min()
end = ci_df["timestamp"].max()

sacct_df = sacct_df[
    (sacct_df["start_time_utc"] >= start) &
    (sacct_df["end_time_utc"] <= end)
]

# Merge using UTC-aligned columns
sacct_df = pd.merge_asof(
    sacct_df,
    ci_df,
    left_on="start_time_utc",
    right_on="timestamp",
    direction="backward"
)

sacct_df["carbon_g"] = sacct_df["energy_kwh"] * sacct_df["CI"]
sacct_df["carbon_kg"] = sacct_df["carbon_g"] / 1000

output = sacct_df[[
    "JobID",
    "submit_time",
    "waitingtime_sec",
    "start_time",
    "end_time",
    "runtime_sec",
    "NodeList",
    "MAXCPU",
    "AllocCPUS",
    "energy_j",
    "energy_kwh",
    "energy_j_job",
    "energy_kwh_job",
    "carbon_g",
    "carbon_kg"
]]

output.to_csv("jobs_energy_CI_Dataset.csv", index=False)


# ============================================================
# IPMI ENERGY ALLOCATION PER JOB
# Handles multiple jobs per node and irregular IPMI intervals
# ============================================================

# Prepare jobs dataframe
jobs_df = sacct_df[[
    "JobID",
    "node_id",
    "start_time_utc",
    "end_time_utc",
    "AllocCPUS"
]].copy()

jobs_df["JobID"] = jobs_df["JobID"].astype(str)
jobs_df["node_id"] = jobs_df["node_id"].astype(str)
jobs_df["AllocCPUS"] = pd.to_numeric(jobs_df["AllocCPUS"], errors="coerce")

jobs_df["start_time_utc"] = pd.to_datetime(
    jobs_df["start_time_utc"],
    errors="coerce",
    utc=True
)

jobs_df["end_time_utc"] = pd.to_datetime(
    jobs_df["end_time_utc"],
    errors="coerce",
    utc=True
)

jobs_df = jobs_df.dropna(subset=[
    "JobID",
    "node_id",
    "start_time_utc",
    "end_time_utc",
    "AllocCPUS"
])

jobs_df = jobs_df[
    (jobs_df["AllocCPUS"] > 0) &
    (jobs_df["end_time_utc"] > jobs_df["start_time_utc"])
]

jobs_df = jobs_df.sort_values(
    ["node_id", "start_time_utc"]
).reset_index(drop=True)

print("Jobs for IPMI allocation:", len(jobs_df))

# Load IPMI data
ipmi_dfs = []

for file in glob.glob(IPMI_FILE_GLOB):
    print("Reading IPMI file:", file)

    reader = pd.read_csv(
        file,
        names=["timestamp", "node", "power_w"],
        header=None,
        chunksize=50000
    )

    for chunk in reader:
        chunk["timestamp"] = pd.to_datetime(
            chunk["timestamp"],
            errors="coerce",
            utc=True
        )

        chunk["power_w"] = pd.to_numeric(
            chunk["power_w"],
            errors="coerce"
        )

        chunk["node_id"] = (
            chunk["node"]
            .astype(str)
            .str.extract(r"(\d+)")
        )

        chunk = chunk.dropna(subset=[
            "timestamp",
            "node_id",
            "power_w"
        ])

        ipmi_dfs.append(
            chunk[["timestamp", "node_id", "power_w"]]
        )

if not ipmi_dfs:
    raise RuntimeError("No IPMI files were loaded. Check IPMI_FILE_GLOB.")

ipmi_df = pd.concat(ipmi_dfs, ignore_index=True)

ipmi_df["node_id"] = ipmi_df["node_id"].astype(str)

print("Raw IPMI rows:", len(ipmi_df))


# Filter IPMI to useful nodes and time range
nodes_used = jobs_df["node_id"].unique()
ipmi_df = ipmi_df[ipmi_df["node_id"].isin(nodes_used)]

job_start_min = jobs_df["start_time_utc"].min()
job_end_max = jobs_df["end_time_utc"].max()

ipmi_df = ipmi_df[
    (ipmi_df["timestamp"] >= job_start_min - pd.Timedelta(minutes=10)) &
    (ipmi_df["timestamp"] <= job_end_max + pd.Timedelta(minutes=10))
]

print("Filtered IPMI rows:", len(ipmi_df))

# Average duplicate readings per node/timestamp

ipmi_df = (
    ipmi_df
    .groupby(["node_id", "timestamp"], as_index=False)["power_w"]
    .mean()
)

ipmi_df = ipmi_df.sort_values(
    ["node_id", "timestamp"]
).reset_index(drop=True)


# Build IPMI intervals
# Each reading applies until the next reading for that node

ipmi_df["next_timestamp"] = (
    ipmi_df.groupby("node_id")["timestamp"].shift(-1)
)

ipmi_df["dt_sec"] = (
    ipmi_df["next_timestamp"] - ipmi_df["timestamp"]
).dt.total_seconds()

ipmi_df = ipmi_df.dropna(subset=[
    "next_timestamp",
    "dt_sec",
    "power_w"
])

ipmi_df = ipmi_df[
    (ipmi_df["dt_sec"] > 0) &
    (ipmi_df["dt_sec"] <= 600)
]

print("Usable IPMI intervals:", len(ipmi_df))


# Memory-safe allocation
job_energy = defaultdict(float)

for node, node_ipmi in ipmi_df.groupby("node_id", sort=False):
    node_jobs = jobs_df[jobs_df["node_id"] == node].copy()

    if node_jobs.empty:
        continue

    node_jobs = node_jobs.sort_values(
        "start_time_utc"
    ).reset_index(drop=True)

    print(
        f"Allocating node {node}: "
        f"IPMI intervals={len(node_ipmi)}, jobs={len(node_jobs)}"
    )

    for _, sample in node_ipmi.iterrows():
        t0 = sample["timestamp"]
        t1 = sample["next_timestamp"]
        power_w = sample["power_w"]

        active_jobs = node_jobs[
            (node_jobs["start_time_utc"] < t1) &
            (node_jobs["end_time_utc"] > t0)
        ]

        if active_jobs.empty:
            continue

        overlap_start = active_jobs["start_time_utc"].where(
            active_jobs["start_time_utc"] > t0,
            t0
        )

        overlap_end = active_jobs["end_time_utc"].where(
            active_jobs["end_time_utc"] < t1,
            t1
        )

        overlap_sec = (
            overlap_end - overlap_start
        ).dt.total_seconds()

        valid = overlap_sec > 0

        if not valid.any():
            continue

        active_jobs = active_jobs.loc[valid]
        overlap_sec = overlap_sec.loc[valid]

        total_active_cpus = active_jobs["AllocCPUS"].sum()

        if total_active_cpus <= 0:
            continue

        energy_shares = (
            power_w *
            overlap_sec *
            active_jobs["AllocCPUS"] /
            total_active_cpus
        )

        for jobid, energy_j in zip(active_jobs["JobID"], energy_shares):
            job_energy[jobid] += float(energy_j)


# Convert accumulated energy to dataframe

job_ipmi_energy = pd.DataFrame({
    "JobID": list(job_energy.keys()),
    "ipmi_energy_j": list(job_energy.values())
})

print("Jobs with allocated IPMI energy:", len(job_ipmi_energy))


# Merge back into sacct_df

sacct_df["JobID"] = sacct_df["JobID"].astype(str)

for col in [
    "ipmi_energy_j",
    "ipmi_energy_kwh",
    "ipmi_carbon_g",
    "ipmi_carbon_kg",
    "ipmi_vs_slurm_energy_ratio"
]:
    if col in sacct_df.columns:
        sacct_df = sacct_df.drop(columns=[col])

sacct_df = sacct_df.merge(
    job_ipmi_energy,
    on="JobID",
    how="left"
)

sacct_df["ipmi_energy_j"] = sacct_df["ipmi_energy_j"].fillna(0)
sacct_df["ipmi_energy_kwh"] = sacct_df["ipmi_energy_j"] / (1000 * 3600)


# Compare IPMI and Slurm energy

sacct_df["ipmi_vs_slurm_energy_ratio"] = np.where(
    sacct_df["energy_j_job"] > 0,
    sacct_df["ipmi_energy_j"] / sacct_df["energy_j_job"],
    np.nan
)


# Carbon using IPMI energy

sacct_df["ipmi_carbon_g"] = sacct_df["ipmi_energy_kwh"] * sacct_df["CI"]
sacct_df["ipmi_carbon_kg"] = sacct_df["ipmi_carbon_g"] / 1000


# Diagnostics

print("Total sacct jobs after IPMI merge:", len(sacct_df))
print("Jobs with nonzero IPMI energy:", (sacct_df["ipmi_energy_j"] > 0).sum())
print("Total allocated IPMI energy kWh:", sacct_df["ipmi_energy_kwh"].sum())


# Final Output

output = sacct_df[[
    "JobID",
    "submit_time",
    "waitingtime_sec",
    "start_time",
    "end_time",
    "runtime_sec",
    "NodeList",
    "node_id",
    "MAXCPU",
    "AllocCPUS",

    "energy_j",
    "energy_kwh",
    "energy_j_job",
    "energy_kwh_job",

    "CI",
    "carbon_g",
    "carbon_kg",

    "ipmi_energy_j",
    "ipmi_energy_kwh",
    "ipmi_carbon_g",
    "ipmi_carbon_kg",
    "ipmi_vs_slurm_energy_ratio"
]]

output.to_csv("jobs_CI_ipmi_energy_dataset.csv", index=False)

print("✅ DONE: IPMI energy allocated per job")


