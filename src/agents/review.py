import json
import re
import yaml
import logging
from typing import Dict, Any, List, Optional, Tuple
from .base import BaseAgent
import numpy as np
import retry
import litellm
from .prompts import REVIEW_SYSTEM_PROMPT, REVIEW_SINGLE_ASPECT_PROMPT, UNIFIED_REVIEW_PROMPT

logger = logging.getLogger(__name__)

class ReviewAgent(BaseAgent):
    """Agent for reviewing research ideas."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize with configuration."""
        super().__init__(config_path)
# self.model = self.config["review_agent"].get("model", "gemini/gemini-2.0-flash-lite")
        self.model = self.config["review_agent"].get("model", "gemini/gemini-2.0-flash")
        # self.model = self.config["ideation_agent"].get("model", "gemini/gemini-2.0-flash")
        # Add default weights for scoring
        self.aspect_weights = {
            "novelty": 0.2,
            "clarity": 0.2,
            "feasibility": 0.2,
            "effectiveness": 0.2,
            "impact": 0.2
        }

        # Add trajectory-level memory
        self.prior_feedback = []  # Memory of prior feedback
        self.reviewed_aspects = []  # Memory of recently reviewed aspects
        self.memory_size = 3  # Keep last 3 items

    def record_feedback(self, feedback: Dict[str, Any]):
        """Record feedback in memory"""
        # Store key aspects of feedback
        feedback_summary = {
            "aspects": list(feedback.get("scores", {}).keys()),
            "low_scoring": [k for k, v in feedback.get("scores", {}).items() if v < 6],
            "average_score": feedback.get("average_score", 0)
        }
        
        self.prior_feedback.append(feedback_summary)
        if len(self.prior_feedback) > self.memory_size:
            self.prior_feedback.pop(0)
        
        # Track reviewed aspects
        self.reviewed_aspects.extend(feedback_summary["aspects"])
        if len(self.reviewed_aspects) > self.memory_size * 5:  # Keep more aspects
            self.reviewed_aspects = self.reviewed_aspects[-self.memory_size * 5:]
    
    def get_memory_context(self) -> Dict[str, Any]:
        """Get memory context for focused review"""
        return {
            "prior_feedback": self.prior_feedback[-self.memory_size:],
            "recently_reviewed": list(set(self.reviewed_aspects[-10:])),  # Last 10 unique aspects
            "focus_areas": self._get_focus_areas()
        }
    
    def _get_focus_areas(self) -> List[str]:
        """Identify areas that need focus based on memory"""
        focus_areas = []
        
        # Find consistently low-scoring aspects
        aspect_scores = {}
        for feedback in self.prior_feedback:
            for aspect in feedback.get("low_scoring", []):
                aspect_scores[aspect] = aspect_scores.get(aspect, 0) + 1
        
        # Focus on aspects that have been consistently problematic
        for aspect, count in aspect_scores.items():
            if count >= 2:  # Appeared as low-scoring at least twice
                focus_areas.append(aspect)
        
        return focus_areas

    def set_aspect_weights(self, weights: Dict[str, float]) -> None:
        """Update the weights for different aspects. Weights should sum to 1."""
        # Validate weights
        if not all(aspect in weights for aspect in self.aspect_weights.keys()):
            logger.warning("Missing aspects in weights, using default weights")
            return
        if abs(sum(weights.values()) - 1.0) > 0.001:  # Allow small floating point difference
            logger.warning("Weights don't sum to 1, normalizing...")
            total = sum(weights.values())
            weights = {k: v/total for k, v in weights.items()}
        self.aspect_weights = weights
    
    @retry.retry(tries=3, delay=2)
    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat request to the model."""
        try:
            response = litellm.completion(messages=messages, model=self.model)
            import time
            time.sleep(2)
            return response
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise
    
    def _get_aspect_description(self, aspect: str) -> str:
        """Get description for a specific review aspect."""
        descriptions = {
            "novelty": "Evaluate how original and innovative the idea is compared to existing work.",
            "clarity": "Assess how well-defined, understandable, and precisely communicated the idea is.",
            "feasibility": "Determine if the idea is technically practical within current capabilities and constraints.",
            "effectiveness": "Evaluate how well the proposed approach might solve the stated problem.",
            "impact": "Assess the potential scientific and practical significance if the idea is successfully implemented."
        }
        return descriptions.get(aspect, "")
    
    def unified_review(self, idea: str) -> Dict[str, Any]:
        """Review all aspects of an idea in a single call and compute the weighted average score."""
        try:
            # Get memory context
            memory_context = self.get_memory_context()
            # Use the unified review prompt template from prompts.py
            prompt = UNIFIED_REVIEW_PROMPT.format(research_idea=idea)

            # Add memory context for focused review
            memory_prompt = ""
            if memory_context["focus_areas"]:
                memory_prompt = f"\n\nFocus particularly on these previously problematic aspects: {', '.join(memory_context['focus_areas'])}"
            
            if memory_context["recently_reviewed"]:
                memory_prompt += f"\n\nRecently reviewed aspects: {', '.join(memory_context['recently_reviewed'])}"
            
            prompt += memory_prompt
            
            # Prepare messages for the chat
            messages = [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            # Execute the chat
            response = self.chat(messages)
            content = response.choices[0].message.content
            
            # Parse the response
            parsed_data = self.parse_unified_review(content)
            
            # Calculate the weighted average score from individual scores
            if "scores" in parsed_data and parsed_data["scores"]:
                scores = parsed_data["scores"]
                valid_scores = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
                if valid_scores:
                    weighted_avg = sum(v * self.aspect_weights[k] for k, v in valid_scores.items())
                    parsed_data["average_score"] = weighted_avg
                    # Print scores and weighted average for verification
                    print("\n=== Review Scores ===")
                    print("Individual scores:")
                    for aspect, score in valid_scores.items():
                        print(f"{aspect}: {score} (weight: {self.aspect_weights[aspect]})")
                    print(f"Weighted average: {weighted_avg:.2f}")
            return parsed_data
            
        except Exception as e:
            logger.exception(f"Error in unified review: {e}")
            return {
                "scores": {},
                "reviews": {},
                "average_score": 5.0
            }
    
    def parse_unified_review(self, response: str) -> Dict[str, Any]:
        """Parse the unified review response using direct string extraction.
        
        This uses a more robust approach similar to ideation.py's refresh_idea
        to extract scores and reviews directly from the text.
        """
        result = {
            "scores": {},
            "reviews": {}
        }
        
        try:
            # Method 1: Try to parse as JSON first (simplest case)
            data = self._extract_json_data(response)
            if data and isinstance(data, dict):
                # Extract scores and reviews
                if "scores" in data:
                    result["scores"] = data["scores"]
                elif "ratings" in data:
                    result["scores"] = data["ratings"]
                
                if "reviews" in data:
                    result["reviews"] = data["reviews"]
                elif "feedback" in data:
                    result["reviews"] = data["feedback"]
                
                # If we got valid data, return it
                if result["scores"] and len(result["scores"]) > 0:
                    print(f"Successfully parsed JSON for review scores: {list(result['scores'].keys())}")
                    return result
        
        except Exception as e:
            print(f"JSON parsing failed: {e}")
        
        print("Direct JSON parsing failed, using string extraction methods")
        
        # Method 2: Direct string extraction for structured JSON
        try:
            aspects = ["novelty", "clarity", "feasibility", "effectiveness", "impact"]
            
            # Look for scores section using direct string search
            if '"scores"' in response:
                scores_start = response.find('"scores"') + len('"scores"')
                scores_start = response.find('{', scores_start) + 1
                scores_end = -1
                brace_count = 1
                
                # Find the matching closing brace
                for i in range(scores_start, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            scores_end = i
                            break
                
                if scores_end > scores_start:
                    scores_text = response[scores_start:scores_end]
                    print(f"Found scores section: {scores_text}")
                    
                    # Extract individual scores using direct string search
                    for aspect in aspects:
                        aspect_pattern = f'"{aspect}"\\s*:\\s*(\\d+(?:\\.\\d+)?)'
                        score_match = re.search(aspect_pattern, scores_text, re.IGNORECASE)
                        if score_match:
                            result["scores"][aspect] = float(score_match.group(1))
            
            # Look for reviews section
            if '"reviews"' in response:
                reviews_start = response.find('"reviews"') + len('"reviews"')
                reviews_start = response.find('{', reviews_start) + 1
                reviews_end = -1
                brace_count = 1
                
                # Find the matching closing brace
                for i in range(reviews_start, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            reviews_end = i
                            break
                
                if reviews_end > reviews_start:
                    reviews_text = response[reviews_start:reviews_end]
                    print(f"Found reviews section")
                    
                    # Extract individual reviews
                    for aspect in aspects:
                        review_pattern = f'"{aspect}"\\s*:\\s*"([^"]+)"'
                        review_match = re.search(review_pattern, reviews_text, re.IGNORECASE)
                        if review_match:
                            review_text = review_match.group(1)
                            # Clean up escaping
                            review_text = review_text.replace('\\"', '"').replace('\\n', '\n')
                            result["reviews"][aspect] = review_text
            
        except Exception as e:
            print(f"String extraction for JSON structure failed: {e}")
        
        # Method 3: Extract individual scores and reviews directly when no JSON structure is found
        if not result["scores"]:
            print("Trying direct extraction of scores and reviews from text")
            try:
                aspects = ["novelty", "clarity", "feasibility", "effectiveness", "impact"]
                
                for aspect in aspects:
                    # Look for score pattern like "novelty: 7" or "novelty score: 7"
                    patterns = [
                        rf"{aspect}(?:\s+score)?:\s*(\d+(?:\.\d+)?)",
                        rf"{aspect}:.*?(\d+(?:\.\d+)?)\s*\/\s*10",
                        rf"{aspect}.*?score.*?(\d+(?:\.\d+)?)"
                    ]
                    
                    for pattern in patterns:
                        score_match = re.search(pattern, response, re.IGNORECASE)
                        if score_match:
                            try:
                                result["scores"][aspect] = float(score_match.group(1))
                                break
                            except (ValueError, IndexError):
                                pass
                    
                    # Look for review text patterns
                    review_patterns = [
                        rf"{aspect}(?:\s+review)?:\s*(.*?)(?=\n\n|\n[a-z]+(?:\s+(?:score|review))?:|\Z)",
                        rf"{aspect}:.*?\n(.*?)(?=\n\n|\n[a-z]+(?:\s+(?:score|review))?:|\Z)"
                    ]
                    
                    for pattern in review_patterns:
                        review_match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                        if review_match:
                            result["reviews"][aspect] = review_match.group(1).strip()
                            break
            
            except Exception as e:
                print(f"Direct text extraction failed: {e}")
                
        # Count how many scores we successfully parsed
        score_count = len(result["scores"])
        review_count = len(result["reviews"])
        print(f"Extracted {score_count} scores and {review_count} reviews")
            
        return result
    
    def _extract_json_data(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from text using multiple approaches."""
        # Method 1: Try direct JSON parsing
        try:
            # Clean up potential non-JSON prefix/suffix
            potential_json = text.strip()
            # Find the first opening brace
            first_brace = potential_json.find('{')
            if first_brace != -1:
                potential_json = potential_json[first_brace:]
                # Find the matching closing brace
                brace_count = 0
                for i, char in enumerate(potential_json):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            potential_json = potential_json[:i+1]
                            break
                
                return json.loads(potential_json)
        except json.JSONDecodeError:
            pass
        
        # Method 2: Look for JSON code block
        json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        match = re.search(json_block_pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
                
        # Method 3: Find JSON object with balanced braces
        try:
            start_idx = text.find("{")
            if start_idx != -1:
                # Find the balanced closing bracket
                open_count = 0
                close_idx = -1
                for i in range(start_idx, len(text)):
                    if text[i] == "{":
                        open_count += 1
                    elif text[i] == "}":
                        open_count -= 1
                        if open_count == 0:
                            close_idx = i
                            break
                if close_idx != -1:
                    json_str = text[start_idx : close_idx + 1]
                    return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            pass
            
        return None
    
    def act(self, state: Dict) -> Dict:
        """Implement the abstract method from BaseAgent.
        
        Perform a review action based on the current state."""
        if not state.get("current_idea"):
            return {"error": "No idea provided for review"}
        
        return self.unified_review(state["current_idea"])
    
    def update_state(self, action_result: Dict) -> None:
        """Implement the abstract method from BaseAgent.
        
        Update internal state based on review results."""
        # Store the latest review result in the state
        self.state["latest_review"] = action_result
        
        # Accumulate review history
        if "review_history" not in self.state:
            self.state["review_history"] = []
        self.state["review_history"].append(action_result)
        
        # Track average scores over time
        if "average_scores" not in self.state:
            self.state["average_scores"] = []
        
        if "average_score" in action_result:
            self.state["average_scores"].append(action_result["average_score"])
