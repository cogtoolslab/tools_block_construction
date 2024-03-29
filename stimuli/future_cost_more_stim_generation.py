# # Cost of future subgoals model preference elicitation
#
# This notebook contains the code used to generate the subgoal pairs and data for analysis for the third human study.
#
# In this study, we want to see if people are sensitive to the computational costs of future subgoals.
#
# For each tower, we
# * generate a tree of subgoal decompositions
# * get the preferences over hte first subgoals across planners directly from the tree
#
# Tower generation code is taken from `Future_costs_stim_generation.ipynb`

# ## Setup

# set up imports
import os

__file__ = os.getcwd()
from scoping_simulations.utils.directories import PROJ_DIR

DF_DIR = os.path.join(PROJ_DIR, "results/dataframes")

try:
    import scoping_simulations.stimuli.tower_generator as tower_generator
except:
    import tower_generator

import datetime
import math
import pickle

import numpy as np
import p_tqdm
import pandas as pd
from scipy.stats import sem as sem
from tqdm import tqdm

import scoping_simulations.utils.blockworld_library as bl
from scoping_simulations.model.Best_First_Search_Agent import Best_First_Search_Agent
from scoping_simulations.model.Subgoal_Planning_Agent import Subgoal_Planning_Agent
from scoping_simulations.model.utils.decomposition_functions import *
from scoping_simulations.utils.blockworld import *
from scoping_simulations.utils.blockworld_library import *

SOFTMAX_K = 1
MAX_LENGTH = 3  # maximum length of sequences to consider
LAMBDAS = np.linspace(0.1, 6.0, 100)  # lambdas to marginalize over
# the generation parameters are in the executable section of the file below
# TODO make these parameters rather than hard coded


def get_initial_preferences(world_in):
    world_index, w = world_in

    decomposer = Rectangular_Keyholes(
        sequence_length=MAX_LENGTH,
        necessary_conditions=[
            Area_larger_than(area=1),
            # Area_smaller_than(area=30), # used to be 21
            Mass_smaller_than(area=18),
            No_edge_rows_or_columns(),
        ],
        necessary_sequence_conditions=[
            Complete(),
            No_overlap(),
            Supported(),
        ],
    )

    sga = Subgoal_Planning_Agent(
        lower_agent=Best_First_Search_Agent(), decomposer=decomposer
    )

    sga.set_world(w)

    # sg_tree = sga.get_subgoal_tree(only_solved_sequences=True)

    # print("Generating subgoal tree for world {}".format(world_index))

    _, all_sequences, solved_sequences = sga.plan_subgoals(verbose=False)

    print(
        "Done generating sequences for world {}, found {} solved sequences out of {}".format(
            world_index, len(solved_sequences), len(all_sequences)
        )
    )

    # ## Generate sequences of different length

    # 1. Use the tree to generate sequences of subgoals up to a certain length
    # 2. Calculate V for each sequence from C, reward\
    #     What do we do about `c_weight`?
    # 3. Over all sequences of a length, get list of V's for the first subgoal
    # 4. Use the list of V's to calculate preferences over the first subgoals

    (
        subgoal_preferences,
        subgoal_depth_sequences,
    ) = get_marginalized_subgoal_choice_preferences_over_lambda(
        solved_sequences, LAMBDAS
    )

    print("Got subgoal preferences over lambda for world {}".format(world_index))
    relative_subgoal_preferences = get_relative_subgoal_informativity(
        subgoal_preferences
    )

    print(
        "Got relative subgoal preferences over lambda for world {}".format(world_index)
    )

    # lets put everything into a big dataframe
    initial_subgoals_df = pd.DataFrame.from_dict(subgoal_preferences, orient="index")
    # add in absolute in col names
    initial_subgoals_df.columns = [
        str(col) + "_abs" for col in initial_subgoals_df.columns
    ]
    # add in relative preferences
    relative_subgoals_df = pd.DataFrame.from_dict(
        relative_subgoal_preferences, orient="index"
    )
    # add in relative in col names
    relative_subgoals_df.columns = [
        str(col) + "_rel" for col in relative_subgoals_df.columns
    ]
    # merge
    initial_subgoals_df = pd.merge(
        initial_subgoals_df, relative_subgoals_df, left_index=True, right_index=True
    )
    # add in subgoalts themselves
    # add the current world index
    initial_subgoals_df["world"] = world_index
    # we need to recover them from the solved_sequences
    subgoals = []
    for sequence in solved_sequences:
        if sequence.subgoals[0].name not in subgoals:
            subgoals.append(sequence.subgoals[0])
    # add in according to subgoal name
    subgoals_df = pd.DataFrame.from_dict(
        {subgoal.name: subgoal for subgoal in subgoals},
        orient="index",
        columns=["subgoal"],
    )
    # merge with initial_subgoals_df
    initial_subgoals_df = pd.merge(
        initial_subgoals_df, subgoals_df, left_index=True, right_index=True
    )
    # add in additional subgoal info
    initial_subgoals_df["C"] = initial_subgoals_df["subgoal"].apply(lambda x: x.C)
    initial_subgoals_df["R"] = initial_subgoals_df["subgoal"].apply(lambda x: x.R())

    print("Created dataframes & done for world {}".format(world_index))

    return (
        initial_subgoals_df,
        solved_sequences,
        w,
        world_index,
        subgoal_depth_sequences,
    )


def get_subgoal_choice_preferences(solved_sequences, c_weight=None):
    """Get a dict with choice prefernece for each initial subgoal of the form:
    {subgoal: [preference for the ith depth agent]}
    Set lambda in the agent itself"""
    # generate subsequences
    length_sequences = {}
    for length in list(range(1, MAX_LENGTH + 1)):
        length_sequences[length] = []
        for (
            seq
        ) in (
            solved_sequences
        ):  # needs to be solved sequences to ensure that they're all solvable and result in the full decompositon (make sure the proper flag is set above)
            if len(seq) <= length:
                length_sequences[length].append(seq)
            elif len(seq) > length:
                # generate a truncated sequence
                shortenend_seq = Subgoal_sequence(seq.subgoals[0:length])
                length_sequences[length].append(shortenend_seq)
        # clear out duplicates according to subgoals
        seen = set()
        length_sequences[length] = [
            x
            for x in length_sequences[length]
            if not (x.names() in seen or seen.add(x.names()))
        ]  # I assume that a tuple of the same objects is the same even when recreated

    subgoals = {}
    # get first subgoal V's (as well as other measures for later analysis)
    subgoal_depth_Vs = {}
    subgoal_depth_sequences = (
        {}
    )  # dict with {initial subgoal: {depth: [sequence objects]}}
    for depth in length_sequences:
        subgoal_depth_Vs[depth] = {}
        for seq in length_sequences[depth]:
            V = seq.V(c_weight) if c_weight is not None else seq.V()
            if seq.subgoals[0].name not in subgoal_depth_sequences:
                subgoal_depth_sequences[seq.subgoals[0].name] = {}
            if seq.subgoals[0].name in subgoal_depth_Vs[depth]:
                subgoal_depth_Vs[depth][seq.subgoals[0].name] += [V]
                subgoal_depth_sequences[seq.subgoals[0].name][depth] += [seq]
            else:
                subgoal_depth_Vs[depth][seq.subgoals[0].name] = [V]
                subgoal_depth_sequences[seq.subgoals[0].name][depth] = [seq]
            if seq.subgoals[0].name not in subgoals:
                subgoals[seq.subgoals[0].name] = seq.subgoals[0]

    # get list of preferences for depth per subgoal
    subgoal_preferences = {}
    for subgoal_name in subgoals.keys():
        subgoal_preferences[subgoal_name] = {}
        for depth in length_sequences:
            # get subgoal preference for depth
            # using softmax with K defined above
            total_best_Vs = [max(vs) for vs in subgoal_depth_Vs[depth].values()]
            sg_V = max(subgoal_depth_Vs[depth][subgoal_name])
            try:
                softmax_val = math.exp(SOFTMAX_K * sg_V) / sum(
                    [math.exp(SOFTMAX_K * v) for v in total_best_Vs]
                )
            except ZeroDivisionError:
                softmax_val = 1 if sg_V == max(total_best_Vs) else 0
            subgoal_preferences[subgoal_name][depth] = softmax_val
    return subgoal_preferences, subgoal_depth_sequences


def get_subgoal_choice_preferences_over_lambda(solved_sequences, lambdas):
    """Generates dict with {$\lambda$: {subgoal: [preference for the ith depth agent]}}

    Also returns dict with all sequences of a certain length. Note that this is only returned for a single value of $\lambda$, so be careful with running V() on it.
    """
    subgoal_preferences_over_lambda = {}
    for l in lambdas:
        (
            subgoal_preferences_over_lambda[l],
            subgoal_depth_sequences,
        ) = get_subgoal_choice_preferences(solved_sequences, l)
    return subgoal_preferences_over_lambda, subgoal_depth_sequences


# We'll need to marginalize over lambda


def get_marginalized_subgoal_choice_preferences_over_lambda(solved_sequences, lambdas):
    (
        subgoal_preferences_over_lambda,
        subgoal_depth_sequences,
    ) = get_subgoal_choice_preferences_over_lambda(solved_sequences, lambdas)
    # marginalize over lambda
    subgoal_preferences = {}
    for subgoal_name in subgoal_preferences_over_lambda[lambdas[0]].keys():
        subgoal_preferences[subgoal_name] = {}
        for depth in subgoal_preferences_over_lambda[lambdas[0]][subgoal_name].keys():
            subgoal_preferences[subgoal_name][depth] = np.mean(
                [
                    subgoal_preferences_over_lambda[l][subgoal_name][depth]
                    for l in lambdas
                ]
            )
    return subgoal_preferences, subgoal_depth_sequences


# That gives us the absolute choice preference of the planner. We also want the relative choice preference, which is the ratio in entropy of the distribution over the first subgoals with and without the planner included. The higher the difference, the more the planner is preferred. This indicates the relative to the entropy of the other planners introducing the new one reduces entropy by a certain amount.


def entropy(p):
    try:
        return -sum([p_i * math.log(p_i) for p_i in p])
    except ValueError:
        return 0


def get_relative_subgoal_informativity(subgoal_preferences):
    """Returns dict with {subgoal: informativeness of subgoal}"""
    subgoal_relative_preferences = {}
    for subgoal_name in subgoal_preferences.keys():
        subgoal_relative_preferences[subgoal_name] = {}
        entropy_all = entropy(subgoal_preferences[subgoal_name].values())
        for depth in subgoal_preferences[subgoal_name].keys():
            other_entropy = entropy(
                [
                    subgoal_preferences[subgoal_name][d]
                    for d in subgoal_preferences[subgoal_name].keys()
                    if d != depth
                ]
            )
            try:
                subgoal_relative_preferences[subgoal_name][depth] = (entropy_all) / (
                    other_entropy
                )
            except ZeroDivisionError:
                subgoal_relative_preferences[subgoal_name][depth] = 0
        subgoal_relative_preferences
    return subgoal_relative_preferences


if __name__ == "__main__":
    # used for naming the output file
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Usually we would fix the random seeds here, but the agents are being run with fixed random seeds, so this is not necessary here.

    # show all columns in dataframe
    pd.set_option("display.max_columns", None)

    # ## Generating towers
    #

    block_library = bl_nonoverlapping_simple

    generator = tower_generator.TowerGenerator(
        8,
        8,
        block_library=block_library,
        seed=3,
        padding=(1, 0),
        num_blocks=lambda: random.randint(
            6, 18
        ),  #  flat random interval of tower sizes (inclusive)
    )

    print("Generating towers")
    NUM_TOWERS = 128 * 3
    towers = []
    for i in tqdm(range(NUM_TOWERS)):
        tower = generator.generate()
        towers.append(tower)

    worlds = [
        Blockworld(silhouette=t["bitmap"], block_library=bl.bl_nonoverlapping_simple)
        for t in towers
    ]

    print("Generated {} towers".format(len(worlds)))

    # for generating additional towers beyond the original ones while keeping the same random seed
    CUTOFF = 128
    print("Ignoring first {CUTOFF} towers")
    towers = towers[CUTOFF:]

    initial_subgoals_dfs = []  # store the results

    worlds = zip(range(len(worlds)), worlds)

    # actually run it
    # outs = map(get_initial_preferences, list(worlds)) # for debugging purposes
    outs = p_tqdm.p_umap(get_initial_preferences, list(worlds))
    initial_subgoals_dfs = [out[0] for out in outs]
    solved_sequences = {out[3]: out[1] for out in outs}
    worlds = {out[3]: out[2] for out in outs}
    subgoal_depth_sequencess = {out[3]: out[4] for out in outs}

    print("Done generating initial subgoals, collating dfs...")

    combined_df = pd.concat(initial_subgoals_dfs)

    # save out initial_subgoals_df
    combined_df.to_csv("initial_subgoals_df_" + date + ".csv")
    # also to pickle
    with open("initial_subgoals_df_" + date + ".pkl", "wb") as f:
        pickle.dump(combined_df, f)
    # save the sequences organized by subgoal and depth
    with open("subgoal_depth_sequences_" + date + ".pkl", "wb") as f:
        pickle.dump(subgoal_depth_sequencess, f)
    # save the solved sequences
    with open("solved_sequences_" + date + ".pkl", "wb") as f:
        pickle.dump(solved_sequences, f)
    # save the worlds
    with open("worlds_" + date + ".pkl", "wb") as f:
        pickle.dump(worlds, f)

    print(
        "Saved to {} and corresponding files".format(
            "initial_subgoals_df_" + date + ".csv"
        )
    )
