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
from scoping_simulations.utils.directories import DF_DIR

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

### Parameters ###
# TODO make these parameters rather than hard coded
SOFTMAX_K = 1
MAX_LENGTH = 3  # maximum length of sequences to consider
LAMBDAS = np.linspace(0.1, 10.0, 100)  # lambdas to marginalize over
MIN_SUBGOAL_SIZE = 4  # minimum size of subgoal to consider
MAX_SUBGOAL_MASS = 20  # maximum mass of subgoal to consider
N_COST_SAMPLES = 5  # number of samples for lower agent cost
NUM_TOWERS = 128*4  # number of towers to generate # OG 128 * 2
MIN_WORLD_SIZE = 8  # minimum number of blocks in a tower OG: 8
MAX_WORLD_SIZE = 16  # maximum number of blocks in a tower OG: 16
TIMEOUT_WORLD = 60 * 60 * 12  # timeout for each world in seconds


def get_initial_preferences(world_in):
    world_index, w = world_in

    decomposer = Rectangular_Keyholes(
        sequence_length=MAX_LENGTH,
        necessary_conditions=[
            Area_larger_than(MIN_SUBGOAL_SIZE),
            # Area_smaller_than(area=30), # used to be 21
            Mass_smaller_than(MAX_SUBGOAL_MASS),
            No_edge_rows_or_columns(),
        ],
        necessary_sequence_conditions=[
            Complete(),
            No_overlap(),
            Supported(),
        ],
    )

    sga = Subgoal_Planning_Agent(
        lower_agent=Best_First_Search_Agent(),
        decomposer=decomposer,
        n_samples=N_COST_SAMPLES,
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

    subgoal_depth_sequences, initial_subgoals_df = parse_solved_sequences(
        world_index, solved_sequences
    )
    
    return (
        initial_subgoals_df,
        solved_sequences,
        w,
        world_index,
        subgoal_depth_sequences,
    )


def parse_solved_sequences(world_index, solved_sequences, lambdas=LAMBDAS):
    """Generate sequences of different length

    1. Use the tree to generate sequences of subgoals up to a certain length
    2. Calculate V for each sequence from C, reward\
        What do we do about `c_weight`?
    3. Over all sequences of a length, get list of V's for the first subgoal
    4. Use the list of V's to calculate preferences over the first subgoals"""
    (
        subgoal_preferences,
        subgoal_depth_sequences,
    ) = get_marginalized_subgoal_choice_preferences_over_lambda(
        solved_sequences, lambdas
    )

    relative_subgoal_preferences = get_relative_subgoal_informativity(
        subgoal_preferences
    )

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
    return subgoal_depth_sequences, initial_subgoals_df


def get_initial_preferences_w_timeout(world_in, timeout=TIMEOUT_WORLD):
    """Same as get_initial_preferences but with a timeout so it can be called by p_tqdm pathos multiprocessing"""
    import signal

    def handler(signum, frame):
        print("Timeout in get_initial_preferences occured")
        raise Exception("Timeout!")

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)

    try:
        return get_initial_preferences(world_in)
    except Exception as e:
        print("Exception:", e)
        return None


def get_subgoal_choice_preferences(
    solved_sequences, c_weight=None, how="softmax_weighted"
):
    """Get a dict with choice prefernece for each initial subgoal of the form:
    {subgoal: [preference for the ith depth agent]}
    Set lambda in the agent itself

    The choice proportion is the softmax (k=1) of choosing this initial subgoal over all the other initial subgoals. The higher the value, the more preferred the subgoal is.

    Unlike the previous function which only uses the best sequence of subgoals following the past one, this one uses different methods to aggregate over the other sequences that could follow the first one.

    The methods are:
    * a function object: any function that operates on a list of numerical values
    * 'mean': mean of the cost of all sequences
    * 'best': best cost of all sequences (that is the behavior of the previous function)
    * 'median': median of the cost of all sequences
    * 'sum': sum of the cost of all sequences
    * 'count': count of the number of sequences (Ie. we want to maximize the number of sequences that can follow the first one)
    * 'var': the variance of the costs
    * 'top_kp': mean of the top k% of the sequences
    * 'top_kc': mean of the top k sequences
    * softmax_weighted(_k): the value of each sequence is weigthed according to their softmax, meaning that the better the sequence the more it counts. By default, k is 1.
    """
    # print("Computing subgoal preferences over all sequences using", how)
    # generate subsequences
    length_sequences = {}
    for length in list(range(1, MAX_LENGTH + 1)):
        matched_sequences = []
        for (
            seq
        ) in (
            solved_sequences
        ):  # needs to be solved sequences to ensure that they're all solvable and result in the full decompositon (make sure the proper flag is set above)
            if len(seq) <= length:
                matched_sequences.append(seq)
            elif len(seq) > length:
                # generate a truncated sequence
                shortenend_seq = Subgoal_sequence(seq.subgoals[0:length])
                matched_sequences.append(shortenend_seq)
        # clear out duplicates according to subgoals
        unique_length_sequences = []
        seen = set()
        for seq in matched_sequences:
            # have we seen this sequence before?
            if str(seq.names()) in seen:
                continue
            # we haven't seen this
            seen.add(str(seq.names()))
            unique_length_sequences.append(seq)
        length_sequences[length] = unique_length_sequences

    subgoals = {}
    # get first subgoal V's (as well as other measures for later analysis)
    subgoal_depth_Vs = {}
    subgoal_depth_sequences = (
        {}
    )  # dict with {initial subgoal: {depth: [sequence objects]}}
    for depth in length_sequences:
        subgoal_depth_Vs[depth] = {}
        for seq in length_sequences[depth]:
            V = (
                seq.V(c_weight, log_C=True)
                if c_weight is not None
                else seq.V(log_C=True)
            )
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
    # this is the only part that changes from the previous function
    subgoal_preferences = {}
    subgoal_Vs = {}
    for subgoal_name in subgoals.keys():
        subgoal_preferences[subgoal_name] = {}
        subgoal_Vs[subgoal_name] = {}
        for depth in length_sequences:
            if callable(how):
                other_Vs = [how(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = how(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "mean":
                other_Vs = [np.mean(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = np.mean(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "best":
                other_Vs = [max(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = max(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "median":
                other_Vs = [np.median(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = np.median(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "sum":
                other_Vs = [sum(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = sum(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "count":
                other_Vs = [len(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = len(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "var":
                other_Vs = [np.var(vs) for vs in subgoal_depth_Vs[depth].values()]
                sg_V = np.var(subgoal_depth_Vs[depth][subgoal_name])
            elif how == "softmax_weighted":
                other_Vs = [
                    np.sum(softmax(vs) * np.array(vs))
                    for vs in subgoal_depth_Vs[depth].values()
                ]
                sg_V = np.sum(
                    softmax(subgoal_depth_Vs[depth][subgoal_name])
                    * np.array(subgoal_depth_Vs[depth][subgoal_name])
                )
            elif how.startswith("softmax_weighted_"):
                # we want to change the softmax k
                try:
                    k = float(how.removeprefix("softmax_weighted_"))
                except:
                    raise Exception(
                        f"The how method must contain a float, but instead was {how}"
                    )
                other_Vs = [
                    np.sum(softmax(vs, k) * np.array(vs))
                    for vs in subgoal_depth_Vs[depth].values()
                ]
                sg_V = np.sum(
                    softmax(subgoal_depth_Vs[depth][subgoal_name], k)
                    * np.array(object=subgoal_depth_Vs[depth][subgoal_name])
                )
            elif how.startswith("top_") and how.endswith("p"):
                # we want the top p percent of elements
                try:
                    k = int(how.removeprefix("top_").removesuffix("p"))
                except:
                    raise Exception(
                        f"The how method must contain an integer, but instead was {how}"
                    )
                k = float(k / 100.0)
                other_Vs = [
                    np.mean(sorted(vs, reverse=True)[0 : int(len(vs) * k)])
                    for vs in subgoal_depth_Vs[depth].values()
                ]
                sg_V = np.mean(
                    sorted(subgoal_depth_Vs[depth][subgoal_name], reverse=True)[
                        0 : int(len(subgoal_depth_Vs[depth][subgoal_name]) * k)
                    ]
                )
            elif how.startswith("top_") and how.endswith("c"):
                # we want the top k elements
                try:
                    k = int(how.removeprefix("top_").removesuffix("c"))
                except:
                    raise Exception(
                        f"The how method must contain an integer, but instead was {how}"
                    )
                other_Vs = [
                    np.mean(sorted(vs, reverse=True)[0:k])
                    for vs in subgoal_depth_Vs[depth].values()
                ]
                sg_V = np.mean(
                    sorted(subgoal_depth_Vs[depth][subgoal_name], reverse=True)[0:k]
                )
            else:
                raise Exception(f"How method '{how}' is not implemented.")
            # we calculate the softmax of the initial subgoal over all the other values to get at its relative preference
            try:
                softmax_val = math.exp(SOFTMAX_K * sg_V) / sum(
                    [math.exp(SOFTMAX_K * v) for v in other_Vs]
                )
            except ZeroDivisionError:
                softmax_val = 1 if sg_V == max(other_Vs) else 0
            except OverflowError:
                # Fallback in case of numerical instability
                max_val = max(sg_V, max(other_Vs))
                if max_val == sg_V:
                    softmax_val = 1.0
                else:
                    softmax_val = 0.0
            subgoal_preferences[subgoal_name][depth] = softmax_val
            subgoal_Vs[subgoal_name][depth] = sg_V
    return subgoal_preferences, subgoal_depth_sequences


def get_subgoal_choice_preferences_over_lambda(solved_sequences, lambdas):
    """Generates dict with {lambda: {subgoal: [preference for the ith depth agent]}}

    Also returns dict with all sequences of a certain length. Note that this is only returned for a single value of lambda, so be careful with running V() on it.
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


def entropy(p):
    try:
        return -sum([p_i * math.log(p_i) for p_i in p])
    except ValueError:
        return 0


def softmax(x, k=1):
    """Compute softmax values for each set of scores in x."""
    x = np.array(x)
    e_x = np.exp(k * x - np.max(k * x, axis=0))
    return e_x / e_x.sum(axis=0)


def get_relative_subgoal_informativity(subgoal_preferences):
    # That gives us the absolute choice preference of the planner. We also want the relative choice preference, which is the ratio in entropy of the distribution over the first subgoals with and without the planner included. The higher the difference, the more the planner is preferred. This indicates the relative to the entropy of the other planners introducing the new one reduces entropy by a certain amount.
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

    block_library = bl_nonoverlapping_simple

    generator = tower_generator.TowerGenerator(
        8,
        8,
        block_library=block_library,
        seed=3,
        padding=(1, 0),
        num_blocks=lambda: random.randint(
            MIN_WORLD_SIZE, MAX_WORLD_SIZE
        ),  #  flat random interval of tower sizes (inclusive)
    )

    print("Generating towers")
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
    # CUTOFF = 0
    # print("Ignoring first {CUTOFF} towers")
    # towers = towers[CUTOFF:]

    initial_subgoals_dfs = []  # store the results

    worlds = zip(range(len(worlds)), worlds)

    # actually run it
    # outs = list(map(get_initial_preferences_w_timeout, list(worlds))) # for debugging purposes
    outs = p_tqdm.p_umap(get_initial_preferences_w_timeout, list(worlds))
    initial_subgoals_dfs = [out[0] for out in outs if out is not None]
    solved_sequences = {out[3]: out[1] for out in outs if out is not None}
    worlds = {out[3]: out[2] for out in outs if out is not None}
    subgoal_depth_sequencess = {out[3]: out[4] for out in outs if out is not None}

    print("Done generating initial subgoals, collating dfs...")

    path = DF_DIR / "future_cost_stimuli" / date

    combined_df = pd.concat(initial_subgoals_dfs)

    # save out initial_subgoals_df
    combined_df.to_csv(path / "initial_subgoals_df_" + date + ".csv")
    # also to pickle
    with open("initial_subgoals_df_" + date + ".pkl", "wb") as f:
        pickle.dump(combined_df, f)
    # save the sequences organized by subgoal and depth
    with open(path / "subgoal_depth_sequences_" + date + ".pkl", "wb") as f:
        pickle.dump(subgoal_depth_sequencess, f)
    # save the solved sequences
    with open(path / "solved_sequences_" + date + ".pkl", "wb") as f:
        pickle.dump(solved_sequences, f)
    # save the worlds
    with open(path / "worlds_" + date + ".pkl", "wb") as f:
        pickle.dump(worlds, f)

    # save out the parameters
    with open(path / "parameters_" + date + ".txt", "w") as f:
        f.write("SOFTMAX_K = {}\n".format(SOFTMAX_K))
        f.write("MAX_LENGTH = {}\n".format(MAX_LENGTH))
        f.write("LAMBDAS = {}\n".format(LAMBDAS))
        f.write("MIN_SUBGOAL_SIZE = {}\n".format(MIN_SUBGOAL_SIZE))
        f.write("MAX_SUBGOAL_MASS = {}\n".format(MAX_SUBGOAL_MASS))
        f.write("N_COST_SAMPLES = {}\n".format(N_COST_SAMPLES))
        f.write("NUM_TOWERS = {}\n".format(NUM_TOWERS))
        f.write("MIN_WORLD_SIZE = {}\n".format(MIN_WORLD_SIZE))
        f.write("MAX_WORLD_SIZE = {}\n".format(MAX_WORLD_SIZE))
        f.write("TIMEOUT_WORLD = {}\n".format(TIMEOUT_WORLD))

    print(
        "Saved to {}".format(
            path.absolute()
        )
    )
