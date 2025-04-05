from typing import Dict
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class CostTracker:
    """Tracks costs of LLM API usage"""
    budget: float = 50.0  # Default budget of $50
    input_cost_per_million: float = 0.1  # $0.1 per million tokens for input
    output_cost_per_million: float = 0.4  # $0.4 per million tokens for output
    total_input_tokens: int = field(default=0)
    total_output_tokens: int = field(default=0)
    _start_time: datetime = field(default_factory=datetime.now)
    
    def calculate_current_cost(self) -> float:
        """Calculate current cost based on input and output tokens"""
        input_cost = (self.total_input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (self.total_output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost
    
    def add_tokens(self, input_tokens: int, output_tokens: int) -> bool:
        """
        Add tokens to the tracker and check if we're still within budget
        Returns True if we're within budget, False if we've exceeded it
        """
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        current_cost = self.calculate_current_cost()
        
        # Log the current usage
        logger.info(f"Current usage: ${current_cost:.4f} | "
                   f"Input tokens: {self.total_input_tokens} | "
                   f"Output tokens: {self.total_output_tokens}")
        
        return current_cost <= self.budget
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        current_cost = self.calculate_current_cost()
        return {
            "current_cost": current_cost,
            "budget": self.budget,
            "remaining_budget": self.budget - current_cost,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "tracking_duration": str(datetime.now() - self._start_time)
        }

# Global instance
cost_tracker = CostTracker()

def update_budget(new_budget: float):
    """Update the global cost tracker's budget"""
    global cost_tracker
    cost_tracker.budget = new_budget
    logger.info(f"Budget updated to: ${new_budget}")

def track_tokens(input_tokens: int, output_tokens: int) -> bool:
    """
    Track token usage and return whether we're still within budget
    To be called after each LLM generation
    """
    global cost_tracker
    return cost_tracker.add_tokens(input_tokens, output_tokens)

def get_current_usage() -> Dict:
    """Get current usage statistics"""
    global cost_tracker
    return cost_tracker.get_usage_stats()