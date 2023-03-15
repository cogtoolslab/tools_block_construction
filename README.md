# Tools for block construction
Aim of the project is to investigate how people and artificial agents use tools to intervene on the world to make planning easier.

The block tower reconstrution task is based on the one described in [McCarthy, Kirsh, & Fan (2020)](https://cogtoolslab.github.io/pdf/mccarthy_cogsci_2020.pdf) and adapted from the corresponding [`block_construction` repo](https://github.com/cogtoolslab/block_construction).

A subset of this work has been published as:
[Binder, F., Kirsh, D., and Fan, J. (2021). Visual scoping operations for physical assembly. _Proceedings of the 43rd Annual Meeting of the Cognitive Science Society._](http://arxiv.org/abs/2106.05654) 
**See the work corresponding to the cogsci 2021 publication in the [cogsci2021 branch](https://github.com/cogtoolslab/tools_block_construction/tree/cogsci2021)**

## Simple action level planning agents

There are two main classes: worlds and agents. See the classes and derived classes for details. For minimal example run something like:

```
from model.BFS_Lookahead_Agent import BFS_Lookahead_Agent
import utils.blockworld as bw
import utils.blockworld_library as bl

a = BFS_Lookahead_Agent() #create agent
w = bw.Blockworld(silhouette=bl.stonehenge_6_4,
	block_library=bl.bl_stonehenge_6_4) #create environment
a.set_world(w) #connect the two
while w.status() == 'Ongoing': #can we still act?
    a.act(1,verbose=True) #plan and take one action in the environment
print('Finished with world in state:",w.status())
```

The following action level planners are available in `models`:
* A\*
* A\* lookahead
* Beam search lookahead
* Breadth First Search
* Breadth First Search lookahead
* Monte Carlo Tree Search
* Q learning

Use `experiment_runner.py` to run suites of experiments and save them to a data frame in the current directory.

### Analysis
The output of `experiment_runner.py` can be analysed in `Analysis.ipynb` using a variety of measures. 

## Hierarchical agents
`Resource_Rational_Subgoal_Planning_Agent.py` implements hierarchical planning using *resource-rational task decomposition*. This is implemented by calculating all subgoals (when `include_subsequences` up to) `lookahead`  into the future (on the block tower reconstruction task with the provided target structures, there are at most 8 subgoals possible), then selecting the sequence of subgoals that maximizes $area of target filled * c_weight * planning cost$.  
The hierarchical planner can work with all action level planners mentioned above. Pass an instantiated action level planner to `lower_agent`.

In order to speed up the process, the hierarchical planners are implemented as simulations over a precomputed dataframe with solutions and costs to all potential subgoals. 
Use `subgoal_generator_runner.py` to generate a dataframe of all subgoals. This dataframe can then by used to simulate various subgoal planning strategies using `Simulated_Lookahead_Subgoal_Planning_Agent.py`


### Analysis
Analysis of the data generated by `subgoal_generator_runner.py` files is performed with various notebooks in the analysis directory. For analysis and publication-quality figures used in the cogsci 2021 paper, see `cogsci2021.ipynb`.

## Requirements
Try using `$ conda env create -f environment.yml` to install all the required packages in a new environment named `scoping`.

- Python > 3.7
- node.js 

If you `Box2D` will not install in a virtual environment, try the following:
```
conda install swig # needed to build Box2D in the pip install
pip install box2d-py # a repackaged version of pybox2d
```