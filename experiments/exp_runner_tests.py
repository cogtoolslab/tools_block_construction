if __name__=="__main__": #required for multiprocessing
    import os
    import sys
    proj_dir =  os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    utils_dir = os.path.join(proj_dir,'utils')
    sys.path.append(utils_dir)
    agent_dir = os.path.join(proj_dir,'model')
    sys.path.append(agent_dir)
    agent_util_dir = os.path.join(agent_dir,'utils')
    sys.path.append(agent_util_dir)

    from Beam_Search_Agent import Beam_Search_Agent
    from BFS_Agent import BFS_Agent
    from MCTS_Agent import MCTS_Agent
    from Beam_Search_Agent import Beam_Search_Agent
    from Naive_Q_Agent import Naive_Q_Agent
    from Astar_Agent import Astar_Agent
    import blockworld as bw
    import random
    import blockworld_library as bl
    import experiment_runner
    import time
    start_time = time.time()

    #16 for nightingale
    fraction_of_cpus = 1

    agents = [
        Beam_Search_Agent(beam_width=2,max_depth=40),
        Beam_Search_Agent(beam_width=1,max_depth=40),
        BFS_Agent(horizon=1),
        BFS_Agent(horizon=2),
        MCTS_Agent(horizon=10),
        Naive_Q_Agent(max_episodes=100),
        Astar_Agent(max_steps=10)
    ]

    silhouette8 = [14,11,]#3,13,12,1,15,5]
    silhouettes = {i : bl.load_interesting_structure(i) for i in silhouette8}
    worlds_silhouettes = {'int_struct_'+str(i) : bw.Blockworld(silhouette=s,block_library=bl.bl_silhouette2_default) for i,s in silhouettes.items()}
    worlds_small = {
        'stonehenge_6_4' : bw.Blockworld(silhouette=bl.stonehenge_6_4,block_library=bl.bl_stonehenge_6_4),
        'stonehenge_3_3' : bw.Blockworld(silhouette=bl.stonehenge_3_3,block_library=bl.bl_stonehenge_3_3),
        # 'block' : bw.Blockworld(silhouette=bl.block,block_library=bl.bl_stonehenge_3_3),
        # 'T' : bw.Blockworld(silhouette=bl.T,block_library=bl.bl_stonehenge_6_4),
        # 'side_by_side' : bw.Blockworld(silhouette=bl.side_by_side,block_library=bl.bl_stonehenge_6_4),
    }
    worlds = {**worlds_silhouettes,**worlds_small}

    results = experiment_runner.run_experiment(worlds,agents,1,20,verbose=False,parallelized=True,save='exp_runner_test')
    print(results[['agent_type','world','world_status']])
    print("Done in %s seconds" % (time.time() - start_time))