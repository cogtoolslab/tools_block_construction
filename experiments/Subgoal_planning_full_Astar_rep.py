if __name__ == "__main__":  # required for multiprocessing
    import time

    import scoping_simulations.experiments.subgoal_generator_runner as experiment_runner
    import scoping_simulations.utils.blockworld as bw
    import scoping_simulations.utils.blockworld_library as bl
    from scoping_simulations.model.Astar_Agent import Astar_Agent
    from scoping_simulations.model.Subgoal_Planning_Agent import *
    from scoping_simulations.model.utils.decomposition_functions import *

    start_time = time.time()

    print("Running experiment....")

    fraction_of_cpus = 1

    # 10000 is very roughly the budget of BFS3
    agents = [
        Subgoal_Planning_Agent(
            lower_agent=Astar_Agent(
                max_steps=16384, heuristic=bw.F1score, only_improving_actions=True
            ),
            sequence_length=8,
            include_subsequences=True,
            c_weight=1,
            max_cost=10**3,  # low number here means one try, one opportunity
            step_size=0,
        )
    ]

    silhouettes = {i: bl.load_interesting_structure(i) for i in bl.SILHOUETTE16}
    worlds = {
        "int_struct_"
        + str(i): bw.Blockworld(
            silhouette=s,
            block_library=bl.bl_silhouette2_default,
            legal_action_space=True,
            physics=False,
        )
        for i, s in silhouettes.items()
    }

    results = experiment_runner.run_experiment(
        worlds,
        agents,
        1,
        1,
        verbose=False,
        parallelized=fraction_of_cpus,
        save="subgoal planning full Astar classic",
        maxtasksperprocess=1,
    )

    print("Done in %s seconds" % (time.time() - start_time))
