import yaml
from pathlib import Path
from loguru import logger
import json
import re
import time
from typing import Dict, Any, Optional, List, Tuple
import os
import retry
import litellm
from .prompts import REVIEW_SINGLE_ASPECT_PROMPT


class StructuredReviewAgent:
    """Agent responsible for generating structured reviews of research ideas."""

    def __init__(self, config_path: str):
        """Initialize the structured review agent."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Get model configuration 
        # self.model = self.config["ideation_agent"].get("model", "gemini/gemini-2.0-flash")
        self.model = self.config["review_agent"].get("model", "gemini/gemini-2.0-flash")

        # New taxonomy of review aspects
        self.review_aspects = [
            "lack_of_novelty",
            "assumptions",
            "vagueness",
            "feasibility_and_practicality",
            "overgeneralization",
            "overstatement",
            "evaluation_and_validation_issues",
            "justification_for_methods",
            "reproducibility",
            "contradictory_statements",
            "impact",
            "alignment",
            "ethical_and_social_considerations",
            "robustness",
        ]

        # New aspect descriptions
        self.aspect_descriptions = {
            "lack_of_novelty": "The idea does not introduce a significant or meaningful advancement over existing work, lacking originality or innovation. Consider: Does the idea merely extend known concepts without offering a fresh perspective?",
            "assumptions": "The idea relies on untested or unrealistic assumptions that may weaken its validity or applicability. Consider: Are the assumptions reasonable and supported by evidence? Are they necessary for the core argument?",
            "vagueness": "The idea is presented in an unclear or ambiguous manner, making it difficult to understand its core components or contributions. Consider: Are the objectives, methods, and results clearly defined and articulated?",
            "feasibility_and_practicality": "The idea is not practical or achievable given current technological, theoretical, or resource constraints. Consider: Is the proposed approach realistic within the given context? Are resource requirements justified?",
            "overgeneralization": "The idea extends its conclusions or applicability beyond the scope of the context provided. Consider: Are the claims properly bounded by the data or analysis? Are limitations acknowledged?",
            "overstatement": "The idea exaggerates its claims, significance, or potential impact beyond what is supported by evidence or reasoning. Consider: Are the claims proportionate to the supporting data and analysis?",
            "evaluation_and_validation_issues": "The idea lacks rigorous evaluation methods, such as insufficient benchmarks, inadequate baselines, or poorly defined success metrics. Consider: Are the evaluation criteria appropriate, comprehensive, and fair?",
            "justification_for_methods": "The idea does not provide sufficient reasoning or evidence to explain why specific methods, techniques, or approaches were chosen. Consider: Are alternative approaches discussed and ruled out with justification?",
            "reproducibility": "The idea does not provide sufficient detail or transparency to allow others to replicate or verify its findings. Consider: Are the methods, data, and analysis steps described thoroughly and unambiguously?",
            "contradictory_statements": "The idea contains internal inconsistencies or conflicts in its assumptions, methods, or conclusions. Consider: Are there contradictions that undermine the coherence or validity of the work?",
            "impact": "The idea is not impactful or significant. It does not solve a real problem or create value. Consider: Does the idea address an important challenge, offer practical benefits, or provide a foundation for future work? Is it scalable, adaptable, and sustainable?",
            "alignment": "The idea is not aligned with the problem statement and its objectives. Consider: Is the proposal consistently focused on addressing the stated problem? Are the methods and outcomes in sync with the research goals?",
            "ethical_and_social_considerations": "The idea does not adhere to ethical standards and may be harmful to individuals, communities, or the environment. Consider: Are potential risks, biases, and ethical implications identified and mitigated?",
            "robustness": "The solution is not resilient to variations in input data, assumptions, or environmental conditions. Consider: Does the approach perform reliably under different scenarios? Are failure modes explored and addressed?",
        }


    @retry.retry(tries=3, delay=2)
    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat request to the model."""
        try:
            response = litellm.completion(messages=messages, model=self.model)
            import time as t
            t.sleep(2)
            return response
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise

    @retry.retry(tries=3, delay=2)
    def review_aspect(self, idea: str, aspect: str) -> Dict[str, Any]:
        """Generate a review for a specific aspect of a research idea with retries."""
        # Use the single aspect prompt
        aspect_description = self.aspect_descriptions.get(aspect, "")
        system_prompt = REVIEW_SINGLE_ASPECT_PROMPT.format(
            aspect=aspect,
            aspect_description=aspect_description,
            research_idea=idea
        )

        user_prompt = f"""Please review this research idea focusing on the aspect of {aspect}:

{idea}

Remember to return a valid JSON object with a single highlight as specified."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        response = self.chat(messages)
        content = response.choices[0].message.content

        # Parse the response to get JSON
        review_data = self._extract_json_data(content)
        
        # Simple string matching in case the highlighted text isn't an exact match
        if "highlight" in review_data and "text" in review_data["highlight"]:
            text = review_data["highlight"]["text"]
            if text not in idea:
                review_data["highlight"]["text"] = self._find_closest_text(text, idea)
            
        # Print the final review data for debugging
        print(f"\n--- PARSED REVIEW DATA ---\nAspect: {review_data.get('aspect')}")
        # print(f"Score: {review_data.get('score')}")
        # print(f"Summary: {review_data.get('summary')}")
        print(f"Highlight Text: '{review_data.get('highlight', {}).get('text', '')}'")
        # print(f"Category: {review_data.get('highlight', {}).get('category', '')}")
        # print(f"Review: {review_data.get('highlight', {}).get('review', '')}")

        return review_data

    def _find_closest_text(self, text: str, original_text: str) -> str:
        """Find the closest matching text in the original text using simple matching."""
        # Case-insensitive match
        text_lower = text.lower()
        original_lower = original_text.lower()
        
        if text_lower in original_lower:
            start = original_lower.find(text_lower)
            return original_text[start:start + len(text)]
            
        # Find the largest common substring
        import difflib
        s = difflib.SequenceMatcher(None, text, original_text)
        match = s.find_longest_match(0, len(text), 0, len(original_text))
        if match.size > len(text) * 0.6:  # 60% of the text is matching
            return original_text[match.b:match.b + match.size]
            
        # Return original as fallback
        return text

    def review_idea_step_by_step(self, idea: str, start_aspect_index: int = 0) -> Dict[str, Any]:
        """Review a research idea one aspect at a time, starting from the specified aspect index."""
        if start_aspect_index >= len(self.review_aspects):
            return {"complete": True, "message": "All aspects reviewed"}

        current_aspect = self.review_aspects[start_aspect_index]
        review_data = self.review_aspect(idea, current_aspect)

        return {
            "complete": False,
            "current_aspect_index": start_aspect_index,
            "current_aspect": current_aspect,
            "review_data": review_data,
            "total_aspects": len(self.review_aspects),
            "next_aspect_index": start_aspect_index + 1,
            "next_aspect": (
                self.review_aspects[start_aspect_index + 1]
                if start_aspect_index + 1 < len(self.review_aspects)
                else None
            ),
        }

    def _extract_json_data(self, text: str) -> Dict[str, Any]:
        """Extract JSON data from text using multiple approaches."""
        # Method 1: Try direct JSON parsing
        try:
            return json.loads(text)
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

        # If we get here, something went wrong - return simple structure to show the raw response
        return {
            "aspect": "error",
            "score": 0,
            "highlight": {
                "text": "Error parsing response",
                "category": "Error",
                "review": f"Could not parse JSON from response: {text[:100]}..."
            },
            "summary": "Error parsing LLM response"
        }
