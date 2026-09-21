"""
SMART-DRI Dataset Processing
============================

Script: process_sacct_CI_year_dataset.py 

Purpose
-------
Processes the raw SMART-DRI workload and sustainability data used to
generate the year-long dataset accompanying [https://doi.org/10.5281/zenodo.22798301/add paper title later].

This workflow:
- processes Slurm accounting/workload records;
- cleans and standardises timestamps and job metadata;
- integrates carbon-intensity data;
- derives the variables included in the published dataset;
- uses chunked/memory-efficient processing for the large workload dataset.

IPMI-derived energy is not included in this dataset because corresponding
IPMI telemetry was not available for the full historical period.

Inputs
------
- Slurm accounting data: obatined using this command:
"sacct -X --format=JobID,Submit,Eligible,Start,End,Nodelist,State,Elapsed,Planned,AllocCPUS,NNodes,ConsumedEnergy  --parsable2 --delimiter='|' --starttime=2026-08-01-00:01 --endtime=2026-07-30-00:00 > sacctlog.csv"
- Carbon-intensity data: https://github.com/SMART-DRI/datasets/tree/main/CI_data

Outputs
-------
- jobs_energy_CI_Dataset.csv

Requirements
------------
Python >= 3.12.3
pandas
numpy
matplotlib
collections

Usage
-----
python3 process_sacct_CI_year_dataset.py

Notes
-----
Input/output paths may need to be configured in the section below.

Authors
-------
Dr. Sudha Ahuja
School of Physical and Chemical Sciences
Queen Mary University of London

"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

SACCT_FILES = [
    "sacctlog_August2025_January2026.csv",
    "sacctlog_FebTOJuly2026.csv",
]

OUTPUT_FILE = "jobs_energy_CI_Dataset.csv"

usecols = [
    "JobID", "Submit", "Eligible", "Start", "End",
    "NodeList", "State", "Elapsed", "Planned",
    "AllocCPUS", "NNodes", "ConsumedEnergy"
]

CI_FILE_GLOB = "/home/sudha/WorkDir/SustainabilityStudies/NetDRIVE_2025_2026/SMART_DRI/WP1_datasets/CI_data/Carbon_Intensity_Data_*.csv"

ci_dfs = []

for file in sorted(glob.glob(CI_FILE_GLOB)):
    print("Reading CI file:", file)

    tmp = pd.read_csv(file)
    tmp.columns = tmp.columns.str.strip()

    tmp = tmp.rename(columns={
        "Datetime (UTC)": "timestamp",
        "Actual Carbon Intensity (gCO2/kWh)": "CI"
    })

    tmp = tmp[["timestamp", "CI"]]

    tmp["timestamp"] = pd.to_datetime(
        tmp["timestamp"],
        errors="coerce",
        utc=True
    )

    tmp["CI"] = pd.to_numeric(
        tmp["CI"],
        errors="coerce"
    )

    tmp = tmp.dropna(subset=["timestamp", "CI"])
    ci_dfs.append(tmp)

if not ci_dfs:
    raise RuntimeError(
        f"No CI files found matching {CI_FILE_GLOB}"
    )

ci_df = (
    pd.concat(ci_dfs, ignore_index=True)
    .drop_duplicates(subset=["timestamp"], keep="last")
    .sort_values("timestamp")
    .reset_index(drop=True)
)

ci_start = ci_df["timestamp"].min()
ci_end = ci_df["timestamp"].max()

print("CI coverage:", ci_start, "to", ci_end)

def convert_energy(value):
    if pd.isna(value):
        return np.nan

    value = str(value).strip()

    try:
        if value.endswith("K"):
            return float(value[:-1]) * 1e3

        if value.endswith("M"):
            return float(value[:-1]) * 1e6

        if value.endswith("G"):
            return float(value[:-1]) * 1e9

        return float(value)

    except ValueError:
        return np.nan



daily_counts = defaultdict(int)
node_counts = defaultdict(int)
runtime_group_counts = defaultdict(int)

runtime_bins = [
    0, 1, 5, 15, 30, 60,
    180, 360, 720, 1440,
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

# Store only a sample for the scatter plot
scatter_parts = []

# Fixed histogram bins allow counts to be accumulated
runtime_hist_bins_sec = np.linspace(
    0,
    24 * 3600,
    51
)

runtime_hist_counts = np.zeros(
    len(runtime_hist_bins_sec) - 1,
    dtype=np.int64
)

runtime_hist_bins_min = np.linspace(
    0,
    24 * 60,
    51
)

runtime_hist_counts_min = np.zeros(
    len(runtime_hist_bins_min) - 1,
    dtype=np.int64
)

if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)

write_header = True
total_jobs = 0

for sacct_file in SACCT_FILES:
    print("Reading Slurm file:", sacct_file)

    chunks = pd.read_csv(
        sacct_file,
        sep="|",
        usecols=usecols,
        dtype=str,
        chunksize=25000,
        engine="python"
    )

    for chunk_number, sacct_df in enumerate(chunks, start=1):

        # Keep completed jobs and remove job-step records
        sacct_df = sacct_df.loc[
            (sacct_df["State"] == "COMPLETED")
            & ~sacct_df["JobID"].str.contains(
                ".",
                regex=False,
                na=False
            )
        ].copy()

        if sacct_df.empty:
            continue

        # Remove duplicates within this chunk
        sacct_df = sacct_df.drop_duplicates(
            subset=["JobID", "Submit"],
            keep="last"
        )

        # Time conversion
        sacct_df["submit_time"] = pd.to_datetime(
            sacct_df["Submit"],
            errors="coerce"
        )

        sacct_df["Planned_time"] = pd.to_timedelta(
            sacct_df["Planned"],
            errors="coerce"
        )

        sacct_df["start_time"] = pd.to_datetime(
            sacct_df["Start"],
            errors="coerce"
        )

        sacct_df["end_time"] = pd.to_datetime(
            sacct_df["End"],
            errors="coerce"
        )

        sacct_df["runtime_sec"] = (
            sacct_df["end_time"]
            - sacct_df["start_time"]
        ).dt.total_seconds()

        sacct_df["waitingtime_sec"] = (
            sacct_df["Planned_time"]
            .dt.total_seconds()
        )

        # Extract node number
        sacct_df["node_id"] = (
            sacct_df["NodeList"]
            .str.extract(r"(\d+)", expand=False)
        )

        node_int = pd.to_numeric(
            sacct_df["node_id"],
            errors="coerce"
        )

        # Default CPU count
        sacct_df["MAXCPU"] = 96

        # cn301–cn321 have 256 CPUs
        sacct_df.loc[
            node_int.between(301, 321),
            "MAXCPU"
        ] = 256

        # Energy conversion
        sacct_df["energy_j"] = (
            sacct_df["ConsumedEnergy"]
            .map(convert_energy)
        )

        sacct_df["energy_kwh"] = (
            sacct_df["energy_j"] / 3_600_000
        )

        sacct_df["AllocCPUS"] = pd.to_numeric(
            sacct_df["AllocCPUS"],
            errors="coerce"
        )

        sacct_df["MAXCPU"] = pd.to_numeric(
            sacct_df["MAXCPU"],
            errors="coerce"
        )

        sacct_df["NNodes"] = pd.to_numeric(
            sacct_df["NNodes"],
            errors="coerce"
        )

        sacct_df["energy_j_job"] = (
            sacct_df["energy_j"]
            * sacct_df["AllocCPUS"]
            / sacct_df["MAXCPU"]
        )

        sacct_df["energy_kwh_job"] = (
            sacct_df["energy_j_job"] / 3_600_000
        )

        # Remove invalid records
        sacct_df = sacct_df.dropna(subset=[
            "start_time",
            "end_time",
            "runtime_sec",
            "energy_j",
            "node_id"
        ])

        sacct_df = sacct_df.loc[
            (sacct_df["energy_j"] > 0)
            & (sacct_df["runtime_sec"] > 0)
        ].copy()

        if sacct_df.empty:
            continue

        sacct_df["runtime_min"] = (
            sacct_df["runtime_sec"] / 60
        )

        # Update daily-submission counts
        valid_submit = sacct_df.dropna(
            subset=["submit_time"]
        ).copy()

        submission_counts = (
            valid_submit["submit_time"]
            .dt.floor("D")
            .value_counts()
        )

        for date, count in submission_counts.items():
            daily_counts[date] += int(count)

        # Update allocated-node counts
        current_node_counts = (
            sacct_df["NNodes"]
            .dropna()
            .value_counts()
        )

        for nodes, count in current_node_counts.items():
            node_counts[int(nodes)] += int(count)

        # Update runtime-category counts
        runtime_groups = pd.cut(
            sacct_df["runtime_min"],
            bins=runtime_bins,
            labels=runtime_labels,
            right=False
        )

        current_runtime_counts = (
            runtime_groups.value_counts(sort=False)
        )

        for category, count in current_runtime_counts.items():
            runtime_group_counts[str(category)] += int(count)

        # Update fixed histogram counts
        counts, _ = np.histogram(
            sacct_df["runtime_sec"],
            bins=runtime_hist_bins_sec
        )

        runtime_hist_counts += counts

        counts_min, _ = np.histogram(
            sacct_df["runtime_min"],
            bins=runtime_hist_bins_min
        )

        runtime_hist_counts_min += counts_min

        # Sample points for scatter plot
        sample_size = min(1000, len(sacct_df))

        scatter_parts.append(
            sacct_df[
                ["runtime_sec", "energy_kwh"]
            ].sample(
                n=sample_size,
                random_state=42
            )
        )

        # UTC timestamps for CI matching
        sacct_df["start_time_utc"] = (
            sacct_df["start_time"]
            .dt.tz_localize("UTC")
        )

        sacct_df["end_time_utc"] = (
            sacct_df["end_time"]
            .dt.tz_localize("UTC")
        )

        sacct_df = sacct_df.loc[
            (sacct_df["start_time_utc"] >= ci_start)
            & (sacct_df["end_time_utc"] <= ci_end)
        ].copy()

        if sacct_df.empty:
            continue

        # CI matching for this chunk only
        sacct_df = sacct_df.sort_values(
            "start_time_utc"
        )

        sacct_df = pd.merge_asof(
            sacct_df,
            ci_df,
            left_on="start_time_utc",
            right_on="timestamp",
            direction="backward"
        )

        sacct_df["carbon_g"] = (
            sacct_df["energy_kwh"]
            * sacct_df["CI"]
        )

        sacct_df["carbon_kg"] = (
            sacct_df["carbon_g"] / 1000
        )

        output = sacct_df[[
            "JobID",
            "submit_time",
            "waitingtime_sec",
            "start_time_utc",
            "end_time_utc",
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

        output.to_csv(
            OUTPUT_FILE,
            mode="a",
            index=False,
            header=write_header
        )

        write_header = False
        total_jobs += len(output)

        print(
            f"  Chunk {chunk_number}: "
            f"{len(output):,} jobs written"
        )

print("Total jobs written:", total_jobs)


daily_submissions = pd.DataFrame({
    "submit_date": list(daily_counts.keys()),
    "job_count": list(daily_counts.values())
}).sort_values("submit_date")

plt.figure(figsize=(10, 5))

plt.plot(
    daily_submissions["submit_date"],
    daily_submissions["job_count"],
    marker="o",
    markersize=2
)

plt.xlabel("Submission date")
plt.ylabel("Number of jobs submitted")
plt.title("Daily job submissions")
plt.xticks(rotation=45)
plt.grid(alpha=0.3)
plt.tight_layout()

plt.savefig(
    "job_submissions_per_day.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


nodes_per_job = pd.DataFrame({
    "NNodes": list(node_counts.keys()),
    "job_count": list(node_counts.values())
}).sort_values("NNodes")

plt.figure(figsize=(8, 5))

plt.bar(
    nodes_per_job["NNodes"].astype(str),
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

runtime_group_df = pd.DataFrame({
    "runtime_group": runtime_labels,
    "job_count": [
        runtime_group_counts[label]
        for label in runtime_labels
    ]
})

plt.figure(figsize=(10, 5))

plt.bar(
    runtime_group_df["runtime_group"],
    runtime_group_df["job_count"]
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


bin_widths = np.diff(runtime_hist_bins_min)

plt.figure(figsize=(8, 5))

plt.bar(
    runtime_hist_bins_min[:-1],
    runtime_hist_counts_min,
    width=bin_widths,
    align="edge"
)

plt.xlabel("Job runtime (minutes)")
plt.ylabel("Number of jobs")
plt.title("Distribution of job runtimes up to 24 hours")
plt.grid(alpha=0.3)
plt.tight_layout()

plt.savefig(
    "job_runtime_distribution_minutes.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

scatter_df = pd.concat(
    scatter_parts,
    ignore_index=True
)

# Cap the final sample if there were many chunks
if len(scatter_df) > 100000:
    scatter_df = scatter_df.sample(
        n=100000,
        random_state=42
    )

plt.figure(figsize=(6, 4))

plt.scatter(
    scatter_df["runtime_sec"],
    scatter_df["energy_kwh"],
    alpha=0.25,
    s=5
)

plt.xlabel("Runtime (sec)")
plt.ylabel("Energy (kWh)")
plt.title("Runtime vs energy")
plt.grid(alpha=0.3)
plt.tight_layout()

plt.savefig(
    "runtime_vs_energy.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

