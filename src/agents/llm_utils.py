from typing import Dict, List, Optional, Any
import litellm
import logging
import os
from collections import namedtuple

# Azure OpenAI imports (only imported when DEPLOY=true)
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Simple named tuple to track completion results
CompletionResult = namedtuple("CompletionResult", ["content", "model", "cost", "input_tokens", "output_tokens", "total_tokens"])

# Global variables to track token usage
total_tokens_used = 0
total_cost = 0.0

# Check deployment mode
DEPLOY_MODE = os.environ.get('DEPLOY', 'false').lower() == 'true'

# Initialize Azure OpenAI client if in deploy mode
azure_client = None
if DEPLOY_MODE and AZURE_AVAILABLE:
    try:
        azure_client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
        )
        logger.info("Azure OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Azure OpenAI client: {e}")
        azure_client = None

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
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
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

def _azure_completion(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo", **kwargs) -> CompletionResult:
    """Azure OpenAI completion wrapper"""
    if not azure_client:
        raise RuntimeError("Azure OpenAI client not available. Check AZURE_OPENAI_* environment variables.")
    
    try:
        # Map model names to Azure deployment names if needed
        deployment_mapping = {
            "gpt-3.5-turbo": os.environ.get("AZURE_GPT35_DEPLOYMENT", "gpt-35-turbo"),
            "gpt-4": os.environ.get("AZURE_GPT4_DEPLOYMENT", "gpt-4"),
            "gpt-4o": os.environ.get("AZURE_GPT4O_DEPLOYMENT", "gpt-4o"),
            "gpt-4o-mini": os.environ.get("AZURE_GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
        }
        
        deployment_name = deployment_mapping.get(model, model)
        
        # Filter out kwargs that Azure OpenAI doesn't support
        azure_kwargs = {}
        supported_params = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty', 'stream']
        for key, value in kwargs.items():
            if key in supported_params:
                azure_kwargs[key] = value
        
        # Make the API call
        response = azure_client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            **azure_kwargs
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
            logger.warning("Content returned as None from Azure OpenAI")
            content = ""
        
        # Create and return result
        return CompletionResult(
            content=content.strip(),
            model=response.model,
            cost=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=usage.total_tokens
        )
        
    except Exception as e:
        logger.error(f"Error in Azure OpenAI completion: {str(e)}")
        raise

def _litellm_completion(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo", **kwargs) -> CompletionResult:
    """LiteLLM completion wrapper"""
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
        logger.error(f"Error in LiteLLM completion: {str(e)}")
        raise

def llm_complete(messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo", **kwargs) -> CompletionResult:
    """Simple wrapper with automatic client selection based on DEPLOY flag
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model identifier
        **kwargs: Additional args for completion
        
    Returns:
        CompletionResult with content and usage stats
    """
    if DEPLOY_MODE and azure_client:
        logger.debug(f"Using Azure OpenAI for model: {model}")
        return _azure_completion(messages, model, **kwargs)
    else:
        logger.debug(f"Using LiteLLM for model: {model}")
        return _litellm_completion(messages, model, **kwargs)

def get_client_info() -> Dict[str, Any]:
    """Get information about which client is being used"""
    return {
        "deploy_mode": DEPLOY_MODE,
        "azure_available": AZURE_AVAILABLE,
        "azure_client_ready": azure_client is not None,
        "active_client": "Azure OpenAI" if (DEPLOY_MODE and azure_client) else "LiteLLM"
    }