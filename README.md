# Centralized ILP Orchestrator for Task Routing in Satellite Networks

> **Bachelor's Thesis in Computer Science** — Sapienza University of Rome  
> **Candidate:** Claudio Bagini (Matr. 2045337)  
> **Advisor:** Dr. Emiliano Casalicchio  
> **Academic Year:** 2025/2026  

---

## Project Overview

Traditional satellite missions operate under a passive **bent-pipe** architecture: satellites act as transparent relays, forwarding raw telemetry and sensory payloads down to terrestrial Ground Stations (GS)[cite: 2, 6, 14]. With the rapid deployment of Low Earth Orbit (LEO) mega-constellations, ground downlinks and ground-station contact windows have become severe communication bottlenecks[cite: 2, 6, 14].

**Orbital Edge Computing (OEC)**—also termed Satellite Computing (SC)—migrates computation directly into orbit[cite: 2, 6, 14]. Embedded processors aboard Satellite Edge Nodes (SENs) analyze raw sensor streams locally, transmitting only distilled insights back to Earth[cite: 2, 6, 14]. 

Orchestrating compute tasks across high-velocity LEO constellations introduces acute physical challenges[cite: 2, 6]:
* **Severe Energy Budgets:** Satellites rely on solar harvesting and onboard batteries, periodically traversing Earth's eclipse shadow (orbital sunset)[cite: 2, 6].
* **Dynamic Mesh Topology:** High orbital velocities (~$7.5\text{ km/s}$) induce continuous link disruptions, variable propagation latencies, and ephemeral Inter-Satellite Links (ISLs)[cite: 2, 6].
* **Constrained Heterogeneous Hardware:** Nodes feature heterogeneous clock frequencies, memory limits, and power coefficients[cite: 2, 6].
* **Strict Temporal Deadlines ($D_r$):** Tasks dropped due to routing or processing delays exceeding $D_r$ waste constrained ISL bandwidth and solar-harvested battery power[cite: 2, 6].

This repository implements a **Centralized Integer Linear Programming (ILP) Orchestrator** designed for multi-hop task offloading and routing across dynamic LEO constellations[cite: 2, 4, 6], featuring an event-driven dynamic batching mechanism and queuing delay compensation[cite: 2, 3, 10].

---

## Objectives

1. **Mathematical Optimization Formulation:** Formalize an exact multi-objective ILP model that jointly optimizes multi-hop ISL routing, compute node placement, fleet battery budgets, and orbital eclipse (sunset) penalties[cite: 2, 4, 6].
2. **Event-Driven Dynamic Batching & Timeout:** Design a non-blocking dual-trigger batching buffer governed by Batch Size ($BS$) and Batch Timeout ($BT$) to curb continuous solver invocation overhead[cite: 2, 3].
3. **Queuing Delay Compensation:** Formulate an analytical deadline adjustment ($D'_r = D_r - T_{batch}$) to protect task slack time against orchestrator accumulation delays[cite: 2, 3, 10].
4. **Discrete-Event Simulation Integration:** Embed the orchestrator and hybrid routing logic within an end-to-end Python/`SimPy` discrete-event simulation environment modeling orbital kinematics (SGP4), optical ISL queues, processor queues, and battery depletion[cite: 2, 3, 8].

---

## System Architecture & Methodology

               +-----------------------------------------------+
               |          Ground Access Points (APs)           |
               +-----------------------------------------------+
                                      |
                            [Task Ingress Batch]
                                      v

+-------------------------------------------------------------------------------------+
|                             MASTER ORCHESTRATOR NODE                                |
|                                                                                     |
|   1. Constellation Mapping (_map_constellation)                                     |
|      - Multi-Source Dijkstra from all APs across active ISL mesh                    |
|      - Evaluated on a 1 MB reference payload with normalized latency and energy     |
|                                                                                     |
|   2. Event-Driven Dynamic Batching (_run_loop)                                      |
|      - Dual trigger: |Buffer| >= BS  OR  elapsed time >= BT                         |
|      - Zero-delay SimPy yield (yield env.timeout(0)) for physical state sync        |
|                                                                                     |
|   3. Mathematical Solver Engine (_solve_ilp via PuLP)                               |
|      - Decision variables: x[r, i] (assignment), y[r] (drop)                        |
|      - Objectives: Latency minimization, Fleet Energy preservation, Sunset penalty  |
|      - Constraints: Uniqueness, Deadlines, Battery capacity, Fair load bound       |
+-------------------------------------------------------------------------------------+
|
+-------------------+-------------------+
|                                       |
v                                       v
[Phase A: Uplink ISL Routing]            [Phase B: Execution & Return]
Planned Dijkstra path to SEN             Local task execution on SEN
(Fallback: Geographic Greedy)            Dynamic Greedy return to AP


### 1. Dynamic Constellation Mapping
Prior to solver execution, the orchestrator gathers a global network snapshot via a **Multi-Source Dijkstra** shortest-path algorithm evaluated from all active Ground Access Points across the ISL mesh[cite: 3, 7]. Links are evaluated using a standardized reference payload ($S_{ref} = 1\text{ MB}$)[cite: 3, 7]:

$$t_{link}(u, v) = \tau_{u, v} + \frac{S_{ref}}{B_{u, v}}$$

$$e_{link}(u, v) = P_{net} \cdot \frac{S_{ref}}{B_{u, v}}$$

The combined dimensionless cost function is[cite: 3, 7]:

$$c_{link}(u, v) = w_R \cdot \left(\frac{t_{link}(u, v)}{T_{max}}\right) + w_e \cdot \left(\frac{e_{link}(u, v)}{E_{max}}\right)$$

### 2. Dynamic Batching & Deadline Compensation
Incoming requests are held in an orchestrator buffer until either a structural or temporal trigger fires[cite: 2, 3]:
* **Structural Threshold:** Buffer length reaches the target Batch Size ($BS$)[cite: 2, 3].
* **Temporal Threshold:** Ingress waiting time reaches the Batch Timeout ($BT$)[cite: 2, 3].

To account for idle time spent waiting in the buffer ($T_{batch}$), task deadlines are adjusted before solving[cite: 2, 3, 10]:

$$D'_r = (1 + \Delta D)(D_r - T_{batch})$$

### 3. Optimization Model Formulation (ILP)
For a batch of requests $R$ and candidate satellites $S$, binary variables $x_{r,i} \in \{0, 1\}$ represent task assignment and $y_r \in \{0, 1\}$ denote request rejection[cite: 3, 4, 6]:

$$\min Z = \begin{cases}  \alpha Z_{time} + \beta Z_{energy} + \gamma Z_{sunset}, & \text{if primary objective is Time} \\ \alpha Z_{energy} + \beta Z_{time} + \gamma Z_{sunset}, & \text{if primary objective is Energy} \end{cases}$$

Subject to[cite: 3, 4, 6, 15]:
1. **Assignment Uniqueness:** $\sum_{i \in S} x_{r,i} + y_r = 1, \quad \forall r \in R$[cite: 3, 7]
2. **Compensated Deadline Compliance:** $x_{r,i} \cdot R_{r,i} \le D'_r, \quad \forall r \in R, \, \forall i \in S$[cite: 3, 7, 10]
3. **Fleet Battery Budget Limits:** $\sum_{r \in R} \sum_{i \in S} x_{r,i} \cdot \epsilon_{r,i,k} \le B_k, \quad \forall k \in S$[cite: 3, 7, 15]
4. **Constellation Fair Load Balancing:** $\sum_{r \in R} x_{r,i} \le \left\lfloor \frac{\vert{}R\vert{}}{\vert{}S\vert{}} \right\rfloor + 5, \quad \forall i \in S$[cite: 3, 15]

### 4. Fault-Tolerant Hybrid Routing
* **Uplink (Phase A):** Packets follow the deterministic Dijkstra shortest path $\vec{P}_{up}$[cite: 3, 7]. If dynamic orbital movement interrupts an intermediate ISL, an autonomous **Geographic Greedy Fallback** (`get_pos_proximity`) redirects traffic using Euclidean distance ranking with loop avoidance[cite: 3, 5, 11].
* **Downlink (Phase B):** Completed task outputs are returned from the executing SEN to the originating gateway via autonomous geographic greedy routing[cite: 3, 5, 11].

---

## Repository Structure

```text
.
├── src/
│   ├── orchestrator.py        # Centralized ILP orchestrator and SimPy batch loop
│   ├── ILP_simulation.py      # Discrete-event simulation routines and task lifecycles
│   ├── Task.py                # Request entity model, deadline and tracking fields
│   ├── EdgeServer.py          # Satellite Edge Node (SEN) compute and queue models
│   ├── AccessPoint.py         # Ground Access Point gateway representation
│   ├── globals.py             # Simulation environment globals and states
│   └── utils.py               # ISL link physics, energy models, and routing helpers
├── config/
│   ├── default_config.json5   # Base constellation and simulation parameters
│   └── constellation_tle/     # Orbital TLE ephemeris datasets
├── experiments/
│   ├── run_benchmarks.py      # Automated parametric simulation runner
│   ├── generate_configs.py    # Multi-seed scenario configuration generator
│   └── slurm_batch_runner.sh  # HPC Slurm job scheduler script
├── docs/
│   └── thesis/                # Complete thesis LaTeX source code
├── requirements.txt           # Environment dependencies
├── LICENSE                    # MIT License
└── README.md                  # Project documentation

Installation & Execution
1. Environment Setup
Bash

git clone [https://github.com/](https://github.com/)<your-username>/centralized-ilp-satellite-orchestrator.git
cd centralized-ilp-satellite-orchestrator

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

2. Running a Single Simulation Instance
Bash

python -m src.ILP_simulation \
    --algorithm ILP-Centralized \
    --batch_size 20 \
    --batch_timeout 0.05 \
    --primary_objective time \
    --arrival_rate 6.0 \
    --energy_budget 80000 \
    --seed 101

Citation
Snippet di codice

@thesis{bagini2026centralized,
  author      = {Claudio Bagini},
  title       = {Centralized ILP Orchestrator for Task Routing in Satellite Networks},
  type        = {Bachelor's Thesis},
  institution = {Sapienza University of Rome},
  faculty     = {Faculty of Information Engineering, Computer Science and Statistics},
  year        = {2026},
  month       = {September}
}

License

This project is licensed under the MIT License.