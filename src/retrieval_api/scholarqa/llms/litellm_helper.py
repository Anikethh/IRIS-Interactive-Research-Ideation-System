import logging
import os
from scholarqa.llms.constants import *
from typing import List, Any, Callable, Tuple, Iterator, Union, Generator

import litellm
from litellm.caching import Cache
from litellm.utils import trim_messages
from langsmith import traceable

# Azure OpenAI imports (only imported when DEPLOY=true)
try:
    from openai import AzureOpenAI
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# litellm.set_verbose=True
litellm.drop_params=True
# os.environ['LITELLM_LOG'] = 'DEBUG'

from scholarqa.state_mgmt.local_state_mgr import AbsStateMgrClient

logger = logging.getLogger(__name__)

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
        logger.info("Azure OpenAI client initialized successfully in scholarqa")
    except Exception as e:
        logger.error(f"Failed to initialize Azure OpenAI client in scholarqa: {e}")
        azure_client = None

class CostAwareLLMCaller:
    def __init__(self, state_mgr: AbsStateMgrClient):
        self.state_mgr = state_mgr

    @staticmethod
    def parse_result_args(method_result: Union[Tuple[Any, CompletionResult], CompletionResult]) -> Tuple[
        Any, List[CompletionResult], List[str]]:
        if type(method_result) == tuple:
            result, completion_costs = method_result
        else:
            result, completion_costs = method_result, method_result
        completion_costs = [completion_costs] if type(completion_costs) != list else completion_costs
        completion_models = [cost.model for cost in completion_costs]
        return result, completion_costs, completion_models

    def call_method(self, cost_args: CostReportingArgs, method: Callable, **kwargs) -> CostAwareLLMResult:
        method_result = method(**kwargs)
        import time as t 
        t.sleep(2)
        result, completion_costs, completion_models = self.parse_result_args(method_result)
        total_cost = self.state_mgr.report_llm_usage(completion_costs=completion_costs, cost_args=cost_args)
        return CostAwareLLMResult(result=result, tot_cost=total_cost, models=completion_models)

    def call_iter_method(self, cost_args: CostReportingArgs, gen_method: Callable, **kwargs) -> Generator[
        Any, None, CostAwareLLMResult]:
        all_results, all_completion_costs, all_completion_models = [], [], []
        for method_result in gen_method(**kwargs):
            result, completion_costs, completion_models = self.parse_result_args(method_result)
            all_completion_costs.extend(completion_costs)
            all_completion_models.extend(completion_models)
            all_results.append(result)
            yield result
        total_cost = self.state_mgr.report_llm_usage(completion_costs=all_completion_costs, cost_args=cost_args)
        return CostAwareLLMResult(result=all_results, tot_cost=total_cost, models=all_completion_models)


def success_callback(kwargs, completion_response, start_time, end_time):
    """required callback method to update the response object with cache hit/miss info"""
    completion_response.cache_hit = kwargs["cache_hit"] if kwargs["cache_hit"] is not None else False


litellm.success_callback = [success_callback]


def setup_llm_cache(cache_type: str = "s3", **cache_args):
    logger.info("Setting up LLM cache...")
    litellm.cache = Cache(type=cache_type, **cache_args)
    litellm.enable_cache()

def _azure_batch_completion(model: str, messages: List[str], system_prompt: str = None, **llm_params) -> List[CompletionResult]:
    """Azure OpenAI batch completion wrapper"""
    if not azure_client:
        raise RuntimeError("Azure OpenAI client not available. Check AZURE_OPENAI_* environment variables.")
    
    # Map model names to Azure deployment names
    deployment_mapping = {
        "gpt-3.5-turbo": os.environ.get("AZURE_GPT35_DEPLOYMENT", "gpt-35-turbo"),
        "gpt-4": os.environ.get("AZURE_GPT4_DEPLOYMENT", "gpt-4"),
        "gpt-4o": os.environ.get("AZURE_GPT4O_DEPLOYMENT", "gpt-4o"),
        "gpt-4o-mini": os.environ.get("AZURE_GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
    }
    
    deployment_name = deployment_mapping.get(model, model)
    
    # Filter supported parameters
    azure_kwargs = {}
    supported_params = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']
    for key, value in llm_params.items():
        if key in supported_params:
            azure_kwargs[key] = value
    
    results = []
    for msg in messages:
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.append({"role": "user", "content": msg})
        
        try:
            response = azure_client.chat.completions.create(
                model=deployment_name,
                messages=chat_messages,
                **azure_kwargs
            )
            
            res_usage = response.usage
            res_str = response.choices[0].message.content
            if res_str is None:
                res_str = ""
            
            cost_tuple = CompletionResult(
                content=res_str.strip(),
                model=response.model,
                cost=0.0,  # Cost calculation can be added later
                input_tokens=res_usage.prompt_tokens,
                output_tokens=res_usage.completion_tokens,
                total_tokens=res_usage.total_tokens
            )
            results.append(cost_tuple)
            
        except Exception as e:
            logger.error(f"Error in Azure batch completion for message {len(results)+1}: {e}")
            raise
    
    return results

def _azure_single_completion(user_prompt: str, system_prompt: str = None, model: str = "gpt-3.5-turbo", **llm_params) -> CompletionResult:
    """Azure OpenAI single completion wrapper"""
    if not azure_client:
        raise RuntimeError("Azure OpenAI client not available. Check AZURE_OPENAI_* environment variables.")
    
    # Map model names to Azure deployment names
    deployment_mapping = {
        "gpt-3.5-turbo": os.environ.get("AZURE_GPT35_DEPLOYMENT", "gpt-35-turbo"),
        "gpt-4": os.environ.get("AZURE_GPT4_DEPLOYMENT", "gpt-4"),
        "gpt-4o": os.environ.get("AZURE_GPT4O_DEPLOYMENT", "gpt-4o"),
        "gpt-4o-mini": os.environ.get("AZURE_GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
    }
    
    deployment_name = deployment_mapping.get(model, model)
    
    # Filter supported parameters
    azure_kwargs = {}
    supported_params = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']
    for key, value in llm_params.items():
        if key in supported_params:
            azure_kwargs[key] = value
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = azure_client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            **azure_kwargs
        )
        
        res_usage = response.usage
        res_str = response.choices[0].message.content
        if res_str is None:
            logger.warning("Content returned as None from Azure OpenAI")
            res_str = ""
        
        return CompletionResult(
            content=res_str.strip(),
            model=response.model,
            cost=0.0,  # Cost calculation can be added later
            input_tokens=res_usage.prompt_tokens,
            output_tokens=res_usage.completion_tokens,
            total_tokens=res_usage.total_tokens
        )
        
    except Exception as e:
        logger.error(f"Error in Azure single completion: {e}")
        raise

@traceable(run_type="llm", name="batch completion")
def batch_llm_completion(model: str, messages: List[str], system_prompt: str = None, fallback=GPT_4o,
                         **llm_lite_params) -> List[CompletionResult]:
    """returns the result from the llm chat completion api with cost and tokens used"""
    
    if DEPLOY_MODE and azure_client:
        logger.debug(f"Using Azure OpenAI for batch completion with model: {model}")
        return _azure_batch_completion(model, messages, system_prompt, **llm_lite_params)
    else:
        logger.debug(f"Using LiteLLM for batch completion with model: {model}")
        fallbacks = [fallback] if fallback else []
        messages = [trim_messages([{"role": "system", "content": system_prompt}, {"role": "user", "content": msg}], model)
                    for msg in messages]
        responses = litellm.batch_completion(messages=messages, model=model, fallbacks=fallbacks, **llm_lite_params)
        import time as t 
        t.sleep(5)
        results = []
        for i, res in enumerate(responses):
            # try:
            #     res_cost = round(litellm.completion_cost(res), 6)
            # except Exception as e:
                # logger.warning(f"Error calculating cost: {e}")
            res_cost = 0.0

            res_usage = res.usage
            res_str = res["choices"][0]["message"]["content"].strip()
            cost_tuple = CompletionResult(content=res_str, model=res["model"],
                                          cost=res_cost if not res.get("cache_hit") else 0.0,
                                          input_tokens=res_usage.prompt_tokens,
                                          output_tokens=res_usage.completion_tokens, total_tokens=res_usage.total_tokens)
            results.append(cost_tuple)
        return results


@traceable(run_type="llm", name="completion")
def llm_completion(user_prompt: str, system_prompt: str = None, fallback=GPT_4o, **llm_lite_params) -> CompletionResult:
    """returns the result from the llm chat completion api with cost and tokens used"""
    
    if DEPLOY_MODE and azure_client:
        logger.debug(f"Using Azure OpenAI for completion")
        model = llm_lite_params.get('model', 'gpt-3.5-turbo')
        return _azure_single_completion(user_prompt, system_prompt, model, **llm_lite_params)
    else:
        logger.debug(f"Using LiteLLM for completion")
        messages = []
        # fallbacks = [fallback] if fallback else []
        fallbacks = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        # print(llm_lite_params)
        response = litellm.completion(messages=messages, fallbacks=fallbacks, **llm_lite_params)
        import time as t 
        t.sleep(2)
        # try:
        #     res_cost = round(litellm.completion_cost(response), 6)
        # except Exception as e:
            # logger.warning(f"Error calculating cost: {e}")
        res_cost = 0.0

        res_usage = response.usage
        res_str = response["choices"][0]["message"]["content"]
        if res_str is None:
            logger.warning("Content returned as None, checking for response in tool_calls...")
            res_str = response["choices"][0]["message"]["tool_calls"][0].function.arguments
        cost_tuple = CompletionResult(content=res_str.strip(), model=response.model,
                                      cost=res_cost if not response.get("cache_hit") else 0.0,
                                      input_tokens=res_usage.prompt_tokens,
                                      output_tokens=res_usage.completion_tokens, total_tokens=res_usage.total_tokens)
        return cost_tuple
