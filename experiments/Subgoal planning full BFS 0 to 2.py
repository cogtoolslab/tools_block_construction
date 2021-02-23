


if __name__=="__main__": #required for multiprocessing
    import os
    import sys
    proj_dir =  os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.append(proj_dir)
    utils_dir = os.path.join(proj_dir,'utils')
    sys.path.append(utils_dir)
    agent_dir = os.path.join(proj_dir,'model')
    sys.path.append(agent_dir)
    agent_util_dir = os.path.join(agent_dir,'utils')
    sys.path.append(agent_util_dir)

    from model.Subgoal_Planning_Agent import *
    from model.utils.decomposition_functions import *
    from model.BFS_Lookahead_Agent import BFS_Lookahead_Agent
    from utils.blockworld import random_scoring
    import utils.blockworld as bw
    import utils.blockworld_library as bl
    import experiments.subgoal_generator_runner as experiment_runner

    import time
    start_time = time.time()

    print("Running experiment....")

    fraction_of_cpus = 1

    agents = [
        # Subgoal_Planning_Agent(
        #         lower_agent=BFS_Lookahead_Agent(horizon=1,scoring_function=bw.random_scoring,only_improving_actions=True),
        #         sequence_length = 8,
        #         include_subsequences=True,
        #         c_weight = 1,
        #         max_cost = 10**2,
        #         step_size=0
        #         ),
        # Subgoal_Planning_Agent(
        #         lower_agent=BFS_Lookahead_Agent(horizon=1,only_improving_actions=True),
        #         sequence_length = 8,
        #         include_subsequences=True,
        #         c_weight = 1,
        #         max_cost = 10**2,
        #         step_size=0
        #         ),
        Subgoal_Planning_Agent(
                lower_agent=BFS_Lookahead_Agent(horizon=2,only_improving_actions=True),
                sequence_length = 8,
                include_subsequences=True,
                c_weight = 1,
                max_cost = 10**2,
                step_size=0
                ),
        ] 

    silhouettes = {i : bl.load_interesting_structure(i) for i in bl.SILHOUETTE16}
    worlds = {'int_struct_'+str(i) : bw.Blockworld(silhouette=s,block_library=bl.bl_silhouette2_default,legal_action_space=True,physics=False) for i,s in silhouettes.items()}
    

    results = experiment_runner.run_experiment(worlds,agents,1,20,verbose=False,parallelized=fraction_of_cpus,save="subgoal planning full BFS0 to 2",maxtasksperprocess = 1)

    print("Done in %s seconds" % (time.time() - start_time))