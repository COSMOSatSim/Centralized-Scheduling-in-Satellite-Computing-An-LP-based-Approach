# SECMotionModel: Satellite Edge Computing Motion Simulation Model
BSc thesis work about the modeling and simulation of LEO satellite movement.

Author: Vincenzo Salvatore

The goal is to define a simulation model for the coverage of LEO satellites, considering their movement. Specifically, we want to know

1. how many satellites of a constellation cover a point on the earth with good coverage without any disturbance due to the elevation angle? 
2. Does the communication latency from the Earth to the satellite depend on the position of the satellite with the user?

![Image](https://github.com/user-attachments/assets/a791f28c-b9f0-4b87-9805-ad46fa1b3fe6)

An answer to these questions is provided in [3] and in the analysis provided by Vincenzo.

3. Can we realize a model, to be embedded in the LCB simulator [4], that given a user position on the ground and given one or more satellite orbits on the same shell, allows to determine the satellite to which connect (the one with the lower latency) for demanding the task execution, and what will be the satellite position and latency at the end of the computation? Based on this information, could the model determine if the task should be executed by the same satellite that received the request or by another satellite?

3.1 Dato un area della superfice terrestre coperta da k satelliti (ad es. k=3) che si trovano sullo stesso piano o su piani diversi. Quale e' la strategia che l'utente puo' utilizzare per scegliere il satellite a cui connettersi? scegliera' sempre quello alla massima elevazione? puo' scegliere un satellite in un angolo specificato intorno alla massima elevazione?

3.2 Dato un satellite e un utente, e data la posizione del satellite rispetto all'utente e le posizioni degli altri satelliti che coprono l'area in cui si trova l'utente. Come posso stimare quale sara' il prossimo satellite a cui l'utente si connettera'?

Assumptions:

- A1: the user does not move - it is stationary
- A2: at times t, a user is connected with the best satellite (let's say Si), although many satellites (let's say Sz and Sj) can cover the area where the user is 
- A3: we can compute the time interval T to move from the situation where Si is the best satellite to the situation where Si does not cover the user anymore because the elevation angle is too small
- ????A4: although the earth rotates along its N-S axis, we can assume the task service time is small enough that the heart rotation effect wrt the satellite orbit movement is negligible [3].?????

Initial papers:

[1] Resource Scheduling and Offloading Strategy Based on LEO Satellite Edge Computing

[2] Computation Offloading in LEO Satellite Networks With Hybrid Cloud and Edge Computing

[3] The Parameters Comparison of the “Starlink” LEO Satellites Constellation for Different Orbital Shells https://www.frontiersin.org/journals/communications-and-networks/articles/10.3389/frcmn.2021.643095/full

[4] https://github.com/DMagliarisi/LCB


So far, the following results have been achieved: 
- Relazione_I 
- Relazione_II https://github.com/casalicchio/SECMotionModel/blob/main/Relazione_II_Modello_di%20movimento.pdf
