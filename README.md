# **Centralized ILP Orchestrator for Task Routing in Satellite Networks**

**Bachelor's Degree Thesis in Computer Science**  
**Candidate:** Claudio Bagini (Matr. 2045337\)  
**Advisor:** Dr. Emiliano Casalicchio  
**Institution:** Sapienza University of Rome — Faculty of Information Engineering, Computer Science and Statistics  
**Academic Year:** 2025/2026

## **1\. Executive Summary & Motivation**

Traditional satellite architectures operate under a passive "bent-pipe" paradigm: satellites act as transparent relays, forwarding raw telemetry and observation payloads directly to terrestrial Ground Stations (GS) for centralized offline processing. With the massive deployment of Low Earth Orbit (LEO) mega-constellations (such as Starlink and OneWeb), downlink channels and ground-station contact windows have become severe communication bottlenecks.  
Orbital Edge Computing (OEC)—also known as Satellite Computing (SC)—alleviates this saturation by deploying computing hardware directly onto Satellite Edge Nodes (SENs). Raw sensory payloads (e.g., Earth Observation, maritime AIS, and IoT streams) are processed in orbit, downlinking only distilled insights or compressed actionable results.  
However, orchestrating compute tasks across high-velocity LEO constellations poses multi-dimensional challenges:

> * **Severe Energy Budgets:** SENs rely on photovoltaic charging and onboard battery storage, cyclically entering Earth's eclipse shadow (orbital sunset). Overloading nodes risks battery depletion, thermal degradation, or node failure.  
> * **Continuous Dynamic Topology:** High orbital velocities (\~7.5 km/s) induce dynamic link reconfigurations, variable propagation latencies, and intermittent Inter-Satellite Links (ISLs).  
> * **Heterogeneous Hardware Constraints:** SENs possess heterogeneous CPU clock frequencies, memory limits, and power coefficients.  
> * **Strict Real-Time Deadlines:** Tasks dropped due to transmission, queuing, or execution delays exceeding deadlines waste constrained ISL bandwidth and solar-harvested battery power.

## **2\. Research Objectives**

> 1. **Multi-Objective ILP Formulation:** Formalize a linear optimization model capturing multi-hop ISL routing, compute node execution, fleet battery budgets, and orbital eclipse (sunset) penalties.  
> 2. **Event-Driven Dynamic Batching & Timeout:** Design a non-blocking dual-trigger batching buffer governed by Batch Size (BS) and Batch Timeout (BT), coupled with an analytical deadline correction formula (D'\_r \= D\_r \- T\_batch).  
> 3. **Discrete-Event Simulation Integration:** Embed the centralized orchestrator within an end-to-end Python/SimPy simulation environment modeling SGP4 orbital kinematics, ISL optical/RF queues, processor queues, and battery depletion.  
> 4. **Bottleneck & Systemic Collapse Characterization:** Conduct stress tests under scaling Poisson arrival rates (λ from 2 to 10 req/s) to identify system collapse thresholds, isolating physical capacity saturation from temporal queue starvation.  
> 5. **Multi-Parametric Optimization & Sensitivity Tuning:** Perform macro-tuning (BS, BT, ΔD) and micro-tuning on solver scalarization weights (evaluating α × γ cross-sensitivity) to achieve optimal Pareto trade-offs.  
> 6. **State-of-the-Art Comparative Benchmarking:** Benchmark the centralized ILP against distributed heuristics (OrbitAware, DTS-base, DTS-APopt) and distributed ILP baselines under identical workload distributions.

## **3\. System Architecture & Methodology**

### **Dynamic Constellation Mapping**

Before every optimization cycle, the orchestrator constructs a global snapshot of the constellation via a Multi-Source Dijkstra shortest-path algorithm executed from each active Ground Access Point across the ISL topology. All candidate links are evaluated against a standardized reference payload (1 MB):

c\_link(u, v) \= w\_R \* (t\_link(u, v) / T\_max) \+ w\_e \* (e\_link(u, v) / E\_max)

### **Multi-Objective ILP Mathematical Model**

For a batch of tasks R and candidate Satellite Edge Nodes S:

min Z \= alpha \* Z\_time \+ beta \* Z\_energy \+ gamma \* Z\_sunset

Subject to:  
1\. Decision Uniqueness: sum\_{i in S} x\_{r,i} \+ y\_r \= 1, for all r in R  
2\. Compensated Deadline: x\_{r,i} \* R\_{r,i} \<= D'\_r, for all r in R, i in S  
3\. Fleet Battery Budget: sum\_r sum\_i x\_{r,i} \* epsilon\_{r,i,k} \<= B\_k, for all k in S  
4\. Fair-Share Balancing: sum\_r x\_{r,i} \<= floor(|R| / |S|) \+ 5, for all i in S

### **Fault-Tolerant Hybrid Routing**

> * **Phase A (Uplink):** Packets follow the deterministic shortest path planned by Dijkstra. If link degradation interrupts a hop mid-transit, an autonomous Geographic Greedy Fallback with loop avoidance dynamically bypasses the faulty link.  
> * **Phase B (Result Downlink):** Following task completion, output payloads are routed back to the originating Access Point via autonomous geographic greedy routing across real-time available ISLs.

## **4\. Experimental Benchmarking Summary**

| Evaluation Metric | Centralized ILP Orchestrator | Distributed Heuristics (OrbitAware / DTS)   |
| :---- | :---- | :---- |
| **Low-Load Regime (λ ≤ 4 req/s)** | **Optimal (\~93.8% Success Rate)** | High (\~88–90% Success Rate) |
| **High-Load Regime (λ ≥ 8 req/s)** | Moderate (\~35–45% Success Rate) | **Superior (\~75–76% Success Rate)** |
| **Primary Failure Cause** | Deadline Exceeded (Buffer Dwell Time) | Battery Depletion / Physical CPU Limits |
| **Solver Wall-Clock Time** | **Negligible (\< 0.60 ms per batch)** | Instantaneous (\< 0.05 ms) |
| **Fleet Load Distribution** | **Uniform (Balanced across all planes)** | Hotspot Prone (Concentrated on few SENs) |
| **Average Energy per Used SEN** | **Significantly Lower (\~10–12 kJ)** | Substantially Higher (\~45–50 kJ) |

## **5\. Repository Structure**

.  
|-- src/  
|   |-- orchestrator.py         \# Centralized ILP Orchestrator (SimPy loop, PuLP solver, Dijkstra)  
|   |-- ILP\_simulation.py       \# SimPy discrete-event simulation engine & task lifecycle  
|   |-- Task.py                 \# Task request data model, attributes, and tracking  
|   |-- EdgeServer.py           \# Satellite Edge Node (SEN) compute & network queue models  
|   |-- AccessPoint.py          \# Ground Access Point gateway entities  
|   |-- globals.py              \# Global constellation simulation states and configuration  
|   \`-- utils.py                \# Inter-satellite link physics, energy models, and routing helpers  
|-- config/  
|   |-- default\_config.json5    \# Baseline constellation & simulation parameters  
|   \`-- constellation\_tle/      \# Orbital TLE datasets (SGP4 orbital propagation)  
|-- experiments/  
|   |-- run\_benchmarks.py       \# Parametric batch runner across algorithms and arrival rates  
|   |-- generate\_configs.py     \# Automation script generating multi-seed experimental configs  
|   |-- slurm\_batch\_runner.sh   \# HPC / Slurm cluster execution script  
|   \`-- data\_analysis.py        \# Automated generation of response time breakdowns & success rates  
|-- docs/  
|   |-- thesis/                 \# Full LaTeX source code (Sapienza sapthesis class)  
|   \`-- figures/                \# Publication-ready plots, heatmaps, and diagrams  
|-- requirements.txt            \# Python dependencies  
|-- LICENSE                     \# MIT License  
\`-- README.md                   \# Project presentation & guide

## **6\. Quick Start & Execution**

To run an individual simulation instance with the calibrated Centralized ILP Orchestrator:

python \-m src.ILP\_simulation \\  
    \--algorithm ILP-Centralized \\  
    \--batch\_size 20 \\  
    \--batch\_timeout 0.05 \\  
    \--primary\_objective time \\  
    \--primary\_weight 1000 \\  
    \--sunset\_weight 8 \\  
    \--arrival\_rate 6.0 \\  
    \--energy\_budget 80000 \\  
    \--seed 101

## **7\. Academic Citation**

@thesis{bagini2026centralized,  
  author       \= {Claudio Bagini},  
  title        \= {Centralized ILP Orchestrator for Task Routing in Satellite Networks},  
  type         \= {Bachelor's Thesis},  
  institution  \= {Sapienza University of Rome},  
  faculty      \= {Faculty of Information Engineering, Computer Science and Statistics},  
  year         \= {2026},  
  month        \= {September}  
}  
