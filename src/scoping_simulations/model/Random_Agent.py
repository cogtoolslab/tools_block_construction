from scoping_simulations.model.BFS_Lookahead_Agent import BFS_Lookahead_Agent
from scoping_simulations.utils.blockworld import random_scoring


class Random_Agent(BFS_Lookahead_Agent):
    """An agent that randomly takes a legal step until a terminal state is reached."""

    def __init__(self, world=None, random_seed=None, label="Random"):
        super().__init__(
            world,
            horizon=1,
            random_seed=random_seed,
            sparse=True,
            scoring="Fixed",
            scoring_function=random_scoring,
            label=label,
        )

    def __str__(self):
        """Yields a string representation of the agent"""
        return self.__class__.__name__ + " random seed: " + str(self.random_seed)

    def get_parameters(self):
        """Returns dictionary of agent parameters."""
        return {
            "agent_type": self.__class__.__name__,
            "random_seed": self.random_seed,
            "label": self.label,
        }
