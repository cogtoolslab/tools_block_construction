# Experiments

The experiments for a certain paper are in the respective subfolders. 

There are two mains ways to run experiments: 
* run the agent directly to generate outcomes (conceptually simple)
* generate the solutions to potential subgoals, then use those to simulate the behavior of certain agents that on the basis of the subgoals (much faster if we have multiple agents or want to see the effect of changing parameters like $\lambda$)

## Run the agent directly

Make a file that imports and uses [experiment_runner.py](src/scoping_simulations/stimuli/experiment_runner.py).

```
if __name__ == "__main__":  # required for multiprocessing
    import os
    import sys
    from scoping_simulations.utils import PROJ_DIR, STIM_DIR
    
    from scoping_simulations.model.Subgoal_Planning_Agent import *
    from scoping_simulations.model.utils.decomposition_functions import *
    from scoping_simulations.model.BFS_Agent import BFS_Agent
    from scoping_simulations.model.Astar_Agent import Astar_Agent
    from scoping_simulations.model.Best_First_Search_Agent import Best_First_Search_Agent
    import scoping_simulations.utils.blockworld as bw
    import scoping_simulations.utils.blockworld_library as bl
    import scoping_simulations.experiments.experiment_runner as experiment_runner
    import scoping_simulations.experiments.subgoal_generator_runner as subgoal_generator_runner
    import scoping_simulations.stimuli.tower_generator
    import tqdm

    import pickle

    import time
    start_time = time.time()

    print("Running experiment....")

    fraction_of_cpus = 1

    # # loading towers from disk
    # PATH_TO_TOWERS = os.path.join(
    #     STIM_DIR, 'generated_towers_bl_nonoverlapping_simple.pkl')
    # # load towers
    # with open(PATH_TO_TOWERS, 'rb') as f:
    #     towers = pickle.load(f)

    # create towers on the fly
    print("Generating towers...")
    block_library = bl.bl_nonoverlapping_simple
    generator = stimuli.tower_generator.TowerGenerator(8, 8,
                                                       block_library=block_library,
                                                       seed=42,
                                                       padding=(2, 0),
                                                       num_blocks=lambda: random.randint(
                                                           5, 10),
                                                       physics=True,
                                                       )
    NUM_TOWERS = 64
    towers = []
    for i in tqdm.tqdm(range(NUM_TOWERS)):
        towers.append(generator.generate())

    for i in range(len(towers)):
        towers[i]['name'] = str(i)
    towers = {t['name']: t['bitmap'] for t in towers}
    worlds = {name: bw.Blockworld(silhouette=silhouette, block_library=bl.bl_nonoverlapping_simple,
                                  legal_action_space=True, physics=True) for name, silhouette in towers.items()}
    print("Made {} towers".format(len(towers)))

    lower_agent = Best_First_Search_Agent(random_seed=42)

    scoping_decomposer = Rectangular_Keyholes(
        sequence_length=1,
        necessary_conditions=[
            Area_larger_than(area=1),
            # maximum subgoal size is 3/4 of the mass of the tower. Prevents degeneratee case of 1 subgoal
            Proportion_of_silhouette_less_than(ratio=3/4),
            No_edge_rows_or_columns(),
            Fewer_built_cells(0),
        ],
        necessary_sequence_conditions=[
            No_overlap(),
            Supported(),
        ]
    )

    lookahead2_decomposer = Rectangular_Keyholes(
        sequence_length=2,
        necessary_conditions=[
            Area_larger_than(area=1),
            # maximum subgoal size is 3/4 of the mass of the tower. Prevents degeneratee case of 1 subgoal
            Proportion_of_silhouette_less_than(ratio=3/4),
            No_edge_rows_or_columns(),
            Fewer_built_cells(0),
        ],
        necessary_sequence_conditions=[
            No_overlap(),
            Supported(),
            Filter_for_length(2),
        ]
    )

    # now we need to generate a number of scoping agents across ranges of c_weight
    
    lambdas = np.arange(0, 1.1, 0.1)

    scoping_agents = [Subgoal_Planning_Agent(lower_agent=lower_agent,
                                             decomposer=scoping_decomposer,
                                             random_seed=42,
                                             c_weight=cw,
                                             step_size=1,
                                             max_number_of_sequences=8192,
                                             label="Incremental Scoping lambda={}".format(cw)) for cw in lambdas]

    lookahead2_agents = [Subgoal_Planning_Agent(lower_agent=lower_agent,
                                                decomposer=lookahead2_decomposer,
                                                random_seed=42,
                                                c_weight=cw,
                                                step_size=1,
                                                max_number_of_sequences=8192,
                                                label="Lookahead Scoping lambda={}".format(cw)) for cw in lambdas]

    print("Running experiment...")
    results_sg = experiment_runner.run_experiment(
        worlds,
        [*lookahead2_agents],
        per_exp=10,
        steps=16,
        verbose=False,
        parallelized=fraction_of_cpus,
        save="RLDM_lookahead_scoping_experiment",
        maxtasksperprocess=5)

    print("Done in %s seconds" % (time.time() - start_time))
```

## Generate the solutions to potential subgoals

The general principle is to use a `Subgoal_Planning_Agent` with whatever lower agent (ie. `BFS_Agent`) and whatever decomposer (ie. `Rectangular_Keyholes`) you want to use. 
The decomposer needs to produce the superset of all subgoal sequences you want to simulate.
Ensure that the decomposer does not only return full sequences (ie. `necessary_sequence_conditions` does not include `Complete()`). 

Run this agent to generate all solved sequences (along with behavior, but we discard this) using `subgoal_generator_runner.py`.
The simulated agents will use the cached action level search of the parent agent (from above), but will do so only on the subset generated by the their decomposer.
So, the different agent types are defined by the decomposer used.

Refer to [experiments/Simulate_Subgoals_Template.py](experiments/Simulate_Subgoals_Template.py) for an example of how to do this.