from typing import List, Dict, Any, Optional, Set, Tuple
import math
import numpy as np
from pathlib import Path
import json
import uuid
import copy
import logging
logger = logging.getLogger(__name__)


class MCTSState:
    """
    State representation for MCTS.
    Contains information about the current idea, depth, and reward.
    """
    def __init__(
        self, 
        research_goal: Optional[str] = None,
        current_idea: Optional[str] = None, 
        depth: int = 0, 
        reward: float = 0,
        retrieved_knowledge: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[Dict[str, Any]] = None
    ):
        self.research_goal = research_goal
        self.current_idea = current_idea or ""
        self.depth = depth 
        self.reward = reward
        self.review_scores = {}  # Dictionary to store individual criterion scores
        self.review_feedback = {}  # Dictionary to store feedback for each criterion
        self.average_score = 0.0  # Average score across all criteria
        self.retrieved_knowledge = retrieved_knowledge or []  # Knowledge retrieved for this state
        self.feedback = feedback or {}  # General feedback for this state
        # Add trajectory-level memory attributes
        self.last_query = None  # Track the last retrieval query
        self.problematic_aspects = []  # Track aspects that have been problematic
        self.action_count = {}  # Count of each action type taken
        self.memory_size = 3  # Keep last 3 items in memory

    def __eq__(self, other):
        if isinstance(other, MCTSState):
            return self.current_idea == other.current_idea
        return False

    def __hash__(self):
        return hash(self.current_idea)
    
    def record_action(self, action: str, **kwargs):
        """Record an action in the trajectory memory"""
        self.last_action = action
        
        # Update action count
        self.action_count[action] = self.action_count.get(action, 0) + 1
        
        # Handle specific action types
        if action == "retrieve_and_refine" and "query" in kwargs:
            self.last_query = kwargs["query"]
        
        if action == "review_and_refine" and "low_scoring_aspects" in kwargs:
            # Keep track of problematic aspects (limit to memory_size)
            new_aspects = kwargs["low_scoring_aspects"]
            self.problematic_aspects.extend(new_aspects)
            # Keep only last few aspects to avoid memory explosion
            if len(self.problematic_aspects) > self.memory_size:
                self.problematic_aspects = self.problematic_aspects[-self.memory_size:]
    
    def get_memory_context(self) -> Dict[str, Any]:
        """Get current memory context for decision making"""
        return {
            "last_query": self.last_query,
            "problematic_aspects": self.problematic_aspects[-self.memory_size:],
            "action_count": self.action_count.copy(),
            "recent_actions": self._get_recent_actions()
        }
    
    def _get_recent_actions(self) -> List[str]:
        """Get list of recent actions for diversity checking"""
        # This would be populated by the parent tracking recent actions
        # For now, return based on action_count
        return [action for action, count in self.action_count.items() if count > 0]
    

    def to_json(self) -> Dict[str, Any]:
        """Serialize state to JSON."""
        return {
            "research_goal": self.research_goal,
            "current_idea": self.current_idea,
            "depth": self.depth,
            "reward": self.reward,
            "review_scores": self.review_scores,
            "review_feedback": self.review_feedback,
            "average_score": self.average_score,
            "retrieved_knowledge": self.retrieved_knowledge,
            "feedback": self.feedback
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'MCTSState':
        """Create state from JSON."""
        state = cls(
            research_goal=data.get("research_goal"),
            current_idea=data.get("current_idea", ""),
            depth=data.get("depth", 0),
            reward=data.get("reward", 0),
            retrieved_knowledge=data.get("retrieved_knowledge", []),
            feedback=data.get("feedback", {})
        )
        # Load additional review data if available
        if "review_scores" in data:
            state.review_scores = data["review_scores"]
        if "review_feedback" in data:
            state.review_feedback = data["review_feedback"]
        if "average_score" in data:
            state.average_score = data["average_score"]
        return state


class MCTSNode:
    """
    Node in the MCTS tree.
    Contains state information and statistics for MCTS algorithm.
    """
    def __init__(
        self, 
        state: MCTSState, 
        action: Optional[str] = None, 
        parent=None, 
        exploration_weight: float = 1.0
    ):
        self.id = str(uuid.uuid4())
        self.state = state
        self.action = action
        self.parent = parent
        self.children = []
        self.visits = 0
        self.value = 0
        self.exploration_weight = exploration_weight
        self.actions = ["generate", "reflect_and_reframe", "review_and_refine", "retrieve_and_refine"]

        # Add fields to track review data
        self.reviews = {
            "scores": {},
            "feedback": {},
            "average_score": 0.0
        }

    def add_child(self, state: MCTSState, action: str = None) -> 'MCTSNode':
        """Add a child node with the given state and action."""
        child_node = MCTSNode(state=state, action=action, parent=self)
        self.children.append(child_node)
        return child_node

    def update(self, reward: float) -> None:
        """Update node statistics."""
        self.visits += 1
        # Incremental update of value
        self.value += (reward - self.value) / self.visits

    def fully_expanded(self) -> bool:
        """Check if all possible actions have been explored."""
        # Assumes a fixed set of actions
        return len(self.children) >= len(self.actions)

    def best_child(self, exploration_weight: Optional[float] = None) -> 'MCTSNode':
        """Select best child node according to UCB formula."""
        if exploration_weight is None:
            exploration_weight = self.exploration_weight

        # UCB formula: value + exploration_weight * sqrt(ln(parent visits) / child visits)
        def ucb_score(child):
            exploitation = child.value
            exploration = math.sqrt(2 * math.log(self.visits) / child.visits)
            return exploitation + exploration_weight * exploration

        # Filter out children with zero visits (should not happen in practice)
        valid_children = [child for child in self.children if child.visits > 0]
        if not valid_children:
            # If no visits yet, select randomly among all children
            return np.random.choice(self.children) if self.children else None

        # Return the child with the highest UCB score
        return max(valid_children, key=ucb_score)

    def to_json(self) -> Dict[str, Any]:
        """Serialize node to JSON."""
        children_data = [child.to_json() for child in self.children]
        
        node_data = {
            "id": self.id,
            "action": self.action,
            "state": self.state.to_json(),
            "visits": self.visits,
            "value": self.value,
            "depth": self.state.depth,
            "reward": self.state.reward,
            "reviews": self.reviews,
            "children": children_data
        }
        
        # Add parent reference if it exists
        if self.parent:
            node_data["parent_id"] = self.parent.id
            
        return node_data

    def update_review_data(self) -> None:
        """Update review data from state for consistency."""
        if hasattr(self.state, 'review_scores') and self.state.review_scores:
            self.reviews["scores"] = copy.deepcopy(self.state.review_scores)
        
        if hasattr(self.state, 'review_feedback') and self.state.review_feedback:
            self.reviews["feedback"] = copy.deepcopy(self.state.review_feedback)
            
        if hasattr(self.state, 'average_score') and self.state.average_score:
            self.reviews["average_score"] = self.state.average_score

    @classmethod
    def from_json(cls, data: Dict[str, Any], parent=None) -> 'MCTSNode':
        """Create node from JSON."""
        # Create state from state data
        state = MCTSState.from_json(data["state"])
        
        # Create node
        node = cls(
            state=state, 
            action=data.get("action"), 
            parent=parent
        )
        
        # Set node attributes
        node.id = data.get("id", str(uuid.uuid4()))
        node.visits = data.get("visits", 0)
        node.value = data.get("value", 0)
        
        # Load review data if available
        if "reviews" in data:
            node.reviews = data["reviews"]
        
        return node

    @classmethod
    def build_tree_from_json(cls, data: Dict[str, Any]) -> 'MCTSNode':
        """Recursively build tree from JSON."""
        # Create the current node
        node = cls.from_json(data)
        
        # Recursively build children
        for child_data in data.get("children", []):
            child = cls.build_tree_from_json(child_data)
            child.parent = node
            node.add_child(child)
            
        return node

    def save_to_file(self, filepath: str) -> None:
        """Save tree to a JSON file."""
        # Update review data from state before saving
        self.update_review_data()
        
        # Serialize to JSON
        tree_json = self.to_json()
        
        # Write to file
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(tree_json, f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> 'MCTSNode':
        """Load tree from a JSON file."""
        with open(filepath, "r") as f:
            tree_json = json.load(f)
        return cls.build_tree_from_json(tree_json)