import copy

from scoping_simulations.model.Agent import Agent
from scoping_simulations.model.Astar_Agent import Astar_Agent
from scoping_simulations.model.Best_First_Search_Agent import Best_First_Search_Agent
from scoping_simulations.model.BFS_Agent import BFS_Agent
from scoping_simulations.model.heuristics.cost_heuristic import ActionCostHeuristic
from scoping_simulations.model.Random_Agent import Random_Agent
from scoping_simulations.model.utils.decomposition_functions import Subgoal


class AgentCostHeuristic(ActionCostHeuristic):
    """Returns the cost of using a action level search algorithm to solve the subgoal"""

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def __call__(self, subgoal: Subgoal) -> float:
        """Returns the cost of using a action level search algorithm to solve the subgoal"""
        # make sure that we are not overwriting the world
        world = copy.deepcopy(subgoal.prior_world)
        world.silhouette = subgoal.target
        self.agent.set_world(world)
        actions, results = self.agent.act(steps=None, verbose=False)
        states_evaluated = results["states_evaluated"]
        return states_evaluated

    def repeat(self, subgoal: Subgoal, n: int) -> float:
        """Returns the costs of n runs of the heuristic."""
        costs = []
        for i in range(n):
            # set agent random seed
            self.agent.random_seed = i
            costs.append(self(subgoal))
        return costs

    def repeat_mean(self, subgoal: Subgoal, n: int) -> float:
        """Returns the mean costs of n runs of the heuristic."""
        costs = self.repeat(subgoal, n)
        return sum(costs) / len(costs)


class BestFirstHeuristic(AgentCostHeuristic):
    "Uses the Best First Search Agent to solve the subgoal"

    def __init__(self):
        super().__init__(Best_First_Search_Agent())
        self.agent.label = "Best First Heuristic"


class BestFirstRepetitionsHeuristic(BestFirstHeuristic):
    """Runs the Best First Heuristic multiple times and returns the average."""

    def __init__(self, n: int = 100):
        super().__init__()
        self.n = n
        self.heuristic = BestFirstHeuristic()
        self.heuristic.agent.label = "Best First Heuristic ({} repetitions)".format(n)

    def __call__(self, subgoal: Subgoal) -> float:
        return self.heuristic.repeat(subgoal, self.n)


class AStarHeuristic(AgentCostHeuristic):
    "Uses A* to solve the subgoal"

    def __init__(self):
        super().__init__(Astar_Agent(heuristic=lambda x: len(x.blocks)))
        self.agent.label = "A* Heuristic (based on number of blocks)"


class AStarRepetitionsHeuristic(AStarHeuristic):
    """Runs the A* Heuristic multiple times and returns the average."""

    def __init__(self, n: int = 100):
        super().__init__()
        self.n = n
        self.heuristic = AStarHeuristic()
        self.heuristic.agent.label = "A* Heuristic ({} repetitions)".format(n)

    def __call__(self, subgoal: Subgoal) -> float:
        return self.heuristic.repeat(subgoal, self.n)


class BFSHeuristic(AgentCostHeuristic):
    "Uses the BFS Agent to solve the subgoal"

    def __init__(self):
        super().__init__(BFS_Agent())
        self.agent.label = "BFS Heuristic"


class RandomAgentHeuristic(AgentCostHeuristic):
    """Uses the Random Agent to solve the subgoal.

    Warning:
    * this is not deterministic
    * this can take a very long time to run_experiment
    """

    def __init__(self):
        super().__init__(Random_Agent())
        self.agent.label = "Random Agent Heuristic"


AGENT_HEURISTICS = [
    BestFirstHeuristic,
    AStarHeuristic,
    BFSHeuristic,
    # RandomAgentHeuristic, # not included by default
]
