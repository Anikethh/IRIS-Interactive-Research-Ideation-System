from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import yaml
import json
import re
from pathlib import Path
from loguru import logger
import retry


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, config_path: str):
        """Initialize with configuration."""
        self.load_config(config_path)
        self.state = {}
        self.messages = []

    def load_config(self, config_path: str) -> None:
        """Load configuration from YAML file."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def _get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for the specified provider."""
        env_var = f"{provider.upper()}_API_KEY"
        return os.environ.get(env_var)

    @retry.retry(tries=3, delay=2)
    def chat(self, model: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Send a chat request to the model."""
        # This will be implemented by the derived classes
        pass

    @abstractmethod
    def act(self, state: Dict) -> Dict:
        """Perform an action based on the current state."""
        pass

    @abstractmethod
    def update_state(self, action_result: Dict) -> None:
        """Update internal state based on action results."""
        pass

    def _extract_json_data(self, text: str) -> Optional[Dict[str, Any]]:
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

        return None
