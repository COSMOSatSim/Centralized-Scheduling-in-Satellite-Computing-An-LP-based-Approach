# Centralized ILP Orchestrator for Task Routing in Satellite Networks

> **Bachelor's Thesis in Computer Science** — Sapienza University of Rome  
> **Candidate:** Claudio Bagini (Matr. 2045337)  
> **Advisor:** Dr. Emiliano Casalicchio  
> **Academic Year:** 2025/2026  
> **Month:** October  

---

## Project Overview

Traditional satellite missions operate under a passive **bent-pipe** architecture: satellites act as transparent relays, forwarding raw telemetry and sensory payloads down to terrestrial Ground Stations (GS). With the rapid deployment of Low Earth Orbit (LEO) mega-constellations, ground downlinks and ground-station contact windows have become severe communication bottlenecks.

**Orbital Edge Computing (OEC)**—also termed Satellite Computing (SC)—migrates computation directly into orbit. Embedded processors aboard Satellite Edge Nodes (SENs) analyze raw sensor streams locally, transmitting only distilled insights back to Earth. 

Orchestrating compute tasks across high-velocity LEO constellations introduces acute physical challenges:
* **Severe Energy Budgets:** Satellites rely on solar harvesting and onboard batteries, periodically traversing Earth's eclipse shadow (orbital sunset).
* **Dynamic Mesh Topology:** High orbital velocities (~7.5 km/s) induce continuous link disruptions, variable propagation latencies, and ephemeral Inter-Satellite Links (ISLs).
* **Constrained Heterogeneous Hardware:** Nodes feature heterogeneous clock frequencies, memory limits, and power coefficients.
* **Strict Temporal Deadlines ($D_r$):** Tasks dropped due to routing or processing delays exceeding $D_r$ waste constrained ISL bandwidth and solar-harvested battery power.

This repository implements a **Centralized Integer Linear Programming (ILP) Orchestrator** designed for multi-hop task offloading and routing across dynamic LEO constellations, featuring an event-driven dynamic batching mechanism and queuing delay compensation.

---

## Objectives

1. **Mathematical Optimization Formulation:** Formalize an exact multi-objective ILP model that jointly optimizes multi-hop ISL routing, compute node placement, fleet battery budgets, and orbital eclipse (sunset) penalties.
2. **Event-Driven Dynamic Batching & Timeout:** Design a non-blocking dual-trigger batching buffer governed by Batch Size ($BS$) and Batch Timeout ($BT$) to curb continuous solver invocation overhead.
3. **Batch Wait Compensation:** Formulate an analytical deadline definition incorporating expected buffer dwell time ($\frac{1}{2} T_{batch}$) and tolerance factor ($\Delta D$) to ensure fair scheduling against decentralized baselines.
4. **Discrete-Event Simulation Integration:** Embed the orchestrator and hybrid routing logic within an end-to-end Python/`SimPy` discrete-event simulation environment modeling orbital kinematics (SGP4), optical ISL queues, processor queues, and battery depletion.

---

## System Architecture & Methodology

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
|     - Multi-Source Dijkstra from all APs across active ISL mesh               |
|     - Evaluated on a 1 MB reference payload with normalized latency & energy  |
|                                                                               |
|  2. Event-Driven Dynamic Batching (_run_loop)                                 |
|     - Dual trigger: |Buffer| >= BS  OR  elapsed time >= BT                    |
|     - Zero-delay SimPy yield (yield env.timeout(0)) for physical state sync   |
|                                                                               |
|  3. Mathematical Solver Engine (_solve_ilp via PuLP)                          |
|     - Decision variables: x[r, i] (assignment), y[r] (drop)                   |
|     - Objectives: Latency minimization, Fleet Energy preservation, Sunset     |
|     - Constraints: Uniqueness, Deadlines, Battery capacity, Fair load bound  |
+-------------------------------------------------------------------------------+
                                       |
                              [Offload Decision]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 1: UPLINK & ISL TASK ROUTING                        |
|  - Packet forwarded along planned multi-hop Dijkstra path from AP to SEN      |
|  - Fallback: Autonomous Geographic Greedy routing in case of link disruption  |
+-------------------------------------------------------------------------------+
                                       |
                                [Task Delivered]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 2: ONBOARD EXECUTION (SEN)                          |
|  - Task processed on designated Satellite Edge Node CPU cores                 |
|  - Local energy consumption deducted from satellite battery budget            |
+-------------------------------------------------------------------------------+
                                       |
                                [Result Ready]
                                       v
+-------------------------------------------------------------------------------+
|                      STEP 3: RESULT DOWNLINK DELIVERY                         |
|  - Processed payload routed back to originating Ground AP                     |
|  - Dynamic Geographic Greedy forwarding over real-time active ISL topology    |
+-------------------------------------------------------------------------------+
```

### 1. Dynamic Constellation Mapping
Prior to solver execution, the orchestrator gathers a global network snapshot via a **Multi-Source Dijkstra** shortest-path algorithm evaluated from all active Ground Access Points across the ISL mesh. Links are evaluated using a standardized reference payload ($S_{ref} = 1\text{ MB}$):

$$t_{link}(u, v) = \tau_{u, v} + \frac{S_{ref}}{B_{u, v}}$$

$$e_{link}(u, v) = P_{net} \cdot \frac{S_{ref}}{B_{u, v}}$$

The combined dimensionless cost function is:

$$c_{link}(u, v) = w_R \cdot \left(\frac{t_{link}(u, v)}{T_{max}}\right) + w_e \cdot \left(\frac{e_{link}(u, v)}{E_{max}}\right)$$

### 2. Dynamic Batching & Deadline Formulation
Incoming requests are held in an orchestrator buffer until either a structural or temporal trigger fires:
* **Structural Threshold:** Buffer length reaches the target Batch Size ($BS$).
* **Temporal Threshold:** Ingress waiting time reaches the Batch Timeout ($BT$).

To prevent the batch aggregation delay from unfairly penalizing centralized scheduling, the service deadline $D_r$ incorporates the expected waiting time in the ingress queue ($\frac{1}{2} T_{batch}$):

$$D_r = \begin{cases} 
(1 + \Delta D) \cdot \left(d_{cpu} + d_{net} + d_{down} + \frac{1}{2} T_{batch}\right), & \text{with Orchestrator} \\
(1 + \Delta D) \cdot \left(d_{cpu} + d_{net} + d_{down}\right), & \text{without Orchestrator} 
\end{cases}$$

Where $d_{cpu}$ is the nominal execution duration, $d_{net}$ is the uplink transmission delay, $d_{down}$ is the result return delay, $T_{batch}$ is the batch timeout, and $\Delta D$ represents the tolerance factor (deadline relaxation).

### 3. Optimization Model Formulation (ILP)
For a batch of requests $R$ and candidate satellites $S$, binary variables $x_{r,i} \in \{0, 1\}$ represent task assignment and $y_r \in \{0, 1\}$ denote request rejection. The optimization target is formulated depending on the chosen primary objective:

* **Primary Objective: Time Minimization**
  $$\min Z_{Time} = \alpha Z_{time} + \beta Z_{energy} + \gamma Z_{sunset}$$

* **Primary Objective: Energy Minimization**
  $$\min Z_{Energy} = \alpha Z_{energy} + \beta Z_{time} + \gamma Z_{sunset}$$

Where $\alpha$ weights the primary performance metric, $\beta$ weights the secondary metric, and $\gamma$ scales the orbital sunset penalty factor.

**Operational Constraints:**
1. **Assignment Uniqueness:** 
   $$\sum_{i \in S} x_{r,i} + y_r = 1, \quad \forall r \in R$$

2. **Deadline Compliance:** 
   $$x_{r,i} \cdot R_{r,i} \le D_r, \quad \forall r \in R, \, \forall i \in S$$

3. **Fleet Battery Budget Limits:** 
   $$\sum_{r \in R} \sum_{i \in S} x_{r,i} \cdot \epsilon_{r,i,k} \le B_k, \quad \forall k \in S$$

4. **Constellation Fair Load Balancing:** 
   $$\sum_{r \in R} x_{r,i} \le \left\lfloor \frac{|R|}{|S|} \right\rfloor + 5, \quad \forall i \in S$$

### 4. End-to-End Task Lifecycle & Routing
* **Step 1 — Uplink & ISL Routing:** Packets follow the deterministic Dijkstra shortest path $\vec{P}_{up}$ from the AP to the designated SEN. If dynamic orbital movement interrupts an intermediate link, an autonomous **Geographic Greedy Fallback** (`get_pos_proximity`) redirects traffic using Euclidean distance ranking with loop avoidance.
* **Step 2 — Onboard Processing:** The assigned SEN enqueues and executes the computation on its local processor, deducting the required execution energy from its onboard battery budget.
* **Step 3 — Result Downlink Delivery:** Completed task results are routed from the servicing SEN back to the originating Ground Access Point via autonomous geographic greedy forwarding across real-time available ISLs.