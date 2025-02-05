import collections
from scipy.special import softmax
import os
import pickle

from rlcard.utils.utils import *


class SARSAAgent:
    ''' Implement SARSA algorithm
    '''

    def __init__(self, env, model_path='./sarsa_model', alpha=0.1, gamma=0.4):
        ''' Initialize Agent
         Args:
         env (Env): Env class
         hyperparameters: alpha, gamma: default the optimal found be tune_ql
        '''
        self.gamma = gamma
        self.alpha = alpha
        self.agent_id = 0
        self.use_raw = False
        self.env = env
        self.model_path = model_path

        # A policy is a dict state_str -> action probabilities
        self.policy = collections.defaultdict(list)
        self.a = len(self.policy)
        # Regret is a dict state_str -> action regrets
        self.qualities = collections.defaultdict(list)

        self.iteration = 0

    def train(self):
        ''' Do one iteration of Sarsa
        '''
        self.iteration += 1
        self.a = len(self.policy)
        self.env.reset()
        self.find_agent()
        self.traverse_tree()

    def find_agent(self):
        ''' Find if the agent starts first or second
                '''
        agents = self.env.get_agents()
        for id, agent in enumerate(agents):
            if isinstance(agent, SARSAAgent):
                self.agent_id = id
                break

    def traverse_tree(self):
        ''' Traverse the game tree:

                Check if the game is over to return the chips earned(reward of the game)
                If opponents plays make the other agent play
                If our agent plays check every possible action and get the Q value of the action
                Then return the Vstate of current state which is Sum(prob(actiona)*V(next_state,actiona)) (on policy)
                Change the policy according to the new Q values
                '''
        if self.env.is_over():
            chips = self.env.get_payoffs()
            return chips[self.agent_id]

        current_player = self.env.get_player_id()
        # compute the quality of previous state
        if not current_player == self.agent_id:
            state = self.env.get_state(current_player)
            # other agent move
            action = self.env.agents[current_player].step(state)

            # Keep traversing the child state
            self.env.step(action)
            Vstate = self.traverse_tree()
            self.env.step_back()
            return Vstate

        if current_player == self.agent_id:
            quality = {}
            value = 0
            obs, legal_actions = self.get_state(current_player)
            action_probs = self.action_probs(obs, legal_actions, self.policy, self.qualities)
            for action in legal_actions:
                action_prob = action_probs[action]

                # Keep traversing the child state
                self.env.step(action)
                q = self.traverse_tree()
                self.env.step_back()

                value += action_prob * q
                quality[action] = q  # value of each action

            ''' alter policy according to new Vactions'''
            self.update_policy(obs, quality, legal_actions)

        return value*self.gamma

    def action_probs(self, obs, legal_actions, policy, action_values):
        ''' Obtain the action probabilities(policy) of the current state
        or create a new policy

        Args:
            obs (str): state_str
            legal_actions (list): List of legal actions
            player_id (int): The current player
            policy (dict): The used policy
            action_values (dict): The action_values of policy

        Returns:
            (tuple) that contains:
                action_probs(numpy.array): The action probabilities
                legal_actions (list): Indices of legal actions
        '''
        # if new state initialize qualities and policy
        if obs not in policy.keys() and obs not in self.qualities.keys():
            tactions = np.array([-np.inf for action in range(self.env.num_actions)])
            for action in range(self.env.num_actions):
                if action in legal_actions:
                    tactions[action] = 0
            self.qualities[obs] = tactions
            action_probs = softmax(tactions)
            self.policy[obs] = action_probs
        else:
            action_probs = policy[obs].copy()
        action_probs = remove_illegal(action_probs, legal_actions)
        return action_probs

    def update_policy(self, obs, next_state_values, legal_actions):
        ''' Update the policy according to the new state/action quality
                Args:
                    obs (str): state_str
                    next_state_values (list): The new qualities of the current iteration
         '''
        # update the quality function
        qf = self.qualities[obs]
        for i in next_state_values:
            qf[i] += self.alpha * (next_state_values[i] - qf[i])

        # update action values
        self.qualities[obs] = qf
        self.policy[obs] = softmax(qf)

    def eval_step(self, state):
        ''' Given a state, predict action based on average policy

        Args:
            state (numpy.array): State representation

        Returns:
            action (int): Predicted action
            info (dict): A dictionary containing information
        '''

        probs = self.action_probs(state['obs'].tostring(), list(state['legal_actions'].keys()), self.policy,
                                  self.qualities)
        #action = np.random.choice(len(probs), p=probs)
        action = np.argmax(probs)

        info = {}
        info['probs'] = {state['raw_legal_actions'][i]: float(probs[list(state['legal_actions'].keys())[i]]) for i in
                         range(len(state['legal_actions']))}

        return action, info

    def step(self, state):
        '''step = eval.step
        '''
        return self.eval_step(state)

    def get_state(self, player_id):
        ''' Get state_str of the player

        Args:
            player_id (int): The player id

        Returns:
            (tuple) that contains:
                state (str): The state str
                legal_actions (list): Indices of legal actions
        '''
        state = self.env.get_state(player_id)
        return state['obs'].tostring(), list(state['legal_actions'].keys())

    def save(self):
        '''  Save model
        '''

        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path)

        policy_file = open(os.path.join(self.model_path, 'policy.pkl'),'wb')
        pickle.dump(self.policy, policy_file)
        policy_file.close()

        values_file = open(os.path.join(self.model_path, 'qualities.pkl'),'wb')
        pickle.dump(self.qualities, values_file)
        values_file.close()

        iteration_file = open(os.path.join(self.model_path, 'iteration.pkl'),'wb')
        pickle.dump(self.iteration, iteration_file)
        iteration_file.close()

    def load(self):
        ''' Load model
        '''

        if not os.path.exists(self.model_path):
            return

        policy_file = open(os.path.join(self.model_path, 'policy.pkl'),'rb')
        self.policy = pickle.load(policy_file)
        policy_file.close()

        values_file = open(os.path.join(self.model_path, 'qualities.pkl'),'rb')
        self.qualities = pickle.load(values_file)
        values_file.close()

        iteration_file = open(os.path.join(self.model_path, 'iteration.pkl'),'rb')
        self.iteration = pickle.load(iteration_file)
        iteration_file.close()