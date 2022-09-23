from typing import List
from aine_drl.drl_util import Experience
from aine_drl.trajectory import Trajectory

class BatchTrajectory(Trajectory):
    """
    It's a batch trajectory abstract class for the batch learning. It can store `max_num_exp` experiences.
    """
    def __init__(self, max_num_exp: int, num_envs: int = 1) -> None:
        """
        Args:
            max_num_exp (int): maximum number of experiences to be stored
            num_envs (int, optional): number of environments. Defaults to 1.
        """
        assert max_num_exp > 0 and num_envs > 0
        self.num_envs = num_envs
        self.max_num_exp = max_num_exp # maximum number of elements
        self.reset()
        
    @property
    def count(self) -> int:
        return self._count
        
    def reset(self):
        self._count = 0 # total experience count of all environments
        self.recent_idx = -1 # index of the most recent experience
        
        self.states = [None] * self.max_num_exp
        self.actions = [None] * self.max_num_exp
        self.rewards = [None] * self.max_num_exp
        self.terminateds = [None] * self.max_num_exp
        self.next_state_buffer = [None] * self.num_envs # most recently added next state
        
    def add(self, experiences: List[Experience]):
        assert len(experiences) == self.num_envs
        for i, ex in enumerate(experiences):
            self.recent_idx = (self.recent_idx + 1) % self.max_num_exp
            self._count = min(self._count + 1, self.max_num_exp)
            
            self.states[self.recent_idx] = ex.state
            self.actions[self.recent_idx] = ex.action
            self.rewards[self.recent_idx] = ex.reward
            self.terminateds[self.recent_idx] = ex.terminated
            self.next_state_buffer[i] = ex.next_state
    