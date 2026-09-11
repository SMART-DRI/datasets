# SMART-DRI WP3 Dataset

## QMUL Data Center/DRI

The QMUL Data Center room hosts of clusters for 3 projects

- GridPP (Computing for LHC Particle Physics experiments -- major
  consumer of the room and the project I work on)
- SPCS (a very small portion (6 servers) for the School of Physical and
  Chemical Sciences
- IT Services (ITS) of the university also has few racks there. Although
  the ITS servers have a small contribution to the total power/energy
  when compared to GridPP.

Given below are the information or numbers you need for WP3 analysis -

1\. Voltage level -- design value around 240 V, however value can
fluctuate during days between 230 to 245 V.

2\. Maximum power (rated capacity) -- 390 kW (design capacity).

3\. Total number of compute nodes

- GridPP - 318 nodes (includes compute, storage and infrastructure
  nodes)
- SPCS - 6 nodes
- ITS - 46 nodes (I counted number of nodes for ITS in the room and
  there were 46 nodes online at the time)

4\. Idle Power -- The GridPP nodes in the Data Center have several type
of nodes (Dell, Lenovo, and some are different generations also). Here
are some of the numbers I got from this week's reading. If you need more
or much better numbers I will keep recording Idle Power numbers over the
course of next month whenever the servers are next in Idle state -

- Lenovo SR570 compute node (several nodes) -- 77 W
- Storage node (18 nodes) -- 330 kW (number for 25% capacity from this
  week)
- Storage node (3 nodes) -- 430 kW (number for 35% usage from this week)
- GPU node (8 nodes) -- 328 W (not being used much but GPU driver
  permanently running)

5\. Historical power/energy usage during typical days -- included in the
attached PUE csv dataset. (Recorded every 30 minutes from the
electricity meters in the data center)

6\. Power usage effectiveness (PUE) -- see the attached PUE csv dataset

*Some other information about the DRI*

The Data center is connected to a District Heating system (DHS) (heat
sink) which are placed in a separate cooling plant room in the same
building. The DHS consists of multiple heat pumps which pump out heat
from the data center through a water cooling system (In-row chillers
flowing through the racks in the data center). Now depending on the day
of operations, the district heating runs on single or dual heat pump
operations mode. This affects the PUE calculations also. So when two
heat pumps are ON, the total electricity consumption for the facility
rises and the electricity meter readings take this into account. The PUE
is specially higher during this period \~1.7). You will see this
behaviour in the PUE dataset file I am attaching.
