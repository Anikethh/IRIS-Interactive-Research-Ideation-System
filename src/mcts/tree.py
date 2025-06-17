import random
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import json
import yaml
from loguru import logger
from collections import defaultdict
import math
from .node import MCTSNode, MCTSState
import numpy as np
import re
import requests
import os
from tqdm import tqdm
import subprocess
from ..agents.ideation import IdeationAgent
from ..agents.review import ReviewAgent


class MCTS:
    """Monte Carlo Tree Search implementation for research ideation."""

    def __init__(self, config_path: str):
        """Initialize MCTS with configuration."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Initialize agents
        self.ideation_agent = IdeationAgent(config_path)
        self.review_agent = ReviewAgent(config_path)

        self.load_prompts()

        # Initialize tracking
        self.current_rollout_id = 0
        self.iteration = 0
        self.results_dir = Path(self.config["experiment"]["results_dir"])
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # MCTS specific parameters
        self.Q = defaultdict(float)  # total reward of each node
        self.N = defaultdict(int)  # visit count for each node
        self.parent2children = {}  # children of each node
        self.explored_nodes = set()  # tracked explored nodes

        # Parameters from config
        self.exploration_weight = self.config["mcts"]["exploration_constant"]
        self.num_rollouts = self.config["experiment"]["n_rollouts"]
        self.discount_factor = self.config["mcts"]["discount_factor"]

        # Add retrieval related paths
        self.data_dir = Path("../data")
        self.retrieved_dir = self.data_dir / "retrieved"
        self.retrieved_dir.mkdir(parents=True, exist_ok=True)
        self.grobid_dir = self.data_dir / "grobid_processed"
        self.grobid_dir.mkdir(parents=True, exist_ok=True)

        # Semantic Scholar API settings
        self.s2_api_url = "https://api.semanticscholar.org/graph/v1"
        s2_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if not s2_api_key:
            logger.warning("SEMANTIC_SCHOLAR_API_KEY environment variable is not set. Semantic Scholar API features will be disabled.")
            self.s2_headers = {}
        else:
            self.s2_headers = {
                "x-api-key": s2_api_key
            }

    def load_prompts(self) -> None:
        """Load prompts from configuration."""
        prompts_path = Path(self.config["experiment"]["prompts_path"])
        with open(prompts_path) as f:
            self.prompts = yaml.safe_load(f)

    def do_rollout(self, root_node: MCTSNode, rollout_id: int) -> MCTSNode:
        """Perform one iteration of MCTS."""
        self.current_rollout_id = rollout_id
        logger.debug("Starting selection phase...")
        path = self._select(root_node)
        leaf = path[-1]

        logger.debug(f"Expanding node {leaf.id}...")
        self._expand(leaf)

        logger.debug(f"Simulating from node {leaf.id}...")
        simulation_path = self._simulate(leaf)

        logger.debug("Backpropagating results...")
        self._backpropagate(path + simulation_path)

        return simulation_path[-1] if simulation_path else path[-1]

    def _select(self, node: MCTSNode) -> List[MCTSNode]:
        """Select a path to an unexplored node."""
        path = []
        while True:
            path.append(node)
            logger.debug(
                f"Node {node.id}: depth={node.state.depth}, idea='{node.state.current_idea[:100]}...'"
            )
            logger.debug(f"Available actions: {node.get_valid_actions()}")

            # Case 1: Node hasn't been expanded
            if node not in self.parent2children:
                logger.debug(f"Node {node.id} not expanded yet")
                return path

            # Case 2: Node has unexplored children
            unexplored = [
                n for n in self.parent2children[node] if n not in self.explored_nodes
            ]
            if unexplored:
                n = random.choice(unexplored)
                logger.debug(
                    f"Selected unexplored node {n.id} with action '{n.action_taken}' in rollout {self.current_rollout_id}"
                )
                path.append(n)
                return path

            # Case 3: All children explored, select best UCT
            node = self._uct_select(node)
            logger.debug(
                f"Selected UCT node {node.id} with action '{node.action_taken}'"
            )

    def _expand(self, node: MCTSNode) -> None:
        """Expand node by generating all possible children."""
        if node in self.explored_nodes:
            return

        if node.is_terminal(self.config["experiment"]["max_depth"]):
            self.explored_nodes.add(node)
            return

        # Generate children using valid actions
        self.parent2children[node] = []
        for action in node.get_valid_actions():
            if action not in node.explored_actions:
                new_state = self.execute_action(node.state, action)
                child = node.add_child(new_state, action)
                self.parent2children[node].append(child)

    def _simulate(self, node: MCTSNode) -> List[MCTSNode]:
        """Simulate from node until terminal state."""
        path = []
        current = node

        logger.debug(f"Starting simulation from node with depth {current.state.depth}")
        while not current.is_terminal(self.config["experiment"]["max_depth"]):
            if current not in self.parent2children:
                actions = current.get_valid_actions()
                logger.debug(f"Available actions for simulation: {actions}")
                if not actions:
                    break

                action = random.choice(actions)
                logger.debug(f"Selected action for simulation: {action}")
                new_state = self.execute_action(current.state, action)
                current = current.add_child(new_state, action)

            else:
                current = random.choice(self.parent2children[current])
                logger.debug(
                    f"Selected existing child with action: {current.action_taken}"
                )
            path.append(current)

        return path

    def _backpropagate(self, path: List[MCTSNode], reward: float) -> None:
        """Backpropagate rewards through the path."""
        for node in reversed(path):
            self.Q[node] += reward
            self.N[node] += 1
            self.explored_nodes.add(node)
            reward *= self.discount_factor

    def _uct_select(self, node: MCTSNode) -> MCTSNode:
        """Select child node using UCT formula."""
        assert all(n in self.explored_nodes for n in self.parent2children[node])

        def uct_value(n: MCTSNode) -> float:
            if self.N[n] == 0:
                return float("inf")

            exploitation = self.Q[n] / self.N[n]
            exploration = self.exploration_weight * math.sqrt(
                math.log(self.N[node]) / self.N[n]
            )
            return exploitation + exploration

        return max(self.parent2children[node], key=uct_value)

    def execute_action(self, state: MCTSState, action: str) -> MCTSState:
        """Execute an action and return the new state."""
        try:
            # Convert MCTSState to dict for agent
            state_dict = {
                "current_idea": state.current_idea,
                "depth": state.depth,
                "action": action,
                "current_state": state,  # Pass the full state for memory access
                "memory_context": state.get_memory_context(),
            }

            # Add research goal if available
            if hasattr(state, "research_goal") and state.research_goal:
                state_dict["research_goal"] = state.research_goal

            # Add memory-aware context
            if hasattr(state, "get_memory_context"):
                state_dict["memory_context"] = state.get_memory_context()

            # Add review criteria if available
            if hasattr(state, "review_scores") and hasattr(state, "review_feedback"):
                review_criteria = []
                for criterion in ["novelty", "clarity", "feasibility", "effectiveness", "impact"]:
                    if criterion in state.review_scores:
                        review_criteria.append((criterion, state.review_feedback.get(criterion, "")))
                state_dict["review_criteria"] = review_criteria

            # Memory-aware action execution
            if action == "retrieve_and_refine":
                
                # Execute with memory context
                context_chunks = self._execute_retrieve_and_refine_with_memory(state, state_dict)
                state_dict["context_chunks"] = context_chunks

            if action == "review_and_refine":
                
                # Execute with memory context
                return self._execute_review_and_refine_with_memory(state, state_dict)

            # Add abstract to state_dict if available
            if hasattr(state, "abstract") and state.abstract:
                state_dict["abstract"] = state.abstract

            # Delegate action execution to ideation agent
            response = self.ideation_agent.execute_action(action, state_dict)

            # Get review from review agent using unified review (all aspects in one call)
            review_data = self.review_agent.unified_review(response["content"])

            reward = review_data["average_score"]

            # Create new state
            new_state = MCTSState(
                research_goal=state.research_goal if hasattr(state, "research_goal") else None,
                current_idea=response["content"], 
                depth=state.depth + 1, 
                reward=reward
            )

            # Copy memory state from parent
            new_state.last_action = state.last_action
            new_state.last_query = state.last_query
            new_state.problematic_aspects = state.problematic_aspects.copy()
            new_state.action_count = state.action_count.copy()

            # Record this action in memory
            new_state.record_action(action, query=state_dict.get("query"))

            # Add review data to state
            if review_data:
                if "scores" in review_data:
                    new_state.review_scores = review_data["scores"]
                if "reviews" in review_data:
                    new_state.review_feedback = review_data["reviews"]
                if "average_score" in review_data:
                    new_state.average_score = review_data["average_score"]

            # Save the state information for analysis
            self._save_action_result(state, action, response["content"], new_state)

            return new_state

        except Exception as e:
            logger.error(f"Error executing action {action}: {e}")
            return self._create_fallback_state(state)
    
    
    def _execute_retrieve_and_refine_with_memory(self, state: MCTSState, state_dict: Dict) -> MCTSState:
        """Execute retrieve_and_refine with memory using existing functions."""
        try:
            # Generate search query using existing retrieval logic
            # Extract key concepts from current idea for search
            search_query = self._extract_search_terms(state.current_idea)
            
            # Avoid repeating last query (moved after search_query is defined)
            if state.last_query and search_query == state.last_query:
                # Modify query slightly for diversity
                search_query = f"{search_query} methodology approach"
            
            # Use existing retrieval function
            context_chunks = self._retrieve_and_process_papers([search_query])
            
            if context_chunks:
                # Add retrieved context to state using existing pattern
                state_dict["context_chunks"] = context_chunks
                
                # Use existing retrieve_and_refine action
                response = self.ideation_agent.execute_action("retrieve_and_refine", state_dict)
                
                # Create new state using existing function
                new_state = self._create_new_state_from_response(state, response, "retrieve_and_refine")
                new_state.record_action("retrieve_and_refine", query=search_query)
                
                return new_state
            else:
                return self._create_fallback_state(state)
            
        except Exception as e:
            logger.error(f"Error in retrieve_and_refine with memory: {e}")
            return self._create_fallback_state(state)
    
    def _execute_review_and_refine_with_memory(self, state: MCTSState, state_dict: Dict) -> MCTSState:
        """Execute review_and_refine with memory using existing functions."""
        try:
            # Use existing unified review
            review_data = self.review_agent.unified_review(state.current_idea)
            
            if review_data:
                # Identify low-scoring aspects for memory
                scores = review_data.get("scores", {})
                low_scoring = [aspect for aspect, score in scores.items() if score < 6]
                
                # Focus on aspects not recently reviewed (memory-based steering)
                if state.problematic_aspects:
                    # Prioritize aspects that haven't been addressed recently
                    new_focus_aspects = [asp for asp in low_scoring if asp not in state.problematic_aspects[-2:]]
                    if new_focus_aspects:
                        low_scoring = new_focus_aspects[:3]  # Focus on top 3 new aspects
                
                # Add review data to state using existing pattern
                if "scores" in review_data:
                    state_dict["review_scores"] = review_data["scores"]
                if "reviews" in review_data:
                    state_dict["reviews"] = review_data["reviews"]
                    
                # Add memory context for non-redundant refinement
                if state.problematic_aspects:
                    state_dict["memory_context"] = f"Previously problematic aspects: {', '.join(state.problematic_aspects[-3:])}"
                
                # Use existing review_and_refine action
                response = self.ideation_agent.execute_action("review_and_refine", state_dict)
                
                # Create new state using existing function
                new_state = self._create_new_state_from_response(state, response, "review_and_refine")
                new_state.record_action("review_and_refine", low_scoring_aspects=low_scoring)
                
                return new_state
            else:
                return self._create_fallback_state(state)
                
        except Exception as e:
            logger.error(f"Error in review_and_refine with memory: {e}")
            return self._create_fallback_state(state)
    
    def _create_new_state_from_response(self, old_state: MCTSState, response: Dict, action: str) -> MCTSState:
        """Create new state from response - using existing pattern."""
        new_state = MCTSState(
            research_goal=old_state.research_goal,
            current_idea=response["content"],
            depth=old_state.depth + 1,
            reward=0.0,
            retrieved_knowledge=getattr(old_state, 'retrieved_knowledge', []),
            feedback=getattr(old_state, 'feedback', {})
        )
        
        # Copy memory state (initialize if not exists)
        new_state.last_action = getattr(old_state, 'last_action', None)
        new_state.last_query = getattr(old_state, 'last_query', None)
        new_state.problematic_aspects = getattr(old_state, 'problematic_aspects', []).copy()
        new_state.action_count = getattr(old_state, 'action_count', {}).copy()
        
        # Use existing review function
        review_data = self.review_agent.unified_review(response["content"])
        if review_data:
            new_state.review_scores = review_data.get("scores", {})
            new_state.review_feedback = review_data.get("reviews", {})
            new_state.average_score = review_data.get("average_score", 0.0)
            new_state.reward = review_data.get("average_score", 0.0) / 10
        
        return new_state
    
    def _create_fallback_state(self, state: MCTSState) -> MCTSState:
        """Create fallback state when action fails."""
        fallback_state = MCTSState(
            research_goal=state.research_goal,
            current_idea=state.current_idea,
            depth=state.depth + 1,
            reward=0.1,
            retrieved_knowledge=getattr(state, 'retrieved_knowledge', []),
            feedback=getattr(state, 'feedback', {})
        )
        
        # Copy memory safely
        fallback_state.last_action = getattr(state, 'last_action', None)
        fallback_state.last_query = getattr(state, 'last_query', None)
        fallback_state.problematic_aspects = getattr(state, 'problematic_aspects', []).copy()
        fallback_state.action_count = getattr(state, 'action_count', {}).copy()
        
        return fallback_state
    
    def _retrieve_relevant_chunks(self, idea: str) -> List[str]:
        """Retrieve relevant text chunks for a given idea."""
        # Placeholder implementation - in a real system, this would use a retrieval system
        try:
            # For now, return empty list which is handled gracefully by the agent
            return []
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            return []

    def _execute_simple_refinement(self, state: MCTSState) -> MCTSState:
        """Fallback refinement when action execution fails."""
        new_state = MCTSState(
            current_idea=state.current_idea, depth=state.depth + 1, reward=0.5
        )
        return new_state

    def _save_action_result(
        self, state: MCTSState, action: str, result: str, new_state: MCTSState
    ) -> None:
        """Save the result of an action for analysis."""
        try:
            # Create a results directory for this rollout if it doesn't exist
            rollout_dir = self.results_dir / f"rollout_{self.current_rollout_id}"
            rollout_dir.mkdir(exist_ok=True)

            # Save the action result
            result_path = rollout_dir / f"action_{state.depth}_{action}.json"
            result_data = {
                "previous_idea": state.current_idea,
                "action": action,
                "result": result,
                "depth": state.depth,
                "reward": new_state.reward,
                "review_scores": getattr(new_state, "review_scores", {}),
                "review_feedback": getattr(new_state, "review_feedback", {}),
                "average_score": getattr(new_state, "average_score", 0.0),
            }

            with open(result_path, "w") as f:
                json.dump(result_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving action result: {e}")

    def _get_review(self, idea: str) -> Optional[List[Dict]]:
        """Get review feedback and scores for an idea."""
        try:
            prompt = self.prompts["review_agent"]["evaluate_research_idea"].format(
                research_idea=idea
            )

            response = self.review_agent.chat(
                model=self.review_model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompts["review_agent"]["system"],
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            content = response["message"]["content"]

            # Try multiple parsing approaches
            review_data = self._parse_review_response(content)
            if review_data:
                return review_data

            # If parsing fails, extract what we can and create a simplified review
            logger.warning(
                "Structured parsing failed, attempting to extract scores heuristically"
            )
            scores = self._extract_scores(content)
            feedback = self._extract_feedback(content)

            if not scores and not feedback:
                logger.warning("Could not extract any structured data from review")
                # Create a basic review with the full response as feedback
                return [
                    {
                        "criterion": "overall",
                        "review": content,
                        "score": 5,  # Default middle score
                    }
                ]

            # Construct review data from extracted information
            reviews = []
            if scores:
                for criterion, score in scores.items():
                    reviews.append(
                        {
                            "criterion": criterion,
                            "review": feedback.get(
                                criterion, "No specific feedback available"
                            ),
                            "score": score,
                        }
                    )
            else:
                # If no scores found, create reviews with default scores
                for criterion, feedback_text in feedback.items():
                    reviews.append(
                        {
                            "criterion": criterion,
                            "review": feedback_text,
                            "score": 5,  # Default middle score
                        }
                    )

            return reviews

        except Exception as e:
            logger.error(f"Error getting review: {e}")
            return None

    def _parse_review_response(self, content: str) -> Optional[List[Dict]]:
        """Try multiple approaches to parse the review response."""
        # Try direct JSON parsing first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass

        # Try finding JSON block in text
        try:
            json_match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", content)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [data]
        except (json.JSONDecodeError, AttributeError):
            pass

        return None

    def _calculate_review_reward(self, review_data: List[Dict]) -> float:
        """Calculate reward from review scores with fallback mechanisms."""
        if not review_data:
            return 0.5

        total_score = 0
        count = 0

        for review in review_data:
            score = review.get("score")
            if isinstance(score, (int, float)):
                total_score += min(float(score), 10)  # Cap at 10
                count += 1
            else:
                # Try to extract score from review text
                try:
                    text_score = re.search(r"(\d+(?:\.\d+)?)", str(score))
                    if text_score:
                        score_val = float(text_score.group(1))
                        if score_val <= 10:
                            total_score += score_val
                            count += 1
                except (ValueError, AttributeError):
                    continue

        if count == 0:
            return 0.5  # Fallback to middle score

        return total_score / (count * 10)  # Normalize to 0-1

    def _execute_simple_refinement(self, state: MCTSState) -> MCTSState:
        """Fallback refinement when review fails."""
        new_state = MCTSState(
            current_idea=state.current_idea, depth=state.depth + 1, reward=0.5
        )
        return new_state

    def get_action_prompt(
        self,
        action: str,
        state: MCTSState,
        review_criteria: List[Tuple[str, str]] = None,
        context_chunks: List[str] = None,
    ) -> str:
        """Get the prompt for a given action."""
        if action == "retrieve_and_refine":
            context_str = "\n\n".join(
                [
                    f"Excerpt {i+1}:\n{chunk}"
                    for i, chunk in enumerate(context_chunks or [])
                ]
            )
            return self.prompts["ideation_agent"]["refine_with_retrieval"].format(
                current_idea=state.current_idea, retrieved_content=context_str
            )
        elif action == "review_and_refine":
            feedback_str = "\n".join(
                [f"- {crit}: {feedback}" for crit, feedback in review_criteria]
            )
            return self.prompts["ideation_agent"]["refine_with_review"].format(
                current_idea=state.current_idea, review_feedback=feedback_str
            )
        elif action == "generate":
            return self.prompts["ideation_agent"]["generate"].format(
                research_topic=state.current_idea
            )
        raise ValueError(f"Unknown action: {action}")

    def calculate_reward(self, state: MCTSState) -> float:
        """Calculate reward for a given state."""
        # If the state has an average_score, use that directly
        if hasattr(state, "average_score") and state.average_score > 0:
            return state.average_score / 10.0  # Normalize to 0-1
            
        # Otherwise, use the reward already calculated or a default based on depth
        if state.reward > 0:
            return state.reward
            
        # Fallback to depth-based reward as a last resort
        return 1.0 / (state.depth + 1)

    def run(
        self, initial_state: MCTSState, num_iterations: int, callback=None
    ) -> MCTSNode:
        """Run MCTS for given number of iterations."""
        root = MCTSNode(state=initial_state)

        for i in range(num_iterations):
            self.current_rollout_id = i
            if callback:
                callback(f"Starting iteration {i+1}/{num_iterations}")

            # Selection
            path = self._select(root)
            node = path[-1]  # Get the last node from the path
            if callback:
                callback(f"Selected node with idea: {node.state.current_idea}")

            # Expansion
            self._expand(node)  # _expand modifies node in place
            if callback:
                callback(f"Expanded with action: {node.action_taken}")

            # Simulation
            simulation_path = self._simulate(node)
            reward = self.calculate_reward(
                simulation_path[-1].state if simulation_path else node.state
            )
            if callback:
                callback(f"Simulation complete. Reward: {reward}")

            # Backpropagation
            self._backpropagate(path + simulation_path, reward)
            if callback:
                callback(f"Backpropagation complete for iteration {i+1}")

        return root

    def _save_progress(self, root: MCTSNode, iteration: int) -> None:
        """Save MCTS progress to disk."""
        save_path = self.results_dir / f"mcts_state_{iteration}.json"
        root.save_to_file(str(save_path))

    def _save_action_result(
        self, state: MCTSState, action: str, response_content: str, new_state: MCTSState
    ) -> None:
        """Save intermediate results to disk."""
        if self.config["experiment"]["save_intermediate"]:
            result_path = self.results_dir / f"iteration_{self.iteration}"
            result_path.mkdir(exist_ok=True)

            result = {
                "action": action,
                "previous_state": state.to_dict(),
                "response": response_content,
                "new_state": new_state.to_dict(),
            }

            with open(result_path / f"step_{state.depth}.json", "w") as f:
                json.dump(result, f, indent=2)

    def _generate_retrieval_queries(self, idea: str) -> Optional[List[str]]:
        """Generate search queries for paper retrieval."""
        try:
            # Use execute_action instead of chat directly
            response = self.ideation_agent.execute_action(
                "generate_queries",
                {
                    "current_idea": idea,
                    "prompt": self.prompts["retrieval_agent"]["generate_query"],
                },
            )

            # Try to parse JSON response
            try:
                queries_data = json.loads(response["content"])
                if isinstance(queries_data, dict) and "queries" in queries_data:
                    return queries_data["queries"][:3]  # Take top 3 queries
                return None
            except json.JSONDecodeError:
                logger.warning("Failed to parse queries as JSON")
                return None

        except Exception as e:
            logger.error(f"Error generating queries: {e}")
            return None

    def _retrieve_and_process_papers(self, queries: List[str]) -> List[Dict]:
        """Retrieve and process papers for each query."""
        all_chunks = []
        seen_papers: Set[str] = set()

        for query in queries:
            try:
                # Search S2 API
                papers = self._search_semantic_scholar(query)

                for paper in papers:
                    paper_id = paper["paperId"]
                    if paper_id in seen_papers:
                        continue
                    seen_papers.add(paper_id)

                    # Try to get PDF if available
                    if paper.get("isOpenAccess"):
                        pdf_path = self._download_pdf(
                            paper_id, paper.get("openAccessPdf", {}).get("url")
                        )
                        if pdf_path:
                            # Process PDF with Grobid
                            json_path = self._process_with_grobid(pdf_path)
                            if json_path:
                                chunks = self._chunk_paper(json_path)
                                all_chunks.extend(chunks)
                                continue

                    # Fallback to using abstract
                    if paper.get("abstract"):
                        all_chunks.append(
                            {
                                "text": paper["abstract"],
                                "paper_id": paper_id,
                                "section": "abstract",
                            }
                        )

            except Exception as e:
                logger.error(f"Error processing query '{query}': {e}")
                continue

        return all_chunks

    def _search_semantic_scholar(self, query: str, limit: int = 5) -> List[Dict]:
        """Search Semantic Scholar API."""
        try:
            params = {
                "query": query,
                "limit": limit,
                "fields": "paperId,title,abstract,isOpenAccess,openAccessPdf",
            }
            response = requests.get(
                f"{self.s2_api_url}/paper/search",
                headers=self.s2_headers,
                params=params,
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Semantic Scholar API error: {e}")
            return []

    def _download_pdf(self, paper_id: str, pdf_url: Optional[str]) -> Optional[Path]:
        """Download PDF if available."""
        if not pdf_url:
            return None

        try:
            pdf_path = self.retrieved_dir / f"{paper_id}.pdf"
            if pdf_path.exists():
                return pdf_path

            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return pdf_path

        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return None

    def _process_with_grobid(self, pdf_path: Path) -> Optional[Path]:
        """Process PDF with Grobid."""
        try:
            output_path = self.grobid_dir / f"{pdf_path.stem}.json"
            if output_path.exists():
                return output_path

            # Call s2orc-doc2json (assuming it's installed and in PATH)
            subprocess.run(
                [
                    "python",
                    "-m",
                    "doc2json.grobid2json.process_pdf",
                    str(pdf_path),
                    str(self.grobid_dir),
                ],
                check=True,
            )

            return output_path

        except Exception as e:
            logger.error(f"Error processing with Grobid: {e}")
            return None

    def _chunk_paper(self, json_path: Path, chunk_size: int = 250) -> List[Dict]:
        """Chunk processed paper into sections."""
        try:
            with open(json_path) as f:
                paper_data = json.load(f)

            chunks = []
            for section in paper_data.get("body_text", []):
                words = section["text"].split()
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i : i + chunk_size])
                    chunks.append(
                        {
                            "text": chunk,
                            "paper_id": paper_data.get("paper_id"),
                            "section": section.get("section"),
                        }
                    )

            return chunks

        except Exception as e:
            logger.error(f"Error chunking paper: {e}")
            return []

    def _select_context_chunks(
        self, chunks: List[Dict], n_chunks: int = 5
    ) -> List[str]:
        """Select chunks to use as context (simple random selection for now)."""
        if not chunks:
            return []
        selected = random.sample(chunks, min(n_chunks, len(chunks)))
        return [chunk["text"] for chunk in selected]
