import requests
import time
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from loguru import logger

class HuggingFaceAPI:
    """Interface for HuggingFace's API."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the HuggingFace API interface.
        
        Args:
            config: Configuration dictionary containing API settings
        """
        self.config = config
        self.api_token = os.getenv("HF_API_TOKEN")
        if not self.api_token:
            raise ValueError("HF_API_TOKEN environment variable not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate text using the HuggingFace API.
        
        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            
        Returns:
            Dictionary containing the API response
        """
        url = f"{self.config['api_base']}{self.config['default_model']}"
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens or self.config.get("max_tokens", 512),
                "temperature": temperature or self.config.get("temperature", 0.7),
                "top_p": top_p or self.config.get("top_p", 0.9),
                "do_sample": True,
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    def batch_generate(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Generate text for multiple prompts in batch.
        
        Args:
            prompts: List of input prompts
            **kwargs: Additional arguments passed to generate()
            
        Returns:
            List of API responses
        """
        results = []
        for i in range(0, len(prompts), self.config["batch_size"]):
            batch = prompts[i:i + self.config["batch_size"]]
            batch_results = [self.generate(prompt, **kwargs) for prompt in batch]
            results.extend(batch_results)
            
            if i + self.config["batch_size"] < len(prompts):
                time.sleep(self.config.get("retry_delay", 1))
                
        return results