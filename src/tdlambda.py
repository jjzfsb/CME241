from typing import Optional, Tuple, Sequence, Callable, Mapping
from src.my_funcs import get_rv_gen_func_single, SAf, S
from src.mdp_for_rl_tabular import MDPRLTabular
from src.monte_carlo import MonteCarlo
import numpy as np

class TDLambda():
    
    def __init__(
        self,
        mdp_rep_for_rl: MDPRLTabular,
        epsilon: float,
        epsilon_half_life: float,
        learning_rate: float,
        learning_rate_decay: float,
        lambd: float,
        num_episodes: int,
        max_steps: int
    ) -> None:
        self.mdp_rep: MDPRLTabular = mdp_rep_for_rl
        self.epsilon: float = epsilon
        self.epsilon_half_life: float = epsilon_half_life
        self.learning_rate: float = learning_rate
        self.learning_rate_decay: float = learning_rate_decay
        self.lambd: float = lambd
        self.num_episodes: int = num_episodes
        self.max_steps: int = max_steps
        self.gamma_lambda = self.mdp_rep.gamma * lambd
    
    
    def forward_value_func(self, pol: SAf) -> Mapping[S, float]:
        sa_dict = self.mdp_rep.state_action_dict
        vf_dict = {s: 0. for s in sa_dict.keys()}
        episodes = 0
        monte = MonteCarlo(self.mdp_rep, True, \
                           self.num_episodes, self.max_steps)
        
        while episodes < self.num_episodes:
            start_state = self.mdp_rep.init_state_gen()
            mc_path = monte.get_mc_path(pol, start_state)
            rew_arr = np.array([x for _, _, x, _ in mc_path[:-1]])
            state_list = [x for x, _, _, _ in mc_path[:-1]]
            val_arr = np.array([vf_dict[s] for s in state_list])
            if mc_path[-1][0] in self.mdp_rep.terminal_states:
                returns = self.get_returns(rew_arr,val_arr)
            else:
                raise RuntimeError('MC path did not reach terminal states, \
                                    increase max_steps')
            for i, r in enumerate(returns):
                s, _, _, _ = mc_path[i]
                vf_dict[s] += self.learning_rate * (returns[i] - vf_dict[s])

            episodes += 1
            
        return vf_dict
    
    
    def backward_value_func(self, pol: SAf) -> Mapping[S, float]:
        sa_dict = self.mdp_rep.state_action_dict
        vf_dict = {s: 0. for s in sa_dict.keys()}
        action_dic = {s: get_rv_gen_func_single(pol[s]) \
                      for s in self.mdp_rep.state_action_dict.keys()}
        episodes = 0
        updates = 0
        
        while episodes < self.num_episodes:
            et_dict = {s: 0. for s in sa_dict.keys()}
            state = self.mdp_rep.init_state_gen()
            steps = 0
            terminate = False
            
            while not terminate:
                action = action_dic[state]()
                next_state, reward =\
                    self.mdp_rep.state_reward_gen_dict[state][action]()
                delta = reward + self.mdp_rep.gamma * vf_dict[next_state] -\
                    vf_dict[state]
                et_dict[state] += 1
                alpha = self.learning_rate * (updates / self.learning_rate_decay
                                              + 1) ** -0.5
                for s in sa_dict.keys():
                    vf_dict[s] += alpha * delta * et_dict[s]
                    et_dict[s] *= self.gamma_lambda
                updates += 1
                steps += 1
                terminate = steps >= self.max_steps or\
                    state in self.mdp_rep.terminal_states
                state = next_state

            episodes += 1

        return vf_dict
    
    def get_returns(self, reward: Sequence[float], val_arr: Sequence[float]) -> list:
        T = len(reward) + 1
        discount = np.power(self.mdp_rep.gamma, np.arange(T))
        returns = []
        for t in range(T-1):
            gt = []
            for i in range(T-t-1):
                gt.append(np.dot(reward[t:t+i+1], discount[:i+1])\
                         + discount[i+1] * val_arr[t+i]  )
            returns.append(sum([g*(self.lambd**k)*(1-self.lambd) \
                                for k,g in enumerate(gt)]))
    
        return returns