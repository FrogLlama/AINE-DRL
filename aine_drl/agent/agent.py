from abc import ABC
from typing import List
from aine_drl.experience import Trajectory, Experience
from aine_drl.drl_algorithm import DRLAlgorithm
from aine_drl.policy import Policy
from aine_drl.util import aine_api
from aine_drl.drl_util import Clock
import numpy as np
import torch

class Agent(ABC):
    def __init__(self, 
                 drl_algorithm: DRLAlgorithm, 
                 policy: Policy, 
                 trajectory: Trajectory,
                 env_count: int = 1,
                 summary_freq: int = 1) -> None:
        """
        Args:
            drl_algorithm (DRLAlgorithm): DRL algorithm
            policy (Policy): policy
            trajectory (Trajectory): tajectory
            env_count (int, optional): environment count. Defaults to 1.
            summary_freq (int, optional): summary frequency which must be greater than `env_count`. Defaults to 1.
        """
        assert env_count > 0 and summary_freq >= env_count
        self.drl_algorithm = drl_algorithm
        self.policy = policy
        self.trajectory = trajectory
        self.env_count = env_count
        self.summary_freq = summary_freq
        self.summary_count = 0
        self.clock = Clock(env_count)
        
    @aine_api
    def update(self, experience: List[Experience]):
        """
        Update the agent. It stores data, trains the DRL algorithm, etc.

        Args:
            experience (List[Experience]): experiences of which the element count must be the environment count.
        """
        # set trajectory
        self.trajectory.add(experience)
        # set clock
        self.clock.tick_time_step()
        if experience[0].terminated:
            self.clock.tick_episode()
        # if can log data
        if self.clock.time_step >= (self.summary_count + 1) * self.summary_freq:
            self.drl_algorithm.log_data(self.clock.time_step)
            self.policy.log_data(self.clock.time_step)
            self.summary_count += 1
        # try training algorithm
        if self._try_train_algorithm():
            self.drl_algorithm.update_hyperparams(self.clock.time_step)
            self.policy.update_hyperparams(self.clock.time_step)
    
    @aine_api
    def act(self, states: np.ndarray) -> np.ndarray:
        """
        Returns actions from the state batch

        Args:
            states (np.ndarray): state batch

        Returns:
            np.ndarray: actions
        """
        pdparam = self.drl_algorithm.get_pdparam(torch.from_numpy(states))
        dist = self.policy.get_policy_distribution(pdparam)
        return dist.sample()
    
    def _try_train_algorithm(self) -> bool:
        can_train = self.trajectory.can_train
        while self.trajectory.can_train:
            batch = self.trajectory.sample()
            # train the algorithm
            self.drl_algorithm.train(batch)
            self.clock.tick_training_step()
        return can_train
