import yaml
from pathlib import Path
from loguru import logger
import json
import re
import retry
import random
from typing import Dict, Any, Optional, List, Tuple
import os
# from google import genai
from .base import BaseAgent
from .prompts import (
    IDEATION_SYSTEM_PROMPT,
    IDEATION_GENERATE_PROMPT,
    IDEATION_REFRESH_APPROACH_PROMPT,
    IDEATION_REFINE_WITH_RETRIEVAL_PROMPT,
    IDEATION_GENERATE_QUERY_PROMPT,
    IDEATION_IMPROVE_WITH_FEEDBACK_PROMPT,
    IDEATION_DIRECT_FEEDBACK_PROMPT,
)
import litellm


class IdeationAgent(BaseAgent):
    """Agent responsible for generating and refining research ideas."""

    def __init__(self, config_path: str):
        """Initialize the ideation agent."""
        super().__init__(config_path)
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Get model configuration
        # self.model = self.config["ideation_agent"].get("model", "gemini/gemini-2.0-flash-lite")
        self.model = self.config["ideation_agent"].get("model", "gemini/gemini-2.0-flash")
        # self.model = "gemini/gemini-2.0-flash"
        print(f"Using model: {self.model}")

        # Add trajectory-level memory
        self.generated_briefs = []  # Memory of generated briefs
        self.recent_approaches = []  # Memory of recent approaches
        self.memory_size = 3  # Keep last 3 items

    def record_brief(self, brief: str):
        """Record a generated brief in memory"""
        self.generated_briefs.append(brief[:200])  # Store first 200 chars
        if len(self.generated_briefs) > self.memory_size:
            self.generated_briefs.pop(0)
    
    def get_memory_context(self) -> str:
        """Get memory context for non-redundant generation"""
        if not self.generated_briefs:
            return ""
        
        context = "Previous approaches to avoid redundancy:\n"
        for i, brief in enumerate(self.generated_briefs, 1):
            context += f"{i}. {brief}...\n"
        
        return context

    @retry.retry(tries=3, delay=2)
    def chat(self, model: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat request to the model."""
        try:
            response = litellm.completion(messages=messages, model=model)
            import time as t
            t.sleep(2)
            return response
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise

    def act(self, state: Dict) -> Dict:
        """Implementation of abstract method from BaseAgent."""
        action_type = state.get("action_type", "execute")
        if action_type == "execute":
            return self.execute_action(state.get("action"), state)
        raise ValueError(f"Unknown action type: {action_type}")

    def update_state(self, action_result: Dict) -> None:
        """Implementation of abstract method from BaseAgent."""
        self.state.update(action_result)
        self.messages.append(
            {"role": "assistant", "content": action_result.get("content", "")}
        )

    def execute_action(self, action: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific ideation action based on the current state."""
        try:
            # Add memory context to state
            if hasattr(state.get('current_state'), 'get_memory_context'):
                memory_context = state['current_state'].get_memory_context()
                state['memory_context'] = memory_context
            
            prompt = self._get_action_prompt(action, state)

            messages = [
                {"role": "system", "content": IDEATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            # if action != "generate_query":
            response = self.chat(model=self.model, messages=messages)
            content = response.choices[0].message.content

            # For debugging: print the raw LLM output to the terminal
            print(f"\n===== RAW LLM OUTPUT FOR {action} =====")
            print(content)
            print("=====================================\n")

            # Record the brief if it's a generation action
            if action == "generate":
                self.record_brief(content)
            
            # For query generation, use specialized extraction
            if action == "generate_query":
                query = self._extract_query(content)
                #query = "Transformer attention irrelevant context long-context modeling key information retrieval hallucination mitigation in-context learning robustness activation outliers"
                print(f"\n===== EXTRACTED QUERY =====")
                print(f"Query: {query}")
                print("============================\n")
                
                if query:
                    return {"content": query}
                else:
                    logger.warning("Could not extract query from response")
                    return {"content": content}

            # Try to extract structured data from the response
            parsed_data = self._extract_json_data(content)
            
            # If we successfully extracted structured JSON data
            if parsed_data:
                # Format to ensure consistent field naming
                result = self._format_structured_idea(parsed_data)
                # Store both parsed and raw output
                result["raw_llm_output"] = content
                return result
            
            # If no JSON structure was found, return the raw content
            logger.warning("Could not extract structured data from response")
            return {"title": "Untitled Research Idea", "content": content, "raw_llm_output": content}

        except Exception as e:
            logger.error(f"Error executing action {action}: {e}")
            return {
                "title": "Error in Idea Generation",
                "content": f"Failed to generate idea with action {action}: {str(e)}",
                "raw_llm_output": ""
            }

    def _format_structured_idea(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format extracted JSON data into a consistent structure."""
        result = {
            "title": data.get("title", "Untitled Research Idea"),
            "content": ""
        }
        
        # If we have proposed_method, experiment_plan, and test_case_examples fields
        # Format them as markdown in the content field
        if "proposed_method" in data or "experiment_plan" in data or "test_case_examples" in data:
            # Start with the title as header
            content_parts = [f"# {result['title']}\n\n"]
            
            # Add proposed method if available
            if "proposed_method" in data:
                content_parts.append(f"## Proposed Method\n\n{data['proposed_method']}\n\n")
            
            # Add experiment plan if available
            if "experiment_plan" in data:
                content_parts.append(f"## Experiment Plan\n\n{data['experiment_plan']}\n\n")
            
            # Add test cases if available
            if "test_case_examples" in data:
                content_parts.append(f"## Test Case Examples\n\n{data['test_case_examples']}\n\n")
            
            # Set the content field to the formatted markdown
            result["content"] = "".join(content_parts)
        # If we only have a content field, use it directly
        elif "content" in data:
            result["content"] = data["content"]
        
        return result

    def _extract_json_data(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from text using multiple approaches.
        
        Enhanced to better handle the specific JSON structure we expect 
        for research idea generation.
        """
        # Method 1: Try direct JSON parsing of the entire response
        try:
            potential_json = text.strip()
            # Skip any non-JSON prefix text
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
                
                # Try to parse this JSON substring
                data = json.loads(potential_json)
                print(f"Successfully parsed JSON directly, found fields: {list(data.keys())}")
                return data
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Direct JSON parsing failed: {e}")
        
        # Method 2: Look for JSON code blocks
        json_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1).strip()
                data = json.loads(json_str)
                print(f"Found JSON block via regex, with fields: {list(data.keys())}")
                return data
            except json.JSONDecodeError as e:
                print(f"JSON block parsing failed: {e}")
        
        # Method 3: Search for specific JSON field patterns and extract their values
        # try:
        #     # Regex to find JSON structure with our expected fields
        #     fields = {}
            
        #     # Extract title
        #     title_match = re.search(r'"title"\s*:\s*"([^"]+)"', text)
        #     if title_match:
        #         fields["title"] = title_match.group(1)
                
        #     # Extract proposed method
        #     method_match = re.search(r'"proposed_method"\s*:\s*"((?:[^"\\]|\\"|\\\\)*)"', text, re.DOTALL)
        #     if method_match:
        #         fields["proposed_method"] = method_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                
        #     # Extract experiment plan
        #     plan_match = re.search(r'"experiment_plan"\s*:\s*"((?:[^"\\]|\\"|\\\\)*)"', text, re.DOTALL)
        #     if plan_match:
        #         fields["experiment_plan"] = plan_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                
        #     # Extract test case examples
        #     examples_match = re.search(r'"test_case_examples"\s*:\s*"((?:[^"\\]|\\"|\\\\)*)"', text, re.DOTALL)
        #     if examples_match:
        #         fields["test_case_examples"] = examples_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                
        #     # Extract general content field as fallback
        #     content_match = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\"|\\\\)*)"', text, re.DOTALL)
        #     if content_match:
        #         fields["content"] = content_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
            
        #     # If we found any of our expected fields, return them
        #     if fields:
        #         print(f"Extracted fields via regex: {list(fields.keys())}")
        #         return fields
        # except Exception as e:
        #     print(f"Field extraction failed: {e}")
        
        # Method 4: Direct string extraction using simple start and end markers 
        # (more reliable than regex with complex escape sequences)
        structured_data = {}
        try:
            # Extract title
            if '"title"' in text:
                title_start = text.find('"title"') + len('"title"')
                # Find the colon after "title"
                title_start = text.find(':', title_start) + 1
                # Find the opening quote after the colon
                title_start = text.find('"', title_start) + 1
                # Find the closing quote
                title_end = text.find('"', title_start)
                if title_end > title_start:
                    structured_data["title"] = text[title_start:title_end]
                    # print(f"Found title using direct string search: {structured_data['title']}")

            # Extract proposed_method - looking for text after "proposed_method": " and up till next field
            if '"proposed_method"' in text:
                method_start = text.find('"proposed_method"') + len('"proposed_method"')
                # Find the colon after "proposed_method"
                method_start = text.find(':', method_start) + 1
                # Find the opening quote after the colon
                method_start = text.find('"', method_start) + 1
                
                # For the end, look for the next field or the closing brace
                if '"experiment_plan"' in text[method_start:]:
                    # Find the end by locating the next field
                    pattern_end = text.find('"experiment_plan"', method_start)
                    # print(f"pattern_end: {pattern_end}")
                    if pattern_end > method_start:
                        structured_data["proposed_method"] = text[method_start:pattern_end]
                        # print(f"Found proposed_method using direct string search: {structured_data['proposed_method']}")
                else:
                    # If no next field, look for closing quote + comma or closing quote + }
                    for end_pattern in ['",', '"}']:
                        pattern_end = text.find(end_pattern, method_start)
                        if pattern_end > method_start:
                            structured_data["proposed_method"] = text[method_start:pattern_end]
                            break

            # Extract experiment_plan
            if '"experiment_plan"' in text:
                plan_start = text.find('"experiment_plan"') + len('"experiment_plan"')
                # Find the colon after "experiment_plan"
                plan_start = text.find(':', plan_start) + 1
                # Find the opening quote after the colon
                plan_start = text.find('"', plan_start) + 1
                
                # For the end, look for the next field or closing brace
                for end_pattern in ['"}', '"\n}', ',\n}', '\n}', '"\\n}', '}']:
                    pattern_end = text.find(end_pattern, plan_start)
                    if pattern_end > plan_start:
                        structured_data["experiment_plan"] = text[plan_start:pattern_end]
                        break

            # Fix any special characters in extracted fields
            for key in structured_data:
                if structured_data[key]:
                    # Replace escaped quotes
                    structured_data[key] = structured_data[key].replace('\\"', '"')
                    # Replace escaped newlines
                    structured_data[key] = structured_data[key].replace('\\n', '\n')
                    # Replace other common escape sequences
                    structured_data[key] = structured_data[key].replace('\\\\', '\\')
                    structured_data[key] = structured_data[key].replace('\\/', '/')

            # Return if we found something useful
            if structured_data and len(structured_data) > 0:
                print(f"Extracted fields using direct string search: {list(structured_data.keys())}")
                return structured_data
        
        except Exception as e:
            print(f"Direct string extraction error: {e}")
        
        # Method 5: Fallback to markdown section extraction
        try:
            # Clean up the text to remove any markdown code blocks
            cleaned_content = re.sub(r"```(?:markdown|json)?\s*", "", text)
            cleaned_content = re.sub(r"```\s*$", "", cleaned_content)
            
            print("Attempting markdown section extraction")
            structured_data = {}
            
            # Look for markdown headers
            headers = re.findall(r'(?:^|\n)#+\s+(.*?)(?:\n|$)', cleaned_content)
            if headers:
                print(f"Found {len(headers)} markdown headers: {headers[:3]}")
                # Use first header as title if available
                structured_data["title"] = headers[0]
            
            # Extract sections based on common headers
            method_section = re.search(r'(?:^|\n)#+\s+(?:Proposed\s+)?Method(?:ology)?[\s:]*\n+(.*?)(?:\n#+\s+|$)', 
                                     cleaned_content, re.IGNORECASE | re.DOTALL)
            if method_section:
                structured_data["proposed_method"] = method_section.group(1).strip()
            
            experiment_section = re.search(r'(?:^|\n)#+\s+(?:Experiment(?:al)?(?:\s+Plan)?|Evaluation)[\s:]*\n+(.*?)(?:\n#+\s+|$)', 
                                         cleaned_content, re.IGNORECASE | re.DOTALL)
            if experiment_section:
                structured_data["experiment_plan"] = experiment_section.group(1).strip()
            
            examples_section = re.search(r'(?:^|\n)#+\s+(?:Test\s+Case\s+Examples|Examples|Use\s+Cases)[\s:]*\n+(.*?)(?:\n#+\s+|$)', 
                                       cleaned_content, re.IGNORECASE | re.DOTALL)
            if examples_section:
                structured_data["test_case_examples"] = examples_section.group(1).strip()
            
            # If we have a structure extracted from markdown sections, return it
            if structured_data and len(structured_data) > 0:
                print(f"Extracted {len(structured_data)} fields from markdown sections")
                return structured_data
            
        except Exception as e:
            print(f"Markdown section extraction error: {e}")
        
        # If all methods fail, return None
        return None

    def _get_action_prompt(self, action: str, state: Dict[str, Any]) -> str:
        """Get the appropriate prompt for the given action."""
        research_goal = state.get("research_goal", "")  # Get research_goal directly
        current_idea = state.get("current_idea", "")
        abstract = state.get("abstract", "")

        if action == "generate":
            # Add memory context to avoid redundancy
            memory_context = self.get_memory_context()
            prompt = IDEATION_GENERATE_PROMPT.format(research_topic=research_goal or current_idea, abstract_section=abstract)
            if memory_context:
                prompt += f"\n\nMemory context (avoid these approaches):\n{memory_context}"
            return prompt
        
        elif action == "generate_query":
            # Add memory context to avoid redundant queries
            memory_context = state.get("memory_context", {})
            memory_prompt = ""
            if memory_context:
                last_query = memory_context.get('last_query')
                if last_query:
                    memory_prompt = f"\n\nPrevious query: {last_query}\nGenerate a different query focusing on other aspects."
            return IDEATION_GENERATE_QUERY_PROMPT.format(research_idea=current_idea) + memory_prompt
        elif action == "refresh_idea":
            # Add memory context to ensure fresh approach
            memory_context = self.get_memory_context()
            memory_prompt = ""
            if memory_context:
                memory_prompt = f"\n\n{memory_context}\n\nGenerate a completely different approach that avoids the above patterns."
            return IDEATION_REFRESH_APPROACH_PROMPT.format(
                research_topic=research_goal,
                current_idea=current_idea,
                abstract_section=abstract
            ) + memory_prompt
        elif action == "review_and_refine":
            # Handle review feedback from state
            accepted_reviews = state.get("review_feedback", [])
            original_raw_output = state.get("original_raw_output")

            # Add memory context for non-redundant refinement
            memory_context = state.get("memory_context", {})
            
            # Format the accepted reviews into a structured feedback string
            review_feedback = []
            for review in accepted_reviews:
                aspect = review.get('aspect', 'general')
                summary = review.get('summary', '')
                score = review.get('score', 0)
                highlight = review.get('highlight', {})
                
                feedback_item = f"Aspect: {aspect.capitalize()} (Score: {score}/10)\n"
                feedback_item += f"Summary: {summary}\n"
                
                if highlight:
                    feedback_item += f"Highlighted text: \"{highlight.get('text', '')}\"\n"
                    feedback_item += f"Specific feedback: {highlight.get('review', '')}\n"
                
                review_feedback.append(feedback_item)
            
            # Join all feedback into a single string
            formatted_feedback = "\n".join(review_feedback)

            # Add memory context to avoid redundant refinements
            memory_prompt = ""
            if memory_context:
                problematic_aspects = memory_context.get('problematic_aspects', [])
                if problematic_aspects:
                    memory_prompt = f"\n\nPreviously addressed aspects (focus on new issues): {', '.join(problematic_aspects[-3:])}"
            
            # Determine which version of the idea to use
            idea_to_improve = original_raw_output if original_raw_output else current_idea
            
            # Custom prompt when using original raw output
            if original_raw_output:
                return f"""ORIGINAL GENERATED RESEARCH IDEA:
        {idea_to_improve}

        REVIEW FEEDBACK:
        {formatted_feedback}

        Please improve the research idea based on the specific feedback provided. Make targeted changes to address each critique while maintaining the original format and structure.

        Return the complete improved idea in the same format as the original.""" + memory_prompt
            else:
                # Use the standard prompt template for formatted ideas
                return IDEATION_IMPROVE_WITH_FEEDBACK_PROMPT.format(
                    idea=idea_to_improve,
                    feedback=formatted_feedback
                ) + memory_prompt

        elif action == "refine_with_retrieval" or action == "retrieve_and_refine":
            # Add memory context to avoid redundant queries
            memory_context = state.get("memory_context", {})
            memory_prompt = ""
            
            if memory_context:
                last_query = memory_context.get('last_query')
                if last_query:
                    memory_prompt = f"\n\nPrevious query (try different approach): {last_query}"
            # Handle both formats: direct retrieved_content parameter or context_chunks 
            if "retrieved_content" in state:
                # Direct content from API endpoint
                retrieved_content = state.get("retrieved_content", "")
                            
            return IDEATION_REFINE_WITH_RETRIEVAL_PROMPT.format(
                current_idea=current_idea, retrieved_content=retrieved_content, abstract_section=abstract
            ) + memory_prompt
        elif action == "process_feedback":
            # Handle user feedback from chat
            user_feedback = state.get("user_feedback", "")
            return IDEATION_DIRECT_FEEDBACK_PROMPT.format(
                current_idea=current_idea, user_feedback=user_feedback
            )
        else:
            raise ValueError(f"Unknown action: {action}")

    def _prepare_retrieval_context(self, idea: str) -> str:
        """Prepare context from retrieved papers."""
        queries = self._generate_retrieval_queries(idea)
        chunks = self._retrieve_and_process_papers(queries)
        return self._select_context_chunks(chunks)

    def _generate_retrieval_queries(self, idea: str) -> List[str]:
        """Generate search queries for retrieval."""
        # Implementation moved from tree.py

    def _retrieve_and_process_papers(self, queries: List[str]) -> List[Dict]:
        """Retrieve and process papers."""
        # Implementation moved from tree.py

    def _select_context_chunks(self, chunks: List[Dict]) -> str:
        """Select and format context chunks."""
        # Implementation moved from tree.py

    def improve_idea(self, idea: str, accepted_reviews: List[Dict[str, Any]], original_raw_output: Optional[str] = None) -> Tuple[str, str]:
        """Improve a research idea based on accepted review feedback.
        
        Args:
            idea: The formatted idea text (parsed/displayed version)
            accepted_reviews: List of review feedback
            original_raw_output: The original unparsed LLM output if available
            
        Returns:
            Tuple of (improved_idea_content, raw_llm_output)
        """
        try:
            # Format the accepted reviews into a structured feedback string
            review_feedback = []
            for review in accepted_reviews:
                aspect = review.get('aspect', 'general')
                summary = review.get('summary', '')
                score = review.get('score', 0)
                highlight = review.get('highlight', {})
                
                feedback_item = f"Aspect: {aspect.capitalize()} (Score: {score}/10)\n"
                feedback_item += f"Summary: {summary}\n"
                
                if highlight:
                    feedback_item += f"Highlighted text: \"{highlight.get('text', '')}\"\n"
                    feedback_item += f"Specific feedback: {highlight.get('review', '')}\n"
                
                review_feedback.append(feedback_item)
            
            # Join all feedback into a single string
            formatted_feedback = "\n".join(review_feedback)
            
            # Determine which version of the idea to use
            idea_to_improve = original_raw_output if original_raw_output else idea
            
            # Custom prompt when using original raw output
            if original_raw_output:
                user_prompt = f"""ORIGINAL GENERATED RESEARCH IDEA:
{idea_to_improve}

REVIEW FEEDBACK:
{formatted_feedback}

Please improve the research idea based on the specific feedback provided. Make targeted changes to address each critique while maintaining the original format and structure.

Return the complete improved idea in the same format as the original."""
            else:
                # Use the standard prompt template for formatted ideas
                # print(f"Improving idea: {idea_to_improve}")
                user_prompt = IDEATION_IMPROVE_WITH_FEEDBACK_PROMPT.format(
                    idea=idea_to_improve,
                    feedback=formatted_feedback
                )
            
            # Call the language model to improve the idea
            messages = [
                {"role": "system", "content": IDEATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.chat(model=self.model, messages=messages)
            new_content = response.choices[0].message.content
            
            print(f"\n===== RAW LLM OUTPUT FOR IMPROVEMENT =====")
            print(new_content)
            print("==========================================\n")
                
            # Clean up the response to remove any markdown code blocks that might have been added
            cleaned_content = re.sub(r"```(?:markdown|json)?\s*", "", new_content)
            cleaned_content = re.sub(r"```\s*$", "", cleaned_content)
            
            # Try to extract JSON if needed
            if not original_raw_output:
                try:
                    # Try to extract structured data 
                    parsed_data = self._extract_json_data(new_content)
                    if parsed_data and "content" in parsed_data:
                        return parsed_data["content"], new_content
                    else:
                        return parsed_data, new_content
                except Exception as e:
                    logger.error(f"Error parsing JSON: {e}")

            try:
                loaded_content = json.loads(cleaned_content)
                return loaded_content["content"], new_content
            except (json.JSONDecodeError, KeyError):
                pass
            
            # Return both the cleaned content and the raw LLM output
            return cleaned_content, new_content
            
        except Exception as e:
            logger.error(f"Error improving idea: {e}")
            # Return the original idea if improvement fails
            error_msg = f"<p>Unable to improve idea: {str(e)}.</p>"
            return f"{error_msg}<p>{idea}</p>", original_raw_output or idea

    def refresh_idea(self, idea: str, original_raw_output: Optional[str] = None) -> Tuple[str, str]:
        """Generate a completely new approach for the same research problem.
        
        Args:
            idea: The formatted idea text (parsed/displayed version)
            original_raw_output: The original unparsed LLM output if available
            
        Returns:
            Tuple of (refreshed_idea_content, raw_llm_output)
        """
        try:
            # Determine which version of the idea to use as input
            idea_to_refresh = original_raw_output if original_raw_output else idea
            
            # Use the refresh approach prompt
            user_prompt = IDEATION_REFRESH_APPROACH_PROMPT.format(
                research_topic=None,
                current_idea=idea_to_refresh
            )
            
            # Call the language model to refresh the idea
            messages = [
                {"role": "system", "content": IDEATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.chat(model=self.model, messages=messages)
            new_content = response.choices[0].message.content
            
            print(f"\n===== RAW LLM OUTPUT FOR REFRESH IDEA =====")
            print(new_content)
            print("==========================================\n")
            
            # Clean up the response to remove any markdown code blocks
            cleaned_content = re.sub(r"```(?:markdown|json)?\s*", "", new_content)
            cleaned_content = re.sub(r"```\s*$", "", cleaned_content)
            
            # Initialize structured data
            structured_data = {}
            
            # Use direct string searches with simple start and end markers as suggested
            # This avoids complex regex and JSON parsing that can fail with escape sequences
            
            # Extract title
            if '"title"' in new_content:
                title_start = new_content.find('"title"') + len('"title"')
                # Find the colon after "title"
                title_start = new_content.find(':', title_start) + 1
                # Find the opening quote after the colon
                title_start = new_content.find('"', title_start) + 1
                # Find the closing quote
                title_end = new_content.find('"', title_start)
                if title_end > title_start:
                    structured_data["title"] = new_content[title_start:title_end]
                    print(f"Found title: {structured_data['title']}")
            
            # Extract proposed_method - looking for text after "proposed_method": " and up till ", "experiment_plan"
            if '"proposed_method"' in new_content:
                method_start = new_content.find('"proposed_method"') + len('"proposed_method"')
                # Find the colon after "proposed_method"
                method_start = new_content.find(':', method_start) + 1
                # Find the opening quote after the colon
                method_start = new_content.find('"', method_start) + 1
                
                # For the end, look for the next field or the closing brace
                if '"experiment_plan"' in new_content[method_start:]:
                    # Find the end by locating the next field
                    pattern_end = new_content.find('", "experiment_plan"', method_start)
                    if pattern_end > method_start:
                        structured_data["proposed_method"] = new_content[method_start:pattern_end]
                        print(f"Found proposed_method by looking for next field")
                else:
                    # If no next field, look for closing quote + comma or closing quote + }
                    for end_pattern in ['",', '"}']:
                        pattern_end = new_content.find(end_pattern, method_start)
                        if pattern_end > method_start:
                            structured_data["proposed_method"] = new_content[method_start:pattern_end]
                            print(f"Found proposed_method by looking for {end_pattern}")
                            break
            
            # Extract experiment_plan
            if '"experiment_plan"' in new_content:
                plan_start = new_content.find('"experiment_plan"') + len('"experiment_plan"')
                # Find the colon after "experiment_plan"
                plan_start = new_content.find(':', plan_start) + 1
                # Find the opening quote after the colon
                plan_start = new_content.find('"', plan_start) + 1
                
                # For the end, look for the next field or closing brace
                if '"test_case_examples"' in new_content[plan_start:]:
                    # Find the end by locating the next field
                    pattern_end = new_content.find('", "test_case_examples"', plan_start)
                    if pattern_end > plan_start:
                        structured_data["experiment_plan"] = new_content[plan_start:pattern_end]
                        print(f"Found experiment_plan by looking for next field")
                else:
                    # If no next field, look for closing quote + comma or closing quote + }
                    for end_pattern in ['",', '"}']:
                        pattern_end = new_content.find(end_pattern, plan_start)
                        if pattern_end > plan_start:
                            structured_data["experiment_plan"] = new_content[plan_start:pattern_end]
                            print(f"Found experiment_plan by looking for {end_pattern}")
                            break
            
            # Extract test_case_examples
            if '"test_case_examples"' in new_content:
                test_start = new_content.find('"test_case_examples"') + len('"test_case_examples"')
                # Find the colon after "test_case_examples"
                test_start = new_content.find(':', test_start) + 1
                # Find the opening quote after the colon
                test_start = new_content.find('"', test_start) + 1
                
                # For the end, look for closing quote + comma or closing quote + }
                for end_pattern in ['",', '"}']:
                    pattern_end = new_content.find(end_pattern, test_start)
                    if pattern_end > test_start:
                        structured_data["test_case_examples"] = new_content[test_start:pattern_end]
                        print(f"Found test_case_examples by looking for {end_pattern}")
                        break
            
            # Fix any special characters in extracted fields
            for key in structured_data:
                if structured_data[key]:
                    # Replace escaped quotes
                    structured_data[key] = structured_data[key].replace('\\"', '"')
                    # Replace escaped newlines
                    structured_data[key] = structured_data[key].replace('\\n', '\n')
                    # Replace other common escape sequences
                    structured_data[key] = structured_data[key].replace('\\\\', '\\')
                    structured_data[key] = structured_data[key].replace('\\/', '/')
            
            print(f"Extracted fields using simple search: {list(structured_data.keys())}")
            
            # Fallback for markdown format if JSON parsing failed
            if not structured_data or len(structured_data.keys()) <= 1:
                print("Simple search extraction failed or incomplete, trying markdown section extraction")
                
                # Look for markdown headers in the cleaned content
                headers = re.findall(r'(?:^|\n)#+\s+(.*?)(?:\n|$)', cleaned_content)
                print(f"Found {len(headers)} markdown headers: {headers[:3]}")
                
                # If we found a title but not in structured_data, add it
                if headers and "title" not in structured_data:
                    structured_data["title"] = headers[0]
                
                # Extract sections based on common headers
                method_section = re.search(r'(?:^|\n)#+\s+(?:Proposed\s+)?Method(?:ology)?[\s:]*\n+(.*?)(?:\n#+\s+|$)', cleaned_content, re.IGNORECASE | re.DOTALL)
                if method_section and "proposed_method" not in structured_data:
                    structured_data["proposed_method"] = method_section.group(1).strip()
                
                experiment_section = re.search(r'(?:^|\n)#+\s+(?:Experiment(?:al)?(?:\s+Plan)?|Evaluation)[\s:]*\n+(.*?)(?:\n#+\s+|$)', cleaned_content, re.IGNORECASE | re.DOTALL)
                if experiment_section and "experiment_plan" not in structured_data:
                    structured_data["experiment_plan"] = experiment_section.group(1).strip()
                
                examples_section = re.search(r'(?:^|\n)#+\s+(?:Test\s+Case\s+Examples|Examples|Use\s+Cases)[\s:]*\n+(.*?)(?:\n#+\s+|$)', cleaned_content, re.IGNORECASE | re.DOTALL)
                if examples_section and "test_case_examples" not in structured_data:
                    structured_data["test_case_examples"] = examples_section.group(1).strip()
            
            # Format the structured data into a proper research idea
            if structured_data and ("title" in structured_data or "proposed_method" in structured_data or "experiment_plan" in structured_data):
                print(f"Successfully extracted structured data: {list(structured_data.keys())}")
                # Format the content
                formatted_content = ""
                
                # Add title
                if "title" in structured_data and structured_data["title"]:
                    formatted_content += f"# {structured_data['title']}\n\n"
                else:
                    formatted_content += "# Refreshed Research Idea\n\n"
                
                # Add proposed method
                if "proposed_method" in structured_data and structured_data["proposed_method"]:
                    formatted_content += f"## Proposed Method\n\n{structured_data['proposed_method']}\n\n"
                
                # Add experiment plan
                if "experiment_plan" in structured_data and structured_data["experiment_plan"]:
                    formatted_content += f"## Experiment Plan\n\n{structured_data['experiment_plan']}\n\n"
                
                # Add test cases
                if "test_case_examples" in structured_data and structured_data["test_case_examples"]:
                    formatted_content += f"## Test Case Examples\n\n{structured_data['test_case_examples']}\n\n"
                
                print(f"Created formatted content with {len(formatted_content)} characters")
                return formatted_content, new_content
            else:
                # If structured data extraction failed, use the cleaned content directly
                print("Structured data extraction failed, using cleaned content directly")
                
                # Check if cleaned content already has a title (markdown #)
                if not cleaned_content.strip().startswith("#"):
                    # Add a generic title
                    cleaned_content = "# Refreshed Research Idea\n\n" + cleaned_content
                
                return cleaned_content, new_content
            
        except Exception as e:
            logger.error(f"Error refreshing idea: {e}")
            traceback.print_exc()  # Print the full stack trace for debugging
            # Return the original idea if refresh fails
            error_msg = f"<p>Unable to refresh idea: {str(e)}.</p>"
            return f"{error_msg}<p>{idea}</p>", original_raw_output or idea

    def _extract_query(self, text: str) -> Optional[str]:
        """Extract query from LLM response using multiple methods."""
        # Method 1: Try to find the exact JSON pattern {"query": "..."}
        try:
            # Look for pattern starting with {"query" and ending with }
            json_pattern = r'{"query":[^}]*}'
            json_match = re.search(json_pattern, text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # For debugging
                print(f"Found JSON pattern: {json_str}")
                query_data = json.loads(json_str)
                if "query" in query_data:
                    return query_data["query"]
        except Exception as e:
            print(f"JSON extraction error: {e}")
            pass
            
        # Method 2: Look for any JSON with query field
        try:
            # Look for any JSON block
            json_block_pattern = r'```(?:json)?\s*(.*?)\s*```|{.*}'
            match = re.search(json_block_pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1) or match.group(0)
                print(f"Found JSON block: {json_str}")
                # Clean up the extracted JSON string - handle edge cases
                json_str = json_str.replace('\\n', ' ').replace('\\', '\\\\')
                json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)
                
                query_data = json.loads(json_str)
                if "query" in query_data:
                    return query_data["query"]
        except Exception as e:
            print(f"JSON block extraction error: {e}")
            pass
            
        # Method 3: Try to extract query directly with various regex patterns
        try:
            # Try multiple patterns
            patterns = [
                r'(?:"|\')query(?:"|\'):\s*(?:"|\')([^"\']+)(?:"|\')(?:,|})',  # Standard JSON format
                r'query:\s*(?:"|\')([^"\']+)(?:"|\')(?:,|}|\n)',  # Relaxed format
                r'query\s*=\s*(?:"|\')([^"\']+)(?:"|\')(?:,|}|\n)',  # Assignment format
                r'(?:query|search query):\s*(?:"|\')?(.*?)(?:"|\')?(?:\n|$)',  # Plain text format
            ]
            
            for pattern in patterns:
                query_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if query_match:
                    print(f"Found query with pattern: {pattern}")
                    return query_match.group(1).strip()
        except Exception as e:
            print(f"Regex extraction error: {e}")
            pass
            
        # Method 4: Look for specific markers that might indicate a query
        try:
            markers = [
                "Search query:", "Query:", "Generated query:", 
                "Search term:", "Search for:", "The query is:"
            ]
            
            for marker in markers:
                if marker in text:
                    parts = text.split(marker, 1)
                    if len(parts) > 1:
                        # Take text after marker until next newline or punctuation
                        result = parts[1].strip()
                        end = result.find('\n')
                        if end != -1:
                            result = result[:end]
                        
                        # Remove quotes if present
                        result = result.strip('"').strip("'").strip()
                        
                        if result:
                            print(f"Found query with marker: {marker}")
                            return result
        except Exception as e:
            print(f"Marker extraction error: {e}")
            pass
            
        # Method 5: If all else fails, use the first paragraph as the query
        try:
            paragraphs = re.split(r'\n\s*\n', text)
            for para in paragraphs:
                para = para.strip()
                if len(para) > 10 and not para.startswith('{') and not para.startswith('```'):
                    # Remove potential prefixes like "Query:" if they exist
                    result = re.sub(r'^(?:search\s+)?query:\s*', '', para, flags=re.IGNORECASE)
                    print(f"Using first paragraph as query: {result[:50]}...")
                    return result
        except Exception as e:
            print(f"Paragraph extraction error: {e}")
            pass
                
        # If nothing found, return the raw text (limited to 200 chars)
        print("No query pattern found, returning truncated raw text")
        return text[:200] if text else None

    def process_feedback(self, idea: str, user_feedback: str, original_raw_output: Optional[str] = None) -> Tuple[str, str]:
        """Process direct user feedback from chat to improve a research idea.
        
        Args:
            idea: The formatted idea text (parsed/displayed version)
            user_feedback: The feedback text from the user
            original_raw_output: The original unparsed LLM output if available
            
        Returns:
            Tuple of (improved_idea_content, raw_llm_output)
        """
        try:
            # Determine which version of the idea to use
            idea_to_improve = original_raw_output if original_raw_output else idea
            
            # Use the direct feedback prompt
            user_prompt = IDEATION_DIRECT_FEEDBACK_PROMPT.format(
                current_idea=idea_to_improve,
                user_feedback=user_feedback
            )
            
            # Call the language model to improve the idea based on user feedback
            messages = [
                {"role": "system", "content": IDEATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.chat(model=self.model, messages=messages)
            new_content = response.choices[0].message.content
            
            print(f"\n===== RAW LLM OUTPUT FOR USER FEEDBACK IMPROVEMENT =====")
            print(new_content)
            print("==========================================\n")
            
            # Try to extract structured data from the response
            parsed_data = self._extract_json_data(new_content)
            
            # If we successfully extracted structured JSON data
            if parsed_data:
                # Format to ensure consistent field naming
                result = self._format_structured_idea(parsed_data)
                # Return both the formatted content and raw output
                return result.get("content", new_content), new_content
            
            # Clean up the response to remove any markdown code blocks that might have been added
            cleaned_content = re.sub(r"```(?:markdown|json)?\s*", "", new_content)
            cleaned_content = re.sub(r"```\s*$", "", cleaned_content)
            
            # Return both the cleaned content and the raw LLM output
            return cleaned_content, new_content
            
        except Exception as e:
            logger.error(f"Error processing user feedback: {e}")
            # Return the original idea if improvement fails
            error_msg = f"<p>Unable to process feedback: {str(e)}.</p>"
            return f"{error_msg}<p>{idea}</p>", original_raw_output or idea
