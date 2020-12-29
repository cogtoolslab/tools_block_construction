import os
from random import choice
import sys
from typing import Sequence

proj_dir =  os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0,proj_dir)

import utils.blockworld as blockworld
from model.BFS_Agent import *
import model.utils.decomposition_functions
import copy
import numpy as np

BAD_SCORE = -9999

class Subgoal_Planning_Agent(BFS_Agent):
    """Implements n subgoal lookahead planning"""

    def __init__(self,
                         world=None,
                         decomposer = None,
                         lookahead = 1,
                         include_subsequences=True,
                         r_weight = 1000,
                         S_treshold=0.8,
                         S_iterations=1,
                         lower_agent = BFS_Agent(only_improving_actions=True),
                         random_seed = None
                         ):
            self.world = world
            self.lookahead = lookahead
            self.include_subsequences = include_subsequences # only consider sequences of subgoals exactly `lookahead` long or ending on final decomposition
            self.r_weight = r_weight
            self.S_threshold = S_treshold #ignore subgoals that are done in less than this proportion
            self.S_iterations = S_iterations #how often should we run the simulation to determine S?
            self.lower_agent = lower_agent
            self.random_seed = random_seed
            if decomposer is None:
                try:
                    decomposer = model.utils.decomposition_functions.Horizontal_Construction_Paper(self.world.full_silhouette)
                except AttributeError: # no world has been passed, will need to be updated using decomposer.set_silhouette
                    decomposer = model.utils.decomposition_functions.Horizontal_Construction_Paper(None) 
            self.decomposer = decomposer
            self._cached_subgoal_evaluations = {} #sets up cache for  subgoal evaluations

    def __str__(self):
            """Yields a string representation of the agent"""
            return str(self.get_parameters())

    def get_parameters(self):
        """Returns dictionary of agent parameters."""
        return {**{
            'agent_type':self.__class__.__name__,
            'lookeahead':self.lookahead,
            'decomposition_function':self.decomposer.__class__.__name__,
            'include_subsequences':self.include_subsequences,
            'r_weight':self.r_weight,
            'S_threshold':self.S_threshold,
            'S_iterations':self.S_iterations,
            'random_seed':self.random_seed
            }, **{"lower level: "+key:value for key,value in self.lower_agent.get_parameters().items()}}
    
    def set_world(self, world):
        super().set_world(world)
        self.decomposer.set_silhouette(world.full_silhouette)
        self._cached_subgoal_evaluations = {} #clear cache

    def act(self,steps=1,verbose=False):
        """Finds subgoal plan, then builds the first subgoal. Steps here refers to subgoals (ie. 2 steps is acting the first two planned subgoals). Pass -1 to steps to execute the entire subgoal plan."""
        if self.random_seed is None: self.random_seed = randint(0,99999)
        # get best sequence of subgoals
        sequence,sg_planning_cost = self.plan_subgoals(verbose=verbose)
        # finally plan and build all subgoals in order
        cur_i = 0
        lower_level_cost = 0
        lower_level_info = []
        lower_level_actions = []
        self.lower_agent.world = self.world
        while cur_i < len(sequence) and cur_i != steps: 
            current_subgoal = sequence[cur_i]
            self.world.set_silhouette(current_subgoal['decomposition'])
            self.world.current_state.clear() #clear caches
            while self.world.status()[0] == "Ongoing":
                actions, info = self.lower_agent.act()
                lower_level_cost += info['states_evaluated']
                lower_level_info.append(info)
                lower_level_actions+=actions
            cur_i += 1
            self.world.set_silhouette(self.world.full_silhouette) # restore full silhouette to the world we're acting with
        return lower_level_actions,{'states_evaluated':lower_level_cost,
                                'sg_planning_cost':sg_planning_cost,
                                '_subgoal_sequence':sequence}

    def plan_subgoals(self,verbose=False):
        """Plan a sequence of subgoals. First, we need to compute a sequence of subgoals however many steps in advance (since completion depends on subgoals). Then, we compute the cost and value of every subgoal in the sequence. Finally, we choose the sequence of subgoals that maximizes the total value over all subgoals within."""
        self.decomposer.set_silhouette(self.world.full_silhouette) #make sure that the decomposer has the right silhouette
        sequences = self.decomposer.get_sequences(state = self.world.current_state,length=self.lookahead,filter_for_length=not self.include_subsequences)
        if verbose: 
            print("Got",len(sequences),"sequences:")
            for sequence in sequences:
                print([g['name'] for g in sequence])
        # we need to score each in sequence (as it depends on the state before)
        number_of_states_evaluated = self.score_subgoals_in_sequence(sequences,verbose=verbose)
        # now we need to find the sequences that maximizes the total value of the parts according to the formula $V_{Z}^{g}(s)=\max _{z \in Z}\left\{R(s, z)-C_{\mathrm{Alg}}(s, z)+V_{Z}^{g}(z)\right\}$
        return self.choose_sequence(sequences,verbose=verbose),number_of_states_evaluated #return the sequence of subgoals with the highest score
    
    def choose_sequence(self, sequences,verbose=False):
        """Chooses the sequence that maximizes $V_{Z}^{g}(s)=\max _{z \in Z}\left\{R(s, z)-C_{\mathrm{Alg}}(s, z)+V_{Z}^{g}(z)\right\}$ including weighing by lambda"""
        scores = [None]*len(sequences)
        for i in range(len(sequences)):
            scores[i] = self.score_sequence(sequences[i])
            if verbose: print("Scoring sequence",i+1,"of",len(sequences),"->",[g['name'] for g in sequences[i]],"score:",scores[i])
        if verbose: print("Chose sequence:\n",sequences[scores.index(max(scores))])
        top_indices = [i for i in range(len(scores)) if scores[i] == max(scores)]
        top_sequences = [sequences[i] for i in top_indices]
        seed(self.random_seed) #fix random seed
        return choice(top_sequences)

    def score_sequence(self,sequence):
        """Compute the value of a single sequence with precomputed S,R,C"""
        score = 0
        try:
            for subgoal in sequence:
                if subgoal['C'] is None or subgoal['S'] is None or subgoal['S'] < self.S_threshold or subgoal['R'] == 0: 
                    # we have a case where the subgoal computation was aborted early or we should ignore the subgoal because the success rate is too low or the reward is zero (subgoal already done or empty)
                    subgoal_score = BAD_SCORE
                else:
                    # compute regular score
                    subgoal_score = self.r_weight * subgoal['R'] - subgoal['C']
                score += subgoal_score
        except KeyError:
            # The sequence could not be scored. This happens if we don't get a prior solution for some step of the sequence. 
            return BAD_SCORE
        return score
  
    def score_subgoals_in_sequence(self,sequences,verbose=False):
        """Add C,R,S to the subgoals in the sequences"""
        number_of_states_evaluated = 0
        seq_counter = 0 # for verbose printing
        for sequence in sequences: #reference or copy?
            seq_counter += 1 # for verbose printing
            sg_counter = 0 # for verbose printing
            prior_world = self.world
            for subgoal in sequence:
                sg_counter += 1 # for verbose printing
                #get reward and cost and success of that particular subgoal and store the resulting world
                R = self.reward_of_subgoal(subgoal['decomposition'],prior_world.current_state.blockmap) 
                S,C,prior_world,total_cost = self.success_and_cost_of_subgoal(subgoal['decomposition'],prior_world)
                number_of_states_evaluated += total_cost
                if verbose: 
                    print("For sequence",seq_counter,'/',len(sequences),
                    "scored subgoal",
                    sg_counter,'/',len(sequence),"named",
                    subgoal['name'],
                    "with C:"+str(C)," R:"+str(R)," S:"+str(S))
                #store in the subgoal
                subgoal['R'] = R
                subgoal['C'] = C
                subgoal['S'] = S
                #if we can't solve it to have a base for the next one, we break
                if prior_world is None:
                    break
        return number_of_states_evaluated

    def reward_of_subgoal(self,decomposition,prior_blockmap):
        """Gets the unscaled reward of a subgoal: the area of a figure that we can fill out by completing the subgoal in number of cells beyond what is already filled out."""
        return np.sum((decomposition * self.world.full_silhouette) - (prior_blockmap > 0))

    def success_and_cost_of_subgoal(self,decomposition,prior_world = None, iterations=1,max_steps = 20,fast_fail = True):
        """The cost of solving for a certain subgoal given the current block construction"""
        if prior_world is None:
            prior_world = self.world
        # generate key for cache
        key = decomposition * 2 - (prior_world.current_state.blockmap > 0)
        key = key.tostring() #make hashable
        if key in self._cached_subgoal_evaluations:
            # print("Cache hit for",key)
            cached_eval = self._cached_subgoal_evaluations[key]
            return cached_eval['S'],cached_eval['C'],cached_eval['winning_world'],1 #returning 1 as lookup cost, not the cost it tool to calculate the subgoal originally
        current_world = copy.deepcopy(prior_world)
        costs = 0
        wins = 0
        winning_world = None
        for i in range(iterations):
            temp_world = copy.deepcopy(current_world)
            temp_world.set_silhouette(decomposition)
            temp_world.current_state.clear() #clear caches
            self.lower_agent.world = temp_world
            steps = 0
            while temp_world.status()[0] == 'Ongoing' and steps < max_steps:
                _,info = self.lower_agent.act()
                costs += info['states_evaluated']
            wins += temp_world.status()[0] == 'Win'
            if temp_world.status()[0] == 'Win':
                winning_world = copy.deepcopy(temp_world)
            #break early to save performance in case of fail
            if fast_fail and temp_world.status()[0] == 'Fail':
                return 0,None,None,costs
        #store cached evaluation
        cached_eval = {'S':wins/iterations,'C':costs/iterations,'winning_world':winning_world}
        self._cached_subgoal_evaluations[key] = cached_eval
        return wins/iterations,costs/iterations,winning_world,costs


