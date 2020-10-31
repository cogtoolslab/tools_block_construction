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

    from model.BFS_Agent import BFS_Agent
    import model.Construction_Paper_Agent as CPA
    import utils.blockworld as bw
    import utils.blockworld_library as bl
    import experiments.experiment_runner as experiment_runner

    import time
    start_time = time.time()

    #16 for nightingale, 96 for google cloud
    fraction_of_cpus = 1

    agents = [
        CPA.Construction_Paper_Agent(decomposition_function=CPA.random_1_4,lower_agent=BFS_Agent(only_improving_actions = True,horizon = 2))
        ]

    silhouette8 = [14,11,3,13,12,1,15,5]
    silhouettes = {i : bl.load_interesting_structure(i) for i in silhouette8}
    worlds_silhouettes_all = {'int_struct_'+str(i) : bw.Blockworld(silhouette=s,block_library=bl.bl_silhouette2_default,legal_action_space=False) for i,s in silhouettes.items()}
    worlds_small = {
        'stonehenge_6_4' : bw.Blockworld(silhouette=bl.stonehenge_6_4,block_library=bl.bl_stonehenge_6_4),
        'horizontal_tile_stonehenge_6_4' : bw.Blockworld(silhouette=bl.horizontal_tile(bl.stonehenge_6_4),block_library=bl.bl_stonehenge_6_4)
    }
    worlds = {**worlds_silhouettes_all,**worlds_small}

    results = experiment_runner.run_experiment(worlds,agents,2500,20,verbose=False,parallelized=fraction_of_cpus,save='decompositions_increment')
    print(results[['agent','world','world_status']])

    print("Done in %s seconds" % (time.time() - start_time))