import copy
import datetime
import multiprocessing
import os
import random
import time
import traceback

import numpy as np
import pandas as pd
import psutil
import tqdm

from scoping_simulations.analysis.utils.analysis_helper import preprocess_df
from scoping_simulations.utils.directories import PROJ_DIR

RESULTS_DIR = os.path.join(PROJ_DIR, "results")
DF_DIR = os.path.join(RESULTS_DIR, "dataframes")


"""
# Meaning of columns in dataframe:
A row corresponds to an individual action taken, ie. a single block placed.
# every action
'run_ID': unique ID for that run (very long)
'agent': type of agent as string
'world': name of world as string
'step': index of action taken. Starts at 0
'planning_step': index of planning step. Starts at 0
'states_evaluated': in the process of planning, how often was a state evaluated? A proxy for how expensive planning is
'action': action as human readable string (['(width x height)', 'x location'])
'_action': action as object (for analysis)
'action_x': x coordinate of block placed
'action_block_width': width of block placed
'action_block_height: height of block placed
'blocks': blocks in world as human readable string ("width, height at x,y")
'_blocks': blocks as objects (for analysis)
'blockmap': bitmap of the world at the current state
various agent parameters (depends on agent loaded)
# only at planning step
'_world': current state of the world as object (for analysis). State is only updated at each planning step.
'legal_action_space': if true, only legal (in silhouette, not necessarily stable) actions are considered
'fast_failure': if true, the trial is ended when it is clear it can't lead to a perfect reconstruction.
'_blocks': current list of blocks in the world as object (for analysis)
'execution_time': computation time of the planning step in seconds
'world_status': either fail, ongoing, winning
'world_failure_reason': if world_status is fail, then the reason is given here
'agent_attributes': the attributes of the agent as dictionary. Allow for easy grouping of agents across runs. Does not include random seed.
**agent attributes unrolled** as provided by the class of agent. Includes random_seed.
"""

DF_COLS = [
    "run_ID",
    "agent",
    "world",
    "step",
    "planning_step",
    "states_evaluated",
    "action",
    "_action",
    "action_x",
    "action_block_width",
    "action_block_height",
    "blocks",
    "_blocks",
    "blockmap",
    "_world",
    "legal_action_space",
    "fast_failure",
    "execution_time",
    "world_status",
    "world_failure_reason",
    "agent_attributes",
]
RAM_LIMIT = 100  # percentage of RAM usage over which a process doesn't run as to not run out of memory


def run_experiment(
    worlds,
    agents,
    per_exp=100,
    steps=40,
    verbose=False,
    save=True,
    parallelized=True,
    maxtasksperprocess=1,
):
    """Runs x experiments on the given worlds with the given agents for up to 100 steps while keeping logging values to a dataframe. Pass blockworlds as named dictionary for readability of results. Pass agents as a list: the __str__ function of an agent will take care of it. The world is assigned to the agent later, so it makes sense to pass none. You can pass negative numbers steps to run until the agent is finished. Pass a float to parallelized to set the fraction of CPUs to use. Note that the system that reads in the dataframe needs identical or compatible versions of Python and it's modules for it to be able to read the dataframe back in again. Hint: `pip freeze > requirements.txt`"""
    # we want human readable labels for the dataframe
    if type(worlds) is not dict:
        # if worlds is list create dictionary
        worlds = {w.__str__(): w for w in worlds}
    if type(agents) is dict:
        # if agents is dict flatten it and rely on informative agent __str__
        agents = [a for a in agents.values()]

    # we need to copy the world and agent to reset them
    # create a list of experiments to run
    experiments = [
        (copy.deepcopy(w), copy.deepcopy(a), steps, verbose, i)
        for i in range(per_exp)
        for a in agents
        for w in worlds.items()
    ]
    # lets run the experiments
    if parallelized is not False:
        # restart process after a single task is performed—slow for short runs, but fixes memory leak (hopefully)
        P = multiprocessing.Pool(
            int(multiprocessing.cpu_count() * parallelized),
            maxtasksperchild=maxtasksperprocess,
        )
        results_mapped = tqdm.tqdm(
            P.imap_unordered(_run_single_experiment, experiments),
            total=len(experiments),
        )
        P.close()
    else:
        results_mapped = list(map(_run_single_experiment, experiments))

    results = pd.concat(results_mapped).reset_index(drop=True)

    preprocess_df(results)  # automatically fill in code relevant to analysis

    if save is not False:
        # check if results directory exists
        if not os.path.isdir(DF_DIR):
            os.makedirs(DF_DIR)
        # save the results to a file.
        if type(save) is str:
            results.to_pickle(os.path.join(DF_DIR, save + ".pkl"))
            print("Saved to", os.path.join(DF_DIR, save + ".pkl"))
        else:
            results.to_pickle(
                os.path.join(
                    DF_DIR, "Experiment " + str(datetime.datetime.today()) + ".pkl"
                )
            )
            print(
                "Saved to",
                DF_DIR,
                "Experiment " + str(datetime.datetime.today()) + ".pkl",
            )

        # lets also save it as a csv without embedded objects
        columns = [col for col in results.columns if col[0] != "_"]
        results_wo_objects = results[columns]
        # save the results to a file.
        if type(save) is str:
            results_wo_objects.to_csv(os.path.join(DF_DIR, save + ".csv"))
            print("Saved to", os.path.join(DF_DIR, save + ".csv"))
        else:
            results_wo_objects.to_csv(
                os.path.join(
                    DF_DIR, "Experiment " + str(datetime.datetime.today()) + ".csv"
                )
            )
            print(
                "Saved to",
                DF_DIR,
                "Experiment " + str(datetime.datetime.today()) + ".csv",
            )

    return results


def _run_single_experiment(experiment):
    """Runs a single experiment. Returns complete dataframe with an entry for each action."""
    world_dict, agent, steps, verbose, run_nr = experiment
    world_label = world_dict[0]
    world = world_dict[1]
    # if the agent has no random seed assigned yet, assign one now only for this run
    try:
        if agent.random_seed is None:
            agent.random_seed = random.randint(0, 99999)
        else:
            # we increment the random seed with the run number to ensure different behavior between runs
            agent.random_seed += run_nr
    except AttributeError:
        pass
    run_ID = (
        world_label
        + " | "
        + agent.__str__()
        + str(run_nr)
        + " | "
        + str(random.randint(0, 9999))
    )  # unique string representing the run
    sleep = 100
    while psutil.virtual_memory().percent > RAM_LIMIT:
        print(
            "Delaying running",
            agent.__str__(),
            "******",
            world_label,
            f"because of RAM usage. Trying again in {sleep} seconds. RAM usage is "
            + str(psutil.virtual_memory().percent)
            + "%",
        )
        time.sleep(sleep)
        # exponential backoff
        sleep = sleep * 200

    # print('Running', agent.__str__(), '******', world.__str__())
    agent_parameters = agent.get_parameters()
    agent_parameters_w_o_random_seed = {
        key: value for key, value in agent_parameters.items() if key != "random_seed"
    }
    agent_parameters_w_o_random_seed = agent_para_dict(agent_parameters_w_o_random_seed)
    agent.set_world(world)
    # create dataframe
    r = pd.DataFrame(
        columns=DF_COLS + list(agent_parameters.keys()), index=range(steps + 1)
    )
    i = 0  # the ith action taken
    planning_step = 0
    while i != steps and planning_step != steps and world.status()[0] == "Ongoing":
        # execute the action
        try:
            start_time = time.perf_counter()
            chosen_actions, agent_step_info = agent.act(verbose=verbose)
            duration = time.perf_counter() - start_time
            planning_step += 1
        except SystemError as e:
            print("Error while acting:", e)
            print(traceback.format_exc())
        # unroll the chosen actions to get step-by-step entries in the dataframe
        planning_step_blockmaps = get_blockmaps(
            world.current_state.blockmap
        )  # the blockmap for every step
        for ai, action in enumerate(chosen_actions):
            if ai > steps:
                Warning(
                    "Number of actions ({}) exceeding steps ({}).".format(ai, steps)
                )
                break
            insert_into_run_df(
                world_label,
                world,
                run_ID,
                agent_parameters,
                agent_parameters_w_o_random_seed,
                r,
                i,
                planning_step,
                planning_step_blockmaps,
                action,
            )
            i += 1
        # the following are only filled for each planning step, not action step
        if len(chosen_actions) == 0:
            # we couldn't find any actions
            # we also need to fill the boiler plate for the dataframe
            i += 1  # since we didnt increment the counter above
            # insert planning step info
            insert_into_run_df(
                world_label,
                world,
                run_ID,
                agent_parameters,
                agent_parameters_w_o_random_seed,
                r,
                i,
                planning_step,
                planning_step_blockmaps,
                action=None,
            )
            i += 1  # for the following code. NOTE better check whether that truly makes sense
        r.at[i - 1, "execution_time"] = duration
        world_status = world.status()
        r.at[i - 1, "world_status"] = world_status[0]
        r.at[i - 1, "world_failure_reason"] = world_status[1]
        # if we have it, unroll the miscellaneous output from agent
        # should include `states_evaluated`
        for key, value in agent_step_info.items():
            try:
                r[key]
            except KeyError:
                # we need to create column
                r[key] = np.NaN
            try:
                r.at[i - 1, key] = value
            except (
                ValueError
            ):  # happens when the datatype of the columns is inferred as numeric
                r[key] = r[key].astype(object)
                r.at[i - 1, key] = [value]
        # if we've observed no action being taken, we stop execution. We're not changing the world, so we might as well save the CPU cycles.
        # Take this out if we have a non-deterministic agent that sometimes chooses no actions.
        if chosen_actions == []:
            break

    # after we stop acting
    # print("Done with", agent.__str__(), '******', world_label, "in %s seconds with outcome " %
    #   round((time.perf_counter() - start_time)), str(world_status))
    # truncate df and return
    return r[r["run_ID"].notnull()]


def insert_into_run_df(
    world_label,
    world,
    run_ID,
    agent_parameters,
    agent_parameters_w_o_random_seed,
    r,
    i,
    planning_step,
    planning_step_blockmaps,
    action=None,
):
    # adding the agent parameters
    for key, value in agent_parameters.items():
        r.at[i, key] = value
    r.at[i, "run_ID"] = run_ID
    r.at[i, "agent"] = agent_parameters["agent_type"]
    r.at[i, "agent_attributes"] = str(agent_parameters_w_o_random_seed)
    r.at[i, "world"] = world_label
    r.at[i, "step"] = i
    r.at[i, "planning_step"] = planning_step
    # human readable blocks
    r.at[i, "blocks"] = [
        block.__str__() for block in world.current_state.blocks[: i + 1]
    ]
    r.at[i, "_blocks"] = world.current_state.blocks[: i + 1]
    try:
        r.at[i, "blockmap"] = planning_step_blockmaps[i]
    except IndexError:
        pass
    r.at[i, "_world"] = world
    r.at[i, "legal_action_space"] = world.legal_action_space
    r.at[i, "fast_failure"] = world.fast_failure
    r.at[i, "physics"] = world.physics
    # fill action
    if action is not None:
        r.at[i, "action"] = [str(e) for e in action]  # human readable action
        r.at[i, "_action"] = action  # action as object
        r.at[i, "action_x"] = action[1]
        r.at[i, "action_block_width"] = action[0].width
        r.at[i, "action_block_height"] = action[0].height


def get_blockmaps(blockmap):
    """Takes a blockmap as input and returns the sequence of blockmaps leading up to it.
    This produces one blockmap per action taken, even if the act function has only been called once
    (as MCTS does)."""
    blockmaps = []
    # maybe it's wrapped in a list
    if len(blockmap) == 1:
        blockmap = blockmap[0]
    blockmap = np.array(blockmap)
    # generate sequence of blockmaps
    for i in range(np.max(blockmap) + 1):  # for every placed block
        bm = blockmap * (blockmap <= i + 1)
        blockmaps.append(bm)
    return blockmaps


class agent_para_dict(dict):
    """A class for hashable dicts for agent parameters. Derives from a regular dictionary.
    ENTRIES MUST NOT BE CHANGED AFTER CREATION"""

    def __key(self):
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()
