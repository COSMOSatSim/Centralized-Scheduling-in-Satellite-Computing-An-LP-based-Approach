# SECMotionModel
BSc thesis work about the modeling and simulation of LEO satellite motion
The goal is to define a model for the coverage of LEO satellites, considering their movement. Specifically we want to know

1. how many satellites of a constellation cover a point on the earth with a good coverage without any disturb due to the elevation angle ? 
2. Does the communication latency from the Earth to the satellite depends on the position of the satellite wrt the user?

![Image](https://github.com/user-attachments/assets/a791f28c-b9f0-4b87-9805-ad46fa1b3fe6)

Assumptions:

- A1: the user does not move - it is stationary
- A2: at times t a user is connected with the best satellite (let's say Si), although many satellites (let's say Sz and Sj) can cover the area where the user is 
- A3: we can compute the time interval T to move from the situation where Si is the best satellite to the situation where Si does not cover the user anymore because the elevation angle is too small
- A4: although the earth rotates along its N-S axis, we can assume the task service time is small enough that the heart rotation effect wrt the satellite orbit movement is negligible [3].

Initial papers:

[1] Resource Scheduling and Offloading Strategy Based on LEO Satellite Edge Computing
[2] Computation Offloading in LEO Satellite Networks With Hybrid Cloud and Edge Computing
[3] The Parameters Comparison of the “Starlink” LEO Satellites Constellation for Different Orbital Shells https://www.frontiersin.org/journals/communications-and-networks/articles/10.3389/frcmn.2021.643095/full
