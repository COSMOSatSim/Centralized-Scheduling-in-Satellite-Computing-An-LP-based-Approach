# Centralized Scheduling in Satellite Computing: An LP-based Approach

> A centralized **Integer Linear Programming (ILP) orchestrator** for task offloading and multi-hop routing in LEO satellite constellations, with event-driven dynamic batching, evaluated in a SimPy discrete-event simulator.

**Bachelor's Thesis in Computer Science**, Sapienza University of Rome
**Author:** Claudio Bagini (ID 2045337) · **Advisor:** Prof. Emiliano Casalicchio · **Academic Year:** 2025/2026

---

## Overview

Traditional satellites work as passive **bent-pipe** relays: raw data is forwarded to Ground Stations (GS) and processed on Earth. With LEO mega-constellations, downlink capacity and GS contact windows have become a bottleneck.

**Orbital Edge Computing (OEC)**, also called Satellite Computing (SC), moves computation into orbit: Satellite Edge Nodes (SENs) process data locally and downlink only the results. Orchestrating tasks in this environment is hard because of:

- **Tight energy budgets**: solar harvesting, finite batteries, periodic eclipses.
- **Dynamic topology**: satellites move at ~7.5 km/s, so Inter-Satellite Links (ISLs) and latencies change continuously.
- **Heterogeneous, constrained hardware**: different clock frequencies, memory limits and power coefficients.
- **Strict deadlines** ($D_r$): a task that misses its deadline wastes ISL bandwidth and battery energy.

**Research question.** *To what extent can a centralized optimization approach keep global allocation efficient in dense satellite networks before queuing and solver overhead cause systemic degradation?*

## Contributions

1. **ILP model** that jointly optimizes multi-hop ISL routing, compute-node placement, fleet battery budgets and an orbital-eclipse (sunset) penalty, with two modes: *Mapping Time* and *Mapping Energy*.
2. **Event-driven dynamic batching** governed by Batch Size ($BS$) and Batch Timeout ($BT$), to avoid solving one ILP per request.
3. **Deadline compensation** that accounts for the time a request waits in the orchestrator buffer, so centralized scheduling is compared fairly with decentralized baselines.
4. **Integration in an existing SimPy simulator** with SGP4 orbital kinematics, optical ISL queues, processor queues and battery depletion.
5. **Benchmark** against OrbitAware, DTS-base, DTS-Optimal and hierarchical (distributed) ILP, across workload profiles and energy budgets.

## Architecture

```text
               +-----------------------------------------------+
               |          Ground Access Points (APs)           |
               +-----------------------------------------------+
                                       |
                             [Task Ingress Batch]
                                       v
+-------------------------------------------------------------------------------+
|                           MASTER ORCHESTRATOR NODE                            |
|                                                                               |
|  1. Constellation Mapping (_map_constellation)                                |
|     - Multi-source Dijkstra from all APs over the active ISL mesh             |
|     - 1 MB reference payload, normalized latency and energy costs             |
|                                                                               |
|  2. Event-Driven Dynamic Batching (_run_loop)                                 |
|     - Dual trigger: |Buffer| >= BS  OR  elapsed time >= BT                    |
|     - Zero-delay SimPy yield (env.timeout(0)) to sync physical state          |
|                                                                               |
|  3. ILP Solver Engine (_solve_ilp, PuLP + HiGHS)                              |
|     - Variables: x[r,i] (assignment), y[r] (drop)                             |
|     - Objectives: latency, fleet energy, sunset penalty                       |
|     - Constraints: uniqueness, deadlines, batteries, load balancing           |
+-------------------------------------------------------------------------------+
                                       |
                              [Offload Decision]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 1: UPLINK & ISL ROUTING                             |
|  - Planned multi-hop Dijkstra path from AP to the chosen SEN                  |
|  - Fallback: geographic greedy routing if a link breaks                       |
+-------------------------------------------------------------------------------+
                                       |
                                [Task Delivered]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 2: ONBOARD EXECUTION (SEN)                          |
|  - Task runs on the SEN processor queue                                       |
|  - Execution energy is deducted from the satellite battery                    |
+-------------------------------------------------------------------------------+
                                       |
                                [Result Ready]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 3: RESULT DOWNLINK                                  |
|  - Result routed back to the originating AP                                   |
|  - Geographic greedy forwarding over the live ISL topology                    |
+-------------------------------------------------------------------------------+
```

The return path is deliberately **not** planned by the ILP: long tasks outlive the stability window of ISL alignments, so planning the downlink at arrival time would rely on unreliable topology predictions.

## Method

### 1. Constellation mapping

Before each solve, a multi-source Dijkstra runs from every AP over the active ISL graph. Each link is evaluated on a reference payload $S_{ref} = 1\text{ MB}$:

$$t_{link}(u,v) = \tau_{u,v} + \frac{S_{ref}}{B_{u,v}}, \qquad e_{link}(u,v) = P_{net} \cdot \frac{S_{ref}}{B_{u,v}}$$

$$c_{link}(u,v) = w_R \cdot \frac{t_{link}(u,v)}{T_{max}} + w_e \cdot \frac{e_{link}(u,v)}{E_{max}}, \qquad w_R + w_e = 1$$

Dijkstra only finds the path backbone. The ILP then rescales delay and energy using the real payload size of each request.

### 2. Dynamic batching and deadline compensation

Requests wait in the orchestrator buffer until $|Buffer| \ge BS$ or the waiting time reaches $BT$. To avoid penalizing the centralized scheduler for this wait, the deadline includes the expected buffer dwell time:

$$D_r = \begin{cases}
(1 + \Delta D)\,\big(d_{cpu} + d_{net} + d_{down} + \tfrac{1}{2} T_{batch}\big) & \text{with orchestrator} \\
(1 + \Delta D)\,\big(d_{cpu} + d_{net} + d_{down}\big) & \text{without orchestrator}
\end{cases}$$

where $d_{cpu}$, $d_{net}$, $d_{down}$ are execution, uplink and result-return delays, $T_{batch}$ is the batch timeout and $\Delta D$ is the deadline relaxation factor.

### 3. ILP formulation

For a batch $R$ and candidate satellites $S$, let $x_{r,i} \in \{0,1\}$ assign task $r$ to satellite $i$ and $y_r \in \{0,1\}$ drop it. Rejections carry a large penalty $P_{drop} = 10^6$, so the solver drops a task only when it is truly infeasible.

$$Z_{time} = \sum_{r,i} x_{r,i} R_{r,i} + \sum_r y_r P_{drop}, \qquad Z_{energy} = \sum_{r,i} x_{r,i} \epsilon_{r,i} + \sum_r y_r P_{drop}, \qquad Z_{sunset} = \sum_{r,i} x_{r,i} \Omega_i$$

$$\min Z = \begin{cases}
\alpha Z_{time} + \beta Z_{energy} + \gamma Z_{sunset} & \text{Mapping Time} \\
\alpha Z_{energy} + \beta Z_{time} + \gamma Z_{sunset} & \text{Mapping Energy}
\end{cases}$$

subject to:

| Constraint | Formulation |
|---|---|
| Assignment uniqueness | $\sum_{i \in S} x_{r,i} + y_r = 1, \ \forall r \in R$ |
| Deadline compliance | $x_{r,i} \cdot R_{r,i} \le D_r, \ \forall r, i$ |
| Fleet battery budget | $\sum_{r}\sum_{i} x_{r,i}\,\epsilon_{r,i,k} \le B_k, \ \forall k \in S$ |
| Fair load balancing | $\sum_{r} x_{r,i} \le \lfloor \lvert R \rvert / \lvert S \rvert \rfloor + 5, \ \forall i \in S$ |

Here $R_{r,i}$ is the predicted response time (uplink, queues, execution), $\epsilon_{r,i,k}$ the energy spent by satellite $k$ when $r$ runs on $i$, and $\Omega_i \in [0,1]$ the eclipse penalty. When a task is rejected, a diagnostic cascade records the root cause (`No_Route`, `Deadline_Violation`, `Sunset_Violation`, `Energy_Exhaustion`, `Load_Balancing_Rejected`, `Global_ILP_Conflict`).

### 4. Resilient hybrid routing

Packets follow the planned Dijkstra path. If a link breaks mid-flight, the current node switches to **geographic greedy forwarding** (closest neighbour to the destination by Euclidean distance, with a visited-set to avoid loops). If no eligible neighbour remains, the task is dropped as `DROPPED_GREEDY_DEADEND`.

## Experimental setup and key results

**Setup.** Regional Walker-Delta constellation (600 km, 53° inclination), optical ISLs, three workload profiles (mixed, CPU-intensive, data-intensive) with several payload distributions, 40 kJ / 80 kJ battery budgets, arrival rate $\lambda \in \{2, 3, 4, 6, 8, 10\}$ req/s. Tuning in three stages (28 $BS \times BT$ configurations, then the weights $\alpha \times \gamma$, then validation), followed by a benchmark of 9 algorithm configurations.

**Results.**

- **The limit is architectural, not computational.** With $BS \le 20$, HiGHS solves each batch in about 0.30–0.60 ms and onboard execution time stays bounded (about 0.17–0.48 s). Throughput collapses at high load because of **ingress queuing time** in the orchestrator buffer.
- **Two viable batching policies**, both with calibrated weights $\alpha = 1000$, $\gamma = 10$:
  - *Reactive fast-dispatch* ($BS = 20$, $BT = 0.05$ s): lowest latency under light load.
  - *Controlled small-batching* ($BS = 2$, $BT = 2.0$ s): better throughput under heavy load, up to +25% over fast-dispatch in compute-heavy stress.
- **Weight calibration:** up to +19.5% task completion under Time Mapping, no eclipse-related drops with $\gamma = 10$, and no path-bloat latency inflation (>55%) as seen with $\gamma \ge 1000$.
- **Workload-dependent trade-offs:** distributed heuristics sustain higher admission rates at peak load in mixed and compute-heavy workloads. In data-intensive workloads, optimization-based approaches outperform heuristics, in particular the hierarchical ILP (Time). Small-batching is the most competitive centralized configuration for mixed workloads under moderate traffic.
- **Limitations:** single point of failure, telemetry overhead and state staleness. Future work: hybrid two-tier orchestration, reinforcement-learning-based adaptive batching, multi-agent RL and hardware-in-the-loop prototyping.

## Repository structure

| Path | Role |
|---|---|
| `main.py` | Simulation entry point: `python main.py <config.json5> <img_resolution.json5>` |
| `orchestrator.py` | Centralized ILP orchestrator: batching (`_run_loop`), mapping (`_map_constellation`), ILP (`_solve_ilp`), dispatching (`_dispatch_tasks`), hybrid routing and execution (`_route_and_execute_task`) |
| `EdgeServer.py`, `ILP_simulation.py` | Satellite Edge Node state (CPU queue, battery, sunset) and onboard task execution |
| `topology.py`, `Satellite.py`, `SaveCurrentSATOnFile.py` | Constellation topology from TLE data (Skyfield/SGP4) and TLE download from CelesTrak |
| `config.json5`, `img_resolution.json5` | Simulation parameters; workload and payload-size distributions |
| `configsGenerator.py`, `launcher.py`, `run_parallel.sh` | Generation and local parallel execution of experiment campaigns |
| `*.sbatch`, `A_*.sh`, `B_*.sh` | Slurm job scripts (see [`README_cluster.md`](README_cluster.md)) |
| `plotter_sim_*.py`, `plot_analysis_v2.py` | Plots of the experimental results |
| `Tesi/` | LaTeX source and PDF of the thesis |

## Getting started

### Requirements

- **Python 3.12.** The pinned `highspy==1.7.2` in `requirements.txt` provides wheels only up to Python 3.12.
- Internet access for the first run (the satellite TLE data is downloaded from [CelesTrak](https://celestrak.org)).

### Installation

With `pip`:

```bash
git clone https://github.com/baggio2003/Centralized-Scheduling-in-Satellite-Computing.git
cd Centralized-Scheduling-in-Satellite-Computing
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or with [`uv`](https://docs.astral.sh/uv/): `uv sync`, then prefix the commands below with `uv run`.

The core simulator needs `numpy`, `PuLP` + `highspy` (HiGHS solver), `simpy`, `skyfield`, `json5` and `requests`. `matplotlib`, `pandas` and `seaborn` are only needed for the plotting scripts.

### 1. Generate the constellation data (once)

In `config.json5` set `"Build_Configurations": true`, then run:

```bash
python main.py config.json5 img_resolution.json5
```

This downloads the current TLE data and writes the topology files to `data/`, then exits with "File of configurations created". Set `"Build_Configurations"` back to `false` afterwards. The `data/` folder is not versioned.

### 2. Run a single simulation

With `"Load_Configuration": true` and `"SearchNode": "ILP-Centralized"` (the defaults in `config.json5`):

```bash
python main.py config.json5 img_resolution.json5
```

Results are written as CSV files under `result/`, in a folder tree named after the experiment parameters, together with the `used_config.json5` of the run.

### 3. Run an experiment campaign

```bash
python configsGenerator.py           # creates SIMS_SETS/ and SIMS_IMG_RESOLUTIONS/
python launcher.py --filter ILP      # or: ALL, OrbitAware, DTS-base, DTS-APopt
```

`configsGenerator.py` defines the parameter grid (algorithms, seeds, energy budgets, ILP weights) and `launcher.py` runs the configurations in parallel. On a cluster, use the Slurm scripts described in [`README_cluster.md`](README_cluster.md).

### Orchestrator parameters

| Key in `config.json5` | Symbol | Meaning |
|---|---|---|
| `centralized_batch_size` | $BS$ | Maximum batch size |
| `centralized_batch_timeout` | $BT$ | Batch timeout (s) |
| `centralized_primary_objective` | | `"time"` (Mapping Time) or `"energy"` (Mapping Energy) |
| `centralized_primary_weight`, `centralized_secondary_weight`, `centralized_sunset_weight` | $\alpha$, $\beta$, $\gamma$ | Objective weights |
| `centralized_w_r`, `centralized_w_e` | $w_R$, $w_e$ | Dijkstra routing cost weights |

The thesis configurations use $(BS, BT) = (20, 0.05\text{ s})$ or $(2, 2.0\text{ s})$ with $\alpha = 1000$, $\beta = 1$, $\gamma = 10$. The defaults shipped in `config.json5` are different, so adjust them to reproduce the thesis results.

## Acknowledgements

The simulator is built on top of the [SECMotionModel](https://github.com/casalicchio/SECMotionModel) framework developed in Prof. Casalicchio's group (originally by Vincenzo Salvatore). The baseline algorithms follow E. Casalicchio et al., *Handling of energy- and time-constrained heterogeneous satellite computing services*, IEEE ICDCS 2025. The centralized ILP orchestrator, the dynamic batching with deadline compensation, the hybrid routing and the experimental evaluation are the contribution of this thesis.

## License

Released under the GNU General Public License v3.0, see [`LICENSE`](LICENSE).
```