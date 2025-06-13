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
        feedback: Optional[Dict[str, Any]] = None,
        # Enhanced memory components
        trajectory_memory: List[Dict] = None,
        action_history: List[str] = None,
        score_history: List[float] = None,
        knowledge_cache: Dict = None,
        attention_patterns: Dict = None,
        exploration_metadata: Dict = None
        
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
        # Enhanced memory components
        self.trajectory_memory = trajectory_memory or []
        self.action_history = action_history or []
        self.score_history = score_history or []
        self.knowledge_cache = knowledge_cache or {}
        self.attention_patterns = attention_patterns or {
            "relevant_focus": 0.5,
            "noise_reduction": 0.3,
            "context_awareness": 0.4
        }
        self.exploration_metadata = exploration_metadata or {
            "visit_count": 0,
            "last_visited": None,
            "parent_path": [],
            "sibling_comparisons": [],
            "performance_trend": "stable"
        }

    def __eq__(self, other):
        if isinstance(other, MCTSState):
            return self.current_idea == other.current_idea
        return False

    def __hash__(self):
        return hash(self.current_idea)

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

    def add_memory_entry(self, action: str, outcome: Dict, score: float):
        """Add a new entry to trajectory memory"""
        from datetime import datetime
        
        # Initialize memory components if they don't exist
        if not hasattr(self, 'trajectory_memory'):
            self.trajectory_memory = []
        if not hasattr(self, 'action_history'):
            self.action_history = []
        if not hasattr(self, 'score_history'):
            self.score_history = []
        if not hasattr(self, 'exploration_metadata'):
            self.exploration_metadata = {
                "visit_count": 0,
                "last_visited": None,
                "parent_path": [],
                "sibling_comparisons": [],
                "performance_trend": "stable"
            }
        
        memory_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "outcome": outcome,
            "score": score,
            "depth": self.depth,
            "context": {
                "idea_length": len(self.current_idea),
                "knowledge_count": len(self.retrieved_knowledge),
                "feedback_count": len(self.feedback)
            }
        }
        self.trajectory_memory.append(memory_entry)
        self.action_history.append(action)
        self.score_history.append(score)
        
        # Update exploration metadata
        self.exploration_metadata["visit_count"] += 1
        self.exploration_metadata["last_visited"] = memory_entry["timestamp"]
        
        # Update performance trend
        if len(self.score_history) >= 3:
            recent_avg = sum(self.score_history[-3:]) / 3
            earlier_avg = sum(self.score_history[-6:-3]) / 3 if len(self.score_history) >= 6 else recent_avg
            
            if recent_avg > earlier_avg + 0.3:
                self.exploration_metadata["performance_trend"] = "improving"
            elif recent_avg < earlier_avg - 0.3:
                self.exploration_metadata["performance_trend"] = "declining"
            else:
                self.exploration_metadata["performance_trend"] = "stable"

    def update_attention_patterns(self, action: str, outcome: Dict):
        """Update attention patterns based on action outcomes"""
        # Initialize attention patterns if they don't exist
        if not hasattr(self, 'attention_patterns'):
            self.attention_patterns = {
                "relevant_focus": 0.5,
                "noise_reduction": 0.3,
                "context_awareness": 0.4
            }
        
        if action == "retrieve_and_refine":
            # Update based on retrieval success
            papers_found = outcome.get("papers_found", 0)
            improvement_detected = outcome.get("improvement_detected", False)
            
            self.attention_patterns["relevant_focus"] = min(1.0, papers_found / 5.0)
            self.attention_patterns["noise_reduction"] = 0.8 if improvement_detected else 0.3
            
        elif action == "review_and_refine":
            # Update based on review feedback
            aspects_improved = outcome.get("aspects_improved", 0)
            score_increase = outcome.get("score_increase", 0)
            
            self.attention_patterns["context_awareness"] = min(1.0, aspects_improved / 3.0)
            if score_increase > 0.5:
                self.attention_patterns["relevant_focus"] += 0.1
                
        # Normalize attention values
        for key in self.attention_patterns:
            self.attention_patterns[key] = max(0.0, min(1.0, self.attention_patterns[key]))

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