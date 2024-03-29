import random
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

import scoping_simulations.utils.blockworld as blockworld
from scoping_simulations.model.Astar_Agent import Stochastic_Priority_Queue
from scoping_simulations.model.Beam_Search_Lookahead_Agent import backtrack
from scoping_simulations.model.BFS_Lookahead_Agent import (
    Ast_edge,
    Ast_node,
    BFS_Lookahead_Agent,
)

# class for the priority queue


@dataclass(order=True)
class FringeNode:
    cost: int
    node: Any = field(compare=False)


class Astar_Lookahead_Agent(BFS_Lookahead_Agent):
    """An agent implementing the A* algorithm. The algorithm uses a fixed cost (so it tries to find the shortest path to the goal) and a given scoring function as heuristic to distance to goal. The heuristic should include stability.
    An upper limit can be set to prevent endless in difficult problems. -1 for potentially endless search.
    return_best: if true, the agent will return the best path found so far when it hits the upper limit. Otherwise, it will return None.

    The heuristic should be admissible: it should be an upper bound to the actual cost of reaching the goal.
    The h function estimates distance to goal by taking a heuristic, which should return degree of completion between 0 and 1, calculated the number of cells left to fill out and takes the average size of blocks in the library to provice an estimation of steps left to goal. Penalties get represented as really large distances.

    TODO: - [ ] save memory by not adding penalized states to priority queue

    This is a simplified implementation that doesn't take into account that the same state can be reached in multiple ways. However, because we defined the cost function as number of steps, every state can only be reached in the same number of steps (since taking more steps means placing more blocks, and different sizes of blocks lead to potentially different stability), and therefore there cannot be a better path to a node in open set, just an equivalently good one.
    """

    def __init__(
        self,
        world=None,
        heuristic=blockworld.recall,
        max_steps=10**6,
        only_improving_actions=False,
        dense_stability=False,
        random_seed=None,
        label="A* lookahead",
        return_best=True,
    ):
        self.world = world
        self.heuristic = heuristic
        self.max_steps = max_steps
        self.only_improving_actions = only_improving_actions
        self.dense_stability = dense_stability
        self.random_seed = random_seed
        self.label = label
        self.return_best = return_best
        if self.random_seed is None:
            self.random_seed = random.randint(0, 99999)

    def __str__(self):
        """Yields a string representation of the agent"""
        return (
            self.__class__.__name__
            + " heuristic: "
            + self.heuristic.__name__
            + " max_steps "
            + str(self.max_steps)
            + " dense_stability "
            + str(self.dense_stability)
            + " random seed: "
            + str(self.random_seed)
            + " label: "
            + self.label
        )

    def get_parameters(self):
        """Returns dictionary of agent parameters."""
        return {
            "agent_type": self.__class__.__name__,
            "heuristic": self.heuristic.__name__,
            "max_steps": self.max_steps,
            "dense_stability": self.dense_stability,
            "random_seed": self.random_seed,
            "label": self.label,
        }

    def act(self, steps=None, verbose=False):
        """By default performs a full iteration of A*, then acts all the steps."""
        # check if we even can act
        if self.world.status()[0] != "Ongoing":
            print("Can't act with world in status", self.world.status())
            return
        # preload values needed for heuristic
        # the number of cells in the silhouette
        self._silhouette_size = self.world.silhouette.sum()
        self._avg_block_size = mean(
            [block.width * block.height for block in self.world.block_library]
        )
        step = 0
        edges, number_of_states_evaluated = self.Astar_search(verbose)
        for edge in edges:  # act in the world for each edge
            if self.only_improving_actions:
                # check if action improves the current state of the world
                if not self.world.current_state.is_improvement(edge.action):
                    break
            self.world.apply_action(edge.action)
            step += 1
            if verbose:
                print(
                    "Took step ",
                    step,
                    " with action ",
                    [str(a) for a in edge.action],
                    " and got world state",
                    self.world.current_state,
                )
                self.world.current_state.visual_display(
                    blocking=True, silhouette=self.world.silhouette
                )
            if step == steps:
                break  # if we have acted x steps, stop acting
        if verbose:
            print("Done, reached world status: ", self.world.status())
        return [e.action for e in edges][:step], {
            "states_evaluated": number_of_states_evaluated
        }

    def Astar_search(self, verbose=False):
        root = Ast_node(self.world.current_state)
        i = 0
        number_of_states_evaluated = 0
        # using a priority queue to manage the states
        open_set = Stochastic_Priority_Queue()
        open_set.put(FringeNode(self.f(root), root))
        while not open_set.empty() and i != self.max_steps:
            i += 1
            # get node with lowest projected cost. This removes it from the open set
            current_node = open_set.get()
            # check if that node is winning
            if current_node is None:  # empty set after all
                break
            if self.world.is_win(current_node.state):  # 🎉
                if verbose:
                    print("Found winning state after", i)
                return backtrack(current_node), number_of_states_evaluated
            # get children of current state
            possible_actions = current_node.state.possible_actions()
            for action in possible_actions:
                # add the resulting child nodes to the open set
                target_state = self.world.transition(action, current_node.state)
                # if the target state is not stable, don't add it to open set
                if self.dense_stability and not target_state.stability():
                    continue
                # get target state ast node object
                target_node = Ast_node(target_state)
                edge = Ast_edge(action, current_node, target_node)  # make edge
                # add the parent action to allow for backtracking the found path
                edge.target.parent_action = edge
                # place the children in the open set
                open_set.put(FringeNode(self.f(target_node), target_node))
                number_of_states_evaluated += 1
            if verbose:
                print("Step", i, "with open set with", open_set.qsize(), "members")
        if verbose:
            print("A* unsuccessful after iteration ", i)
        if self.return_best:
            return backtrack(current_node), number_of_states_evaluated
        else:
            return [], number_of_states_evaluated

    def f(self, node):
        """The combined cost function that takes into account the cost to get to the node (g) as well as the projected cost of reaching the goal (h).
        g is the number of blocks that have already been placed.
        h should be an estimation of the number of blocks that need to be placed before the silhouette is filled out.
        """
        return self.g(node) + self.h(node)

    def g(self, node):
        """Cost to get to node from start in steps"""
        return len(node.state.blocks)

    def h(self, node):
        """Estimated cost to get from current node to goal state.
        The heuristic should be admissible: it should be a lower bound to the actual cost of reaching the goal. The h function estimates distance to goal by taking a heuristic, which should return degree of completion between 0 and 1, calculated the number of cells left to fill out and takes the average size of blocks in the library to provice an estimation of steps left to goal.
        """
        heur = self.heuristic(node.state)
        out = -(heur - 1) * self._silhouette_size / self._avg_block_size
        # return 0 if the cost to goal is less than 0 (which doesn't make sense)
        return max(0, out)
