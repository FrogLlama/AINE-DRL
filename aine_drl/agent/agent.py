from abc import ABC, abstractmethod
from typing import Dict, Tuple
from aine_drl.experience import Action, ActionTensor, Experience
from aine_drl.network import Network
from aine_drl.policy.policy import Policy
import aine_drl.util as util
from aine_drl.drl_util import Clock, IClockNeed, ILogable
import numpy as np
import torch
from enum import Enum

class BehaviorType(Enum):
    TRAIN = 0,
    INFERENCE = 1

class Agent(ABC):
    """
    Deep reinforcement learning agent.
    
    Args:
        network (Network): deep neural network
        policy (Policy): policy
        num_envs (int): number of environments
    """
    def __init__(self, 
                 network: Network,
                 policy: Policy,
                 num_envs: int) -> None:
        self._clock = Clock(num_envs)
        if isinstance(network, IClockNeed):
            network.set_clock(self._clock)
        if isinstance(policy, IClockNeed):
            policy.set_clock(self._clock)
            
        self.__logable_network = network if isinstance(network, ILogable) else None
        self.__logable_policy = policy if isinstance(policy, ILogable) else None
        
        self.policy = policy
        self.network = network
        self.num_envs = num_envs
        self._behavior_type = BehaviorType.TRAIN
        self.device = util.get_model_device(network)

        self.traced_env = 0
        self.cumulative_average_reward = util.IncrementalAverage()
        self.cumulative_reward = 0.0
        self.episode_average_len = util.IncrementalAverage()
        
    def select_action(self, obs: np.ndarray) -> Action:
        """
        Select action from the observation. 
        `batch_size` must be `num_envs` x `n_steps`. `n_steps` is generally 1. 
        It depends on `Agent.behavior_type` enum value.

        Args:
            obs (ndarray): observation which is the input of neural network. shape must be `(batch_size, *obs_shape)`

        Returns:
            Action: selected action
        """
        assert self.policy is not None, "You must call `Agent.set_policy()` method before it."
        
        if self.behavior_type == BehaviorType.TRAIN:
            return self.select_action_train(torch.from_numpy(obs).to(device=self.device)).to_action()
        elif self.behavior_type == BehaviorType.INFERENCE:
            with torch.no_grad():
                return self.select_action_inference(torch.from_numpy(obs).to(device=self.device)).to_action()
        else:
            raise ValueError(f"Agent.behavior_type you currently use is invalid value. Your value is: {self.behavior_type}")
        
    def update(self, experience: Experience):
        """
        Update the agent. It stores data, trains the agent, etc.

        Args:
            experience (Experience): experience
        """
        assert experience.num_envs == self.num_envs
        
        self._update_info(experience)
            
    def _update_info(self, experience: Experience):
        self.clock.tick_gloabl_time_step()
        self.cumulative_reward += experience.reward[self.traced_env].item()
        # if the traced environment is terminated
        if experience.terminated[self.traced_env] > 0.5:
            self.cumulative_average_reward.update(self.cumulative_reward)
            self.cumulative_reward = 0.0
            self.episode_average_len.update(self.clock.episode_len)
            self.clock.tick_episode()
        
    @abstractmethod
    def select_action_train(self, obs: torch.Tensor) -> ActionTensor:
        """
        Select action when training.

        Args:
            obs (Tensor): observation tensor whose shape is `(batch_size, *obs_shape)`

        Returns:
            ActionTensor: action tensor
        """
        raise NotImplementedError
    
    @abstractmethod
    def select_action_inference(self, obs: torch.Tensor) -> ActionTensor:
        """
        Select action when inference. It's automatically called with `torch.no_grad()`.

        Args:
            obs (Tensor): observation tensor

        Returns:
            ActionTensor action tensor
        """
        raise NotImplementedError
    
    @property
    def clock(self) -> Clock:
        return self._clock
    
    @property
    def behavior_type(self) -> BehaviorType:
        """Returns behavior type. Defaults to train."""
        return self._behavior_type
    
    @behavior_type.setter
    def behavior_type(self, value: BehaviorType):
        """Set behavior type."""
        self._behavior_type = value
    
    @property
    def log_keys(self) -> Tuple[str, ...]:
        """Returns log data keys."""
        lk = ("Environment/Cumulative Reward", "Environment/Episode Length")
        if self.__logable_network is not None:
            lk += self.__logable_network.log_keys
        if self.__logable_policy is not None:
            lk += self.__logable_policy.log_keys
        return lk
        
    @property
    def log_data(self) -> Dict[str, tuple]:
        """
        Returns log data and reset it.

        Returns:
            Dict[str, tuple]: key: (value, time)
        """
        ld = {}
        if self.cumulative_average_reward.count > 0:
            ld["Environment/Cumulative Reward"] = (self.cumulative_average_reward.average, self.clock.global_time_step)
            ld["Environment/Episode Length"] = (self.episode_average_len.average, self.clock.episode)
            self.cumulative_average_reward.reset()
            self.episode_average_len.reset()
        if self.__logable_network is not None:
            ld.update(self.__logable_network.log_data)
        if self.__logable_policy is not None:
            ld.update(self.__logable_policy.log_data)
        return ld
            
    @property
    def state_dict(self) -> dict:
        """Returns the state dict of the agent."""
        sd = self.clock.state_dict
        sd["network"] = self.network.state_dict()
        return sd
    
    def load_state_dict(self, state_dict: dict):
        """Load the state dict."""
        self.clock.load_state_dict(state_dict)
        self.network.load_state_dict(state_dict["network"])
