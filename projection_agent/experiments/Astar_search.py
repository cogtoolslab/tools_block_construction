if __name__=="__main__": #required for multiprocessing
    #add the parent path to import the modules
    from inspect import getsourcefile
    import os.path
    import sys
    current_path = os.path.abspath(getsourcefile(lambda:0))
    current_dir = os.path.dirname(current_path)
    parent_dir = current_dir[:current_dir.rfind(os.path.sep)]
    sys.path.insert(0, parent_dir)

    from Astar_Agent import Astar_Agent
    import blockworld as bw
    import random
    import blockworld_library as bl
    import experiment_runner
    import time
    start_time = time.time()

    #16 for nightingale
    fraction_of_cpus = 1


    agents = [Astar_Agent(),Astar_Agent(heuristic=bw.F1score)]

    silhouette8 = [14,11,3,13,12,1,15,5]
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

    results = experiment_runner.run_experiment(worlds,agents,100,40,verbose=False,parallelized=fraction_of_cpus,save='Astar_search')
    print(results[['agent','world','outcome']])

    print("Done in %s seconds" % (time.time() - start_time))