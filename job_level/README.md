# HPC Job Energy and Carbon Dataset Generation

## Overview

This script generates a job-level dataset by combining Slurm accounting records, node-level IPMI power measurements, and grid carbon intensity data. The resulting dataset contains job runtime information, queue waiting times, estimated energy consumption, and associated carbon emissions.

## Input Data Sources

### 1. Slurm Accounting Data (`sacctlog.csv`)

The Slurm accounting dataset contains completed job records exported using `sacct`. Relevant fields include:

* JobID
* Submit time
* Eligible time
* Start time
* End time
* Node allocation
* CPU allocation
* Runtime
* Planned (queue wait) time
* ConsumedEnergy

Only completed jobs are retained. Job step records (e.g., `.batch`, `.extern`) are excluded so that each row corresponds to a single Slurm job allocation.

### 2. IPMI Node Power Data

IPMI datasets contain timestamped node-level power measurements collected from all compute nodes. Each record consists of:

* Timestamp
* Node name
* Instantaneous power (W)

Multiple rack files are combined into a single dataset.

### 3. Carbon Intensity Data

Grid carbon intensity data contains timestamped measurements of carbon intensity in units of gCO₂/kWh.

## Data Processing

### Job Runtime and Queue Metrics

For each completed job:

* Submit, start, and end timestamps are converted to datetime format.

* Runtime is calculated as:

  Runtime = End Time − Start Time

* Waiting time is derived from Slurm's `Planned` field, which represents the interval between job eligibility and job start.

### Energy Processing

Slurm's `ConsumedEnergy` values are converted into Joules and kWh.

Since Slurm reports node-level energy usage, an approximate per-job energy value is computed by scaling energy according to the fraction of allocated CPU cores:

Job Energy = Node Energy × (Allocated CPUs / Maximum CPUs on Node)

### Carbon Emissions

Carbon intensity measurements are matched to job start times using timestamp-based nearest matching.

Carbon emissions are estimated as:

Carbon Emissions (gCO₂) = Energy (kWh) × Carbon Intensity (gCO₂/kWh)

Both grams and kilograms of CO₂ are reported.

## IPMI-Based Energy Allocation

Node-level IPMI power measurements are converted into energy using the elapsed time between consecutive samples for each node.

For each node:

1. Consecutive IPMI readings define a measurement interval.

2. Energy for that interval is computed as:

   Energy (J) = Power (W) × Interval Duration (s)

3. Jobs overlapping each interval are identified.

4. Node energy is allocated among concurrent jobs according to their share of allocated CPU cores:

   Job Share = Allocated CPUs / Total Active CPUs

5. Allocated energy is accumulated across all intervals to obtain job-level IPMI energy estimates.

This approach accounts for overlapping jobs and varying node utilization while avoiding double-counting node energy.

## Output Dataset

The final dataset contains:

### Job Information

* JobID
* Submit time
* Waiting time
* Start time
* End time
* Runtime
* Node allocation

### Resource Allocation

* Allocated CPUs
* Maximum CPUs on node

### Slurm Energy Metrics

* Energy (J)
* Energy (kWh)
* CPU-scaled job energy (J)
* CPU-scaled job energy (kWh)

### Carbon Metrics

* Carbon intensity
* Carbon emissions (gCO₂)
* Carbon emissions (kgCO₂)

### IPMI Energy Metrics

* IPMI energy (J)
* IPMI energy (kWh)
* IPMI-derived carbon emissions (gCO₂)
* IPMI-derived carbon emissions (kgCO₂)

### Validation Metrics

* Ratio between IPMI-derived and Slurm-derived energy estimates

## Assumptions and Limitations

* IPMI power measurements represent total node power consumption.
* Energy is distributed among concurrent jobs in proportion to allocated CPU cores.
* CPU allocation is used as a proxy for energy share; differences in workload intensity are not explicitly modelled.
* Carbon intensity is matched using the closest available timestamp prior to job start.
* Very large gaps in IPMI measurements are excluded to avoid unrealistic energy estimates.
* Multi-node jobs are not explicitly separated into node-level contributions and are associated with the node information available in the Slurm record.

## Generated Outputs

The script produces:

* `jobs_energy_CI_Dataset.csv`

  * Slurm energy and carbon metrics.

* `jobs_CI_ipmi_energy_dataset.csv`

  * Slurm energy metrics, IPMI-derived energy metrics, and carbon estimates.

* `runtime_vs_energy.png`

  * Scatter plot of job runtime versus energy consumption.

* `runtime_vs_njobs.png`

  * Histogram of job runtimes.
