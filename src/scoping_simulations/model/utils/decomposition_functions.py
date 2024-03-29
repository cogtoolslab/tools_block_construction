"""This file contains decomposition functions as objects. The decompositions can additionally include a state object that the agent keeps track of and returns for the next decomposition (ie location of the construction paper for increments)."""

import copy
import itertools
import math
import random

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage
from tqdm import tqdm

SUBGOAL_COLORS = [
    "red",
    "green",
    "blue",
    "yellow",
    "orange",
    "purple",
    "pink",
    "cyan",
    "brown",
    "black",
    "white",
]


class Subgoal:
    """Stores a subgoal.

    Bitmap stores a boolean bitmap of the target including blank areas (ie. is 1 for the full rectangle), while target just stores the decomposed silhouette with 0 for both background and out-of-subgoal areas.
    """

    def __init__(
        self,
        source,
        target,
        bitmap=None,
        name=None,
        actions=None,
        C=None,
        prior_world=None,
        past_world=None,
        solution_cost=None,
        planning_cost=None,
    ):
        self.source = source
        self.target = copy.deepcopy(target)  # aka decomposition
        if bitmap is not None:
            self.bitmap = bitmap
        else:
            self.bitmap = self.target
        self.name = name
        self.actions = actions
        self.C = C
        self.prior_world = copy.deepcopy(prior_world)
        self.past_world = copy.deepcopy(past_world)
        self.solution_cost = solution_cost
        self.planning_cost = planning_cost

    def key(self):
        key = self.target * 100 - (
            self.prior_world.current_state.order_invariant_blockmap() > 0
        )
        return key.tostring()  # make hashable

    def R(self):
        try:
            return np.sum(
                (self.past_world.current_state.blockmap > 0) * 1.0
                - (self.prior_world.current_state.blockmap > 0) * 1.0
            )
        except AttributeError:
            # if we can't solve it (or haven't yet), we return a reward of 0
            return 0

    def get_current_target(self):
        """Returns the current target of the subgoal, ie. the target minus the previous target.
        This is useful if the subgoal includes the previous subgoals within it."""
        return (self.target > 0.5) & ~(self.prior_world.current_state.blockmap > 0.5)

    def visualize(self, title=None, ax=None, show_blocks=True, block_color="orange"):
        """Make a pretty visualization of the subgoal state.
        Set up in a flexible way to ensure that I can reuse the code for various purposes (ie. analysis step by step). Pass it a figure to have this function add a subplot to it.
        """
        # pull out the relevant objects
        blocks = self.past_world.current_state.blocks
        full_silhouette = self.past_world.full_silhouette
        subgoal_bitmap = self.bitmap
        # create figure
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            draw = True
        else:
            draw = False
        # add subtle gridlines
        # plot the current blocks
        if show_blocks:
            for i, block in enumerate(blocks):
                # plot rectangle
                ax.add_patch(
                    plt.Rectangle(
                        (block.x - 0.5, block.y - block.height + 0.5),
                        block.width,
                        block.height,
                        facecolor=block_color,
                        linewidth=3,
                        edgecolor="black",
                        label=i + 1,
                        alpha=1,
                        zorder=5,
                    )
                )
                # add text labels in the middle of the blocks
                ax.text(
                    block.x, block.y, str(i + 1), fontsize=15, color="grey", zorder=6
                )
        # plot the full silhouette
        ax.imshow(np.invert(full_silhouette > 0), cmap="gray", alpha=0.2, zorder=1)
        # plt.imshow(self.past_world.current_state.blockmap, cmap='pink_r', alpha=0.4)
        # plot the subgoal silhouette as a gray overlay
        ax.imshow(
            np.ones(subgoal_bitmap.shape),
            cmap="gray",
            alpha=np.invert(subgoal_bitmap > 0) * 0.5,
            zorder=10,
        )
        if title:
            ax.set_title(title)
        # remove ticks and frame
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        # show the figure
        if draw:
            plt.show()
        return ax


class Subgoal_sequence:
    """Stores a sequence."""

    def __init__(self, sequence, prior_world=None):
        """Generate sequence from dict input from decomposition function"""
        self.subgoals = []
        self.score = None
        self.prior_world = copy.deepcopy(prior_world)
        last_source = None
        for d in sequence:
            try:
                # assuming we get a sequence from the decomposition function
                subgoal = Subgoal(
                    source=last_source,
                    target=d["decomposition"],
                    name=d["name"],
                    bitmap=d["bitmap"],
                )
                last_source = d["decomposition"]
            except TypeError:
                # if not, then we've gotten some other object
                if type(d).__name__ == "Subgoal":
                    subgoal = d
                elif type(d).__name__ == "SubgoalTreeNode":
                    subgoal = d.subgoal
                else:
                    raise TypeError(
                        "Pass either dict, existing subgoal or subgoal tree node as element in sequence"
                    )
            self.subgoals.append(subgoal)

    def names(self):
        return tuple([sg.name for sg in self.subgoals])

    def actions(self):
        actions = []
        for sg in self.subgoals:
            try:
                actions += sg.actions
            except:  # we don't have any actions (if its unsolvable,...)
                pass
        return actions

    def planning_cost(self):
        """Planning cost of the entire sequence"""
        return sum(
            [
                sg.planning_cost if sg.planning_cost is not None else 0
                for sg in self.subgoals
            ]
        )  # could be max cost as well

    def solution_cost(self):
        """Planning cost of the entire sequence"""
        return sum(
            [
                sg.solution_cost if sg.solution_cost is not None else 0
                for sg in self.subgoals
            ]
        )  # could be max cost as well

    def complete(self):
        """Do we have a solution for all goals in the sequence?"""
        return np.all(
            [s.actions is not None and s.actions != [] for s in self.subgoals]
        )

    def fully_covering(self):
        """Would completing the sequence lead to the entire target being covered?"""
        try:
            common_target = self.subgoals[0].target
        except IndexError:
            # we don't even have a single subgoal
            return False
        for sg in self.subgoals[1:]:
            common_target = np.logical_or(common_target, sg.target)
        silhouette = self.prior_world.full_silhouette == 1
        return np.all(np.equal(common_target, silhouette))

    def V(self, c_weight=1, log_C=False):
        """Adds up the cost and rewards of the subgoals.
        Optionally, pass a weight for the cost (default 1)
        Optionally, pass a flag to log the cost (default False)
        """
        try:
            if not log_C:
                score = sum(
                    [
                        sg.R() - sg.C * c_weight
                        if sg.C is not None
                        else None  # if we havent scores the cost yet, it's 0, but there should be an unreachable penalty somewhere leading up
                        for sg in self.subgoals
                    ]
                )
            else:
                score = sum(
                    [
                        sg.R() - np.log(sg.C) * c_weight
                        if sg.C is not None
                        else None  # if we havent scores the cost yet, it's 0, but there should be an unreachable penalty somewhere leading up
                        for sg in self.subgoals
                    ]
                )
        except TypeError:
            # if we can't solve it (or haven't yet) (-> we observe a cost of none), we return a reward of None
            score = None
        return score

    def R(self):
        """Cumulative reward of subgoals"""
        score = sum([sg.R() for sg in self.subgoals])
        return score

    def C(self):
        """Cumulative cost of subgoals"""
        score = sum([sg.C for sg in self.subgoals])
        return score

    def visual_display(self, blocking=True, title=None):
        """Displays the sequence visually. See also Blockworld.State.visual_display()"""
        plt.close("all")
        plt.figure(figsize=(4, 4))
        try:
            # get silhouette
            silhouette = self.prior_world.silhouette
            # plot existing blocks
            plt.pcolor(
                self.prior_world.current_state.blockmap[::-1],
                cmap="hot_r",
                vmin=0,
                vmax=20,
                linewidth=0,
                edgecolor="none",
            )
            # we print the target silhouette as transparent overlay
            plt.pcolor(
                silhouette[::-1],
                cmap="binary",
                alpha=0.8,
                linewidth=2.5,
                facecolor="grey",
                edgecolor="grey",
                capstyle="round",
                joinstyle="round",
                linestyle=":",
            )
        except AttributeError:
            # no prior world.
            silhouette = np.zeros(self.subgoals[0].bitmap.shape)
        # draw subgoals
        for i, sg in enumerate(self.subgoals):
            # get body of mass for subgoal
            y, x = ndimage.measurements.center_of_mass(sg.bitmap)
            if sg.bitmap is not None:
                # create binary colormap
                cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
                    "",
                    [
                        (0.0, 0.0, 0.0, 0.0),
                        matplotlib.colors.to_rgba(SUBGOAL_COLORS[i], alpha=0.33),
                    ],
                )
                # plot subgoal
                plt.pcolor(
                    sg.bitmap[::-1] > 0,
                    cmap=cmap,
                    linewidth=0.75,
                    facecolor=SUBGOAL_COLORS[i],
                    edgecolor="none",
                )
            plt.text(
                x,
                silhouette.shape[0] - y,
                str(i) + ": " + sg.name,
                fontsize=8,
                color=SUBGOAL_COLORS[i],
                backgroundcolor="black",
                ha="left",
                va="bottom",
                alpha=0.66,
            )
        if title is not None:
            plt.title(title)
        plt.show(block=blocking)

    def __len__(self):
        return len(self.subgoals)

    def __iter__(self):
        self.a = 0
        return self

    def __next__(self):
        try:
            sg = self.subgoals[self.a]
            self.a += 1
            return sg
        except IndexError:
            raise StopIteration


class Decomposition_Function:
    """Decomposition function for a blockworld. See the end of this file for a list of conditions to filter on."""

    def __init__(
        self,
        silhouette=None,
        sequence_length=3,
        necessary_conditions=[],
        necessary_sequence_conditions=[],
    ):
        self.silhouette = silhouette
        self.sequence_length = sequence_length
        self.necessary_conditions = necessary_conditions
        self.necessary_sequence_conditions = necessary_sequence_conditions

    def set_silhouette(self, silhouette):
        self.silhouette = silhouette

    def get_decompositions(self, state=None):
        # if we don't have a silhouette set in the object, add it from the state
        if self.silhouette is None:
            self.silhouette = state.world.full_silhouette
        assert np.all(
            self.silhouette == state.world.full_silhouette
        ), "Silhouette of state and decomposition function don't match"
        decompositions = self.get_all_potential_decompositions()
        decompositions = [
            d for d in decompositions if self.check_necessary_conditions(d, state)
        ]
        return decompositions

    def check_necessary_conditions(self, decomposition, state):
        for condition in self.necessary_conditions:
            if not condition(decomposition, state):
                return False
        return True

    def check_necessary_sequence_conditions(self, sequence, state):
        # special case for empty sequence
        if len(sequence) == 0:
            return False
        for condition in self.necessary_sequence_conditions:
            if not condition(sequence, state):
                return False
        return True

    def get_sequences(
        self, state=None, length=None, number_of_sequences=None, verbose=False
    ):
        """Returns all possible decompositions as a list of Subgoal_sequences"""
        subgoals = self.get_decompositions(state)
        if (
            length is None
        ):  # we can request a particular length, but by default the properties of the decomposer should be used
            length = self.sequence_length
        if len(subgoals) == 0:
            # we can't decompose the rest of the silhouette (are the conditions too strict?)
            if verbose:
                print("No decompositions for state found")
            return []
        sequences = itertools.chain.from_iterable(
            [itertools.permutations(subgoals, l) for l in range(length + 1)]
        )
        # filter sequences
        filtered_sequences = []
        if verbose:
            print("Filtering sequences...")
            # let's calculate the number of permutations so we don't need to turn the iterator into a list
            num_permutations = self.get_number_of_permutations(length, subgoals)
            print("Predicted number of sequences:", num_permutations)
            print("Checking necessary conditions...")
            for sequence in tqdm(sequences, total=num_permutations):
                if self.check_necessary_sequence_conditions(sequence, state):
                    filtered_sequences.append(sequence)
            sequences = filtered_sequences
        else:
            sequences = [
                s
                for s in sequences
                if self.check_necessary_sequence_conditions(s, state)
            ]
        if number_of_sequences is not None and number_of_sequences < len(sequences):
            # if we want to return a limited number of sequences, we do so by randomly sampling
            sequences = random.choices(sequences, k=number_of_sequences)
        # turn into objects
        sequences = [Subgoal_sequence(s, state.world) for s in sequences]
        return sequences

    def get_number_of_permutations(self, length, subgoals):
        """Calculate number of permutations of length *length* from *subgoals*. This is not sensitive to the number of"""
        return int(
            sum(
                [
                    math.factorial(len(subgoals)) / math.factorial(len(subgoals) - l)
                    for l in range(1, length + 1)
                ]
            )
        )

    def get_name(self):
        return type(self).__name__

    def get_parameters(self):
        """Returns dict of parameters"""
        return {
            "necessary_conditions": [
                cond.__str__() for cond in self.necessary_conditions
            ],
            "necessary_sequence_conditions": [
                cond.__str__() for cond in self.necessary_sequence_conditions
            ],
        }

    def __str__(self):
        return self.get_name() + "(" + str(self.get_parameters()) + ")"

    def legal_next_subgoal(self, before, after):
        """Check if the after subgoal can follow the before, ie is a real improvement and subsumes the before"""
        return (
            np.all(after["decomposition"] - before["decomposition"] >= 0)
            and np.sum(after["decomposition"] - before["decomposition"]) > 0
        )


class Horizontal_Construction_Paper(Decomposition_Function):
    """Horizontal construction paper. Returns all positions irregardless of state."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_decompositions(self, state=None):
        decompositions = []
        for y in range(self.silhouette.shape[0]):
            decomposition = np.copy(self.silhouette)
            decomposition[0:y, :] = 0
            bitmap = np.ones_like(self.silhouette)
            bitmap[0:y, :] = 0
            decompositions += [
                {
                    "decomposition": decomposition,
                    "bitmap": bitmap,
                    "name": abs(self.silhouette.shape[0] - y),
                }
            ]
        decompositions.reverse()
        return decompositions

    def get_sequences(
        self, state=None, length=1, number_of_sequences=None, verbose=False
    ):
        """Generate a list of all legal (ie. only strictly increasing) sequences of subgoals up to *length* deep.

        Filter for length ensures that the lenght of sequence is either *n* or that the sequence ends in the complete decomposition. False includes incomplete sequences (use this for incremental planners).
        """
        subgoals = self.get_decompositions(state=state)
        sequences = [[s] for s in subgoals]
        next_sequences = sequences.copy()  # stores the sequences of the current length
        for l in range(length - 1):
            current_sequences = next_sequences
            next_sequences = []
            for current_sequence in current_sequences:
                for subgoal in subgoals:
                    if self.legal_next_subgoal(current_sequence[-1], subgoal):
                        # if we can do the subgoal after the current sequence, include it
                        new_sequence = current_sequence + [subgoal]
                        sequences.append(new_sequence)
                        next_sequences.append(new_sequence)
        if self.filter_for_length:
            sequences = self.filter_for_length(sequences, length)
        if number_of_sequences is not None and number_of_sequences < len(sequences):
            # if we want to return a limited number of sequences, we do so by randomly sampling
            sequences = random.choices(sequences, k=number_of_sequences)
        # turn into objects
        sequences = [Subgoal_sequence(s, state.world) for s in sequences]
        return sequences

    def filter_for_length(self, sequences, length):
        """Filter out sequences that don't have the required length *unless* they end with the full decomposition (since if the sequence ends, we can only reach the full decomp in lucky cases)"""
        return [
            s
            for s in sequences
            if len(s) == length
            or (len(s) <= length and np.all(s[-1]["decomposition"] == self.silhouette))
        ]


class Rectangular_Keyholes(Decomposition_Function):
    """Implements the decomposition of the target into rectangular keyholes.
    Necessary conditions is a list of functions that candidate keyholes must satisfy. They get passed (subgoal (with subgoal['decomposition] as bitmap), current state of the world)

    `decomposition` contains the part of the silhouette that is covered by the subgoal.
    `bitmap` contains the *shape* of the subgoal, including negative space in the silhouette that happens to be in the subgoal.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_all_potential_decompositions(self):
        decompositions = []
        # get all possible rectangles
        for x in range(self.silhouette.shape[1]):
            for y in range(self.silhouette.shape[0]):
                for w in range(self.silhouette.shape[1] - x + 1):
                    for h in range(self.silhouette.shape[0] - y + 1):
                        bitmap = np.zeros(self.silhouette.shape)
                        bitmap[y : y + h, x : x + w] = 1
                        decomposition = self.silhouette * bitmap
                        decompositions += [
                            {
                                "decomposition": decomposition,
                                "bitmap": bitmap,
                                "name": "x:{} y:{} w:{} h:{}".format(x, y, w, h),
                                "x": x,
                                "y": y,
                                "w": w,
                                "h": h,
                            }
                        ]
        return decompositions


class No_Subgoals(Rectangular_Keyholes):
    """Only returns the entire silhouette as a subgoal"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            sequence_length=1,
            necessary_conditions=[No_edge_rows_or_columns()],
            necessary_sequence_conditions=[Complete()],
        )

    def get_all_potential_decompositions(self):
        return super().get_all_potential_decompositions()


class Decomposition_Functions_Combined(Decomposition_Function):
    """Pass a list of decomposition functions to this class to combine them."""

    def __init__(self, decomposition_functions):
        self.decomposition_functions = decomposition_functions

    def get_all_potential_decompositions(self):
        decompositions = []
        for decomposition_function in self.decomposition_functions:
            decompositions += decomposition_function.get_all_potential_decompositions()
        return decompositions

    def get_sequences(
        self, state=None, length=None, number_of_sequences=None, verbose=False
    ):
        sequences = []
        for decomposition_function in self.decomposition_functions:
            sequences += decomposition_function.get_sequences(
                state=state,
                length=length,
                number_of_sequences=number_of_sequences,
                verbose=verbose,
            )
        return sequences

    def get_decompositions(self, state=None):
        decompositions = []
        for decomposition_function in self.decomposition_functions:
            decompositions += decomposition_function.get_decompositions(state=state)
        return decompositions

    def legal_next_subgoal(self, current_subgoal, next_subgoal):
        return all(
            [
                decomposition_function.legal_next_subgoal(current_subgoal, next_subgoal)
                for decomposition_function in self.decomposition_functions
            ]
        )

    def get_necessary_conditions(self):
        return [
            c
            for decomposition_function in self.decomposition_functions
            for c in decomposition_function.get_necessary_conditions()
        ]

    def get_necessary_sequence_conditions(self):
        return [
            c
            for decomposition_function in self.decomposition_functions
            for c in decomposition_function.get_necessary_sequence_conditions()
        ]

    def get_necessary_conditions_for_length(self, length):
        return [
            c
            for decomposition_function in self.decomposition_functions
            for c in decomposition_function.get_necessary_conditions_for_length(length)
        ]

    def __str__(self):
        return (
            "Combined("
            + ", ".join([str(d) for d in self.decomposition_functions])
            + ")"
        )

    def get_parameters(self):
        return {str(d): d.get_parameters() for d in self.decomposition_functions}


# CONDITIONS
# Necessary conditions for SUBGOALS
# Necessary conditions is a list of functions that candidate keyholes must satisfy. They get passed (decomposition (with decomposition['decomposition] as bitmap), current state of the world)
# subset of condition to implement __call__ so the object can be called like a function


class Condition:
    def __init__(self):
        pass

    def __call__(self, decomposition, state):
        return True

    def __str__(self):
        return self.__class__.__name__


class Area_larger_than(Condition):
    def __init__(self, area):
        self.area = area

    def __call__(self, decomposition, state):
        return decomposition["w"] * decomposition["h"] > self.area

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.area) + ")"


class Area_smaller_than(Condition):
    def __init__(self, area):
        self.area = area

    def __call__(self, decomposition, state):
        return decomposition["w"] * decomposition["h"] < self.area

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.area) + ")"


class Mass_larger_than(Condition):
    def __init__(self, area):
        self.area = area

    def __call__(self, decomposition, state):
        return np.sum(decomposition["decomposition"] > 0) > self.area

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.area) + ")"


class Mass_smaller_than(Condition):
    def __init__(self, area):
        self.area = area

    def __call__(self, decomposition, state):
        return np.sum(decomposition["decomposition"] > 0) < self.area

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.area) + ")"


class Non_empty(Condition):
    def __call__(self, decomposition, state):
        return np.sum(decomposition["decomposition"]) > 0


class Width_larger_than(Condition):
    def __init__(self, width):
        self.width = width

    def __call__(self, decomposition, state):
        return decomposition.w > self.width

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.width) + ")"


class Height_larger_than(Condition):
    def __init__(self, height):
        self.height = height

    def __call__(self, decomposition, state):
        return decomposition.h > self.height

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.height) + ")"


class No_empty_rows(Condition):
    """Ensure that no subgoals contains empty rows"""

    def __call__(self, decomposition, state):
        # get relevant rows from bitmap
        rows = np.where(decomposition["bitmap"].sum(axis=1) > 0)[0]
        return not np.any(
            [np.all(decomposition["decomposition"][i, :] == 0) for i in rows]
        )


class No_empty_columns(Condition):
    """Ensure that no subgoals contains empty columns"""

    def __call__(self, decomposition, state):
        # get relevant columns from bitmap
        columns = np.where(decomposition["bitmap"].sum(axis=0) > 0)[0]
        return not np.any(
            [np.all(decomposition["decomposition"][:, i] == 0) for i in columns]
        )


class No_empty_rows_or_columns(Condition):
    """Ensure that no subgoals contains empty rows or columns."""

    def __call__(self, decomposition, state):
        return No_empty_columns()(decomposition, state) and No_empty_rows()(
            decomposition, state
        )


class No_edge_rows_or_columns(Condition):
    """Ensure that no subgoals contains empty rows or columns at the extremes of the subgoal"""

    def __call__(self, decomposition, state):
        # get relevant rows from bitmap
        rows = np.where(decomposition["bitmap"].sum(axis=1) > 0)[0]
        try:
            rows = [min(rows), max(rows)]
        except ValueError:  # happens if there are no rows/cols
            return True  # since this condition is not technically violated
        # get relevant columns from bitmap
        columns = np.where(decomposition["bitmap"].sum(axis=0) > 0)[0]
        columns = [min(columns), max(columns)]
        # do we have empty space on the edge?
        return not np.any(
            [np.all(decomposition["decomposition"][i, :] == 0) for i in rows]
        ) and not np.any(
            [np.all(decomposition["decomposition"][:, i] == 0) for i in columns]
        )


class Empty_cells(Condition):
    """Ensure that no subgoals contains n or more empty cells"""

    def __init__(self, empty_cells):
        self.empty_cells = empty_cells

    def __call__(self, decomposition, state):
        # get map of empty space in subgoal
        empty_space = (decomposition["decomposition"] == 0) * decomposition["bitmap"]
        # do we have empty space on the edge?
        return np.sum(empty_space) > self.empty_cells

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.empty_cells) + ")"


class Fewer_built_cells(Condition):
    """Ensures that no subgoal contains n or more cells that have already built blocks on them"""

    def __init__(self, built_cells=0):
        self.built_cells = built_cells

    def __call__(self, decomposition, state):
        # get map of empty space in subgoal
        built_space = (state.blockmap * decomposition["bitmap"]) > 0
        # do we have empty space on the edge?
        return np.sum(built_space) <= self.built_cells

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.built_cells) + ")"


class Proportion_of_silhouette_less_than(Condition):
    """Ensures that the ratio of the silhouette of the subgoal to the area of the subgoal is less than a certain value. Ie., pass 2/3 to ensure that all subgoals cover less than 2/3 of the mass of the silhouette. 1 will still prevent the single full decomposition, but nothing else."""

    def __init__(self, ratio):
        self.ratio = ratio

    def __call__(self, decomposition, state):
        # get silhouette
        silhouette = state.world.silhouette
        mass = np.sum(silhouette > 0)
        # get area
        area = np.sum(decomposition["decomposition"] > 0)
        # get ratio
        ratio = area / mass
        return ratio < self.ratio

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.ratio) + ")"


# Necessary conditions for SEQUENCES OF SUBGOALS
# Necessary conditions is a list of functions that candidate keyholes must satisfy. They get passed ([decomposition (with decomposition['decomposition] as bitmap]), current state of the world)


class Sequence_Condition:
    def __init__(self):
        pass

    def __call__(self, sequence, state):
        return True

    def __str__(self):
        return self.__class__.__name__


class Filter_for_length(Sequence_Condition):
    """Only allow sequences of a certain length. Shorter, but complete sequences are always allowed."""

    def __init__(self, length):
        self.length = length

    def __call__(self, sequence, state):
        if len(sequence) == self.length:
            return True
        if len(sequence) < self.length and Complete()(sequence, state):
            return True
        return False

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.length) + ")"


class Longer_than(Sequence_Condition):
    """Only allow sequences longer than n. If you want shorter sequences, pass a parameter to the decomposition function—super inefficient to overgenerate and sample in that case."""

    def __init__(self, length):
        self.length = length

    def __call__(self, sequence, state):
        if len(sequence) > self.length:
            return True
        return False

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.length) + ")"


class Longer_than_or_complete(Sequence_Condition):
    """Only allow sequences longer than n, or complete sequences. If you want shorter sequences, pass a parameter to the decomposition function—super inefficient to overgenerate and sample in that case."""

    def __init__(self, length):
        self.length = length

    def __call__(self, sequence, state):
        if len(sequence) > self.length or Complete()(sequence, state):
            return True
        return False

    def __str__(self):
        return self.__class__.__name__ + "(" + str(self.length) + ")"


class Complete(Sequence_Condition):
    """The entire remaining structure is covered by the subgoals"""

    def __call__(self, sequence, state):
        silhouette = state.world.silhouette
        # we only need to care about the part of the silhouette that we haven't built on yet
        silhouette = silhouette * (state.blockmap == 0)
        occupancy = np.zeros(silhouette.shape)
        for decomposition in sequence:
            occupancy += decomposition["decomposition"]
        return np.all((occupancy > 0) == (silhouette > 0))


class Keyhole_increasing(Sequence_Condition):
    """For Horizontal_Construction_Paper,. Ensures that only increasing sequences are considered"""

    def __call__(self, sequence, state):
        for i in range(1, len(sequence)):
            if int(sequence[i]["name"]) <= int(sequence[i - 1]["name"]):
                return False
        return True


class No_overlap(Sequence_Condition):
    """Should be general. Ensure that no subgoals overlap on parts of the actual figure"""

    def __call__(self, sequence, state):
        # create map of occupancy
        occupancy = (sequence[0]["decomposition"] > 0) * 1.0
        for i in range(1, len(sequence)):
            occupancy = occupancy + (sequence[i]["decomposition"] > 0)
        return max(occupancy.flatten()) <= 1


class Supported(Sequence_Condition):
    """Ensures that there is at least one cell in each subgoal that has below it a cell that is either filled out or part of a previous subgoal"""

    def __call__(self, sequence, state):
        # create map of occupancy
        occupancy = (state.blockmap > 0) * 1.0
        for i in range(len(sequence)):
            # update occupancy
            if i > 0:  # nothing to fill for the first subgoal
                occupancy += sequence[i - 1]["decomposition"] > 0
            current = sequence[i]["decomposition"] > 0
            # we need to ignore what is currently 'in' the subgoal to see if it is supported
            # is the current subgoal supported by the ground? If yes, we can move on to the next one
            if np.any(current[-1::]):
                continue
            other_occupancy = occupancy * (current == 0)
            # shift current occupancy down by one
            current = np.roll(current, 1, axis=0)
            # ignore first row since we looped it around
            current[0, :] = 0
            # any overlap?
            if not np.sum(other_occupancy * current) > 0:
                return False
        return True
