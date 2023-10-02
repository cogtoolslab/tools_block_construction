import os
import sys
proj_dir =  os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(proj_dir)
utils_dir = os.path.join(proj_dir,'utils')
sys.path.append(utils_dir)
agent_dir = os.path.join(proj_dir,'model')
sys.path.append(agent_dir)
agent_util_dir = os.path.join(agent_dir,'utils')
sys.path.append(agent_util_dir)

from scoping_simulations.model.utils.decomposition_functions import *
from scoping_simulations.model.Subgoal_Planning_Agent import Subgoal_Planning_Agent
from scoping_simulations.model.Best_First_Search_Agent import Best_First_Search_Agent
from scoping_simulations.model.Astar_Lookahead_Agent import Astar_Lookahead_Agent
import scoping_simulations.stimuli
import scoping_simulations.utils.blockworld as bw
import scoping_simulations.utils.blockworld_library as bl
import scoping_simulations.experiments.subgoal_generator_runner as experiment_runner

EXP_NAME = "best first superset 1 small"
FRACTION_OF_CPUS = 1
MAX_LENGTH = 3 # maximum length of sequences to consider

if __name__=="__main__": #required for multiprocessing

    try:
        import scoping_simulations.stimuli.tower_generator as tower_generator
    except:
        import tower_generator


    import time
    start_time = time.time()
    
    # create towers on the fly
    block_library = bl.bl_nonoverlapping_simple

    generator = tower_generator.TowerGenerator(8, 8,
                                            block_library=block_library,
                                            seed=3,
                                            padding=(1, 0),
                                            num_blocks=lambda: random.randint(6, 18), #  flat random interval of tower sizes (inclusive)
                                            )

    print("Generating towers")
    NUM_TOWERS  = 24
    towers = []
    for i in tqdm(range(NUM_TOWERS)):
        tower = generator.generate()
        towers.append(tower)

    worlds = [bw.Blockworld(silhouette=t['bitmap'], block_library=bl.bl_nonoverlapping_simple) for t in towers]

    print("Generated {} towers".format(len(worlds)))



    print("Running experiment....")

    superset_decomposer = Rectangular_Keyholes(
        sequence_length=MAX_LENGTH,
        necessary_conditions=[
            Area_larger_than(area=1), # ignore subgoals smaller than the smallest block
            # Area_smaller_than(area=30),
            # Mass_smaller_than(area=18),
            No_edge_rows_or_columns(), # Trim the subgoals to remove empty space on the sides
        ],
        necessary_sequence_conditions=[
            # Complete(), # only consider sequences that are complete—THIS NEEDS TO BE OFF FOR THE SUBGOAL GENERATOR
            No_overlap(), # do not include overlapping subgoals
            Supported(), # only consider sequences that could be buildable in theory
        ]
)

    sga = Subgoal_Planning_Agent(lower_agent=(Best_First_Search_Agent()),
                                        decomposer=superset_decomposer)

    agents = [sga]
    
    results = experiment_runner.run_experiment(worlds,agents,1,1,verbose=False,parallelized=FRACTION_OF_CPUS,save=EXP_NAME,maxtasksperprocess = 1)

    print("Done in %s seconds" % (time.time() - start_time))