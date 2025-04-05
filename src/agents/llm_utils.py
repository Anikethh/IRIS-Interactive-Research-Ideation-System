from typing import Dict, List, Optional, Any
import litellm
import logging
from collections import namedtuple

logger = logging.getLogger(__name__)

# Simple named tuple to track completion results
CompletionResult = namedtuple("CompletionResult", ["content", "model", "cost", "input_tokens", "output_tokens", "total_tokens"])

# Global variables to track token usage
total_tokens_used = 0
total_cost = 0.0

def reset_usage():
    """Reset token usage counters"""
    global total_tokens_used, total_cost
    total_tokens_used = 0
    total_cost = 0.0

def get_usage():
    """Get current token usage stats"""
    return {
        "total_tokens": total_tokens_used,
        "total_cost": total_cost
    }

def track_usage(input_tokens: int, output_tokens: int, model: str) -> float:
    """Track token usage and calculate cost"""
    global total_tokens_used, total_cost
    
    # Update total tokens
    total_tokens_used += input_tokens + output_tokens
    
    # Calculate cost based on model - can expand this as needed
    cost_per_1k = {
        "gpt-4": (0.03, 0.06),  # (input, output) cost per 1k tokens
        "gpt-3.5-turbo": (0.0015, 0.002),
        "anthropic/claude-3-opus": (0.015, 0.075),
        "anthropic/claude-3-sonnet": (0.003, 0.015),
        "gemini-pro": (0.00025, 0.0005)
    }
    
    # Get cost rates, default to lowest rate if model not found
    input_rate, output_rate = cost_per_1k.get(model, (0.0001, 0.0002))
    
    # Calculate cost
    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1000
    total_cost += cost
    
    return cost

def llm_complete(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo", **kwargs) -> CompletionResult:
    """Simple wrapper around litellm.completion with cost tracking
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model identifier
        **kwargs: Additional args for litellm.completion
        
    Returns:
        CompletionResult with content and usage stats
    """
    try:
        # Make the API call
        response = litellm.completion(
            messages=messages,
            model=model,
            **kwargs
        )
        
        # Get usage stats
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        
        # Track usage and calculate cost
        cost = track_usage(input_tokens, output_tokens, model)
        
        # Extract the response content
        content = response.choices[0].message.content
        if content is None:
            logger.warning("Content returned as None, checking tool_calls...")
            content = response.choices[0].message.get("tool_calls", [{}])[0].get("function", {}).get("arguments", "")
        
        # Create and return result
        return CompletionResult(
            content=content.strip(),
            model=response.model,
            cost=cost if not response.get("cache_hit", False) else 0.0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage.total_tokens
        )
        
    except Exception as e:
        logger.error(f"Error in llm_complete: {str(e)}")
        raise