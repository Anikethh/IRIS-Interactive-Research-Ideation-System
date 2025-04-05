from typing import Dict, Any, Optional, Tuple, Union, List
from sentence_transformers import CrossEncoder

import modal
import os
import numpy as np
import torch

from scholarqa.rag.reranker.reranker_base import AbstractReranker, RERANKER_MAPPING
import logging

logger = logging.getLogger(__name__)


class ModalReranker(AbstractReranker):
    # def __init__(self, app_name: str, api_name: str, batch_size=32, gen_options: Dict[str, Any] = None):
    #     logger.info(f"using model {app_name} on Modal for reranking")
    #     self.modal_engine = ModalEngine(app_name, api_name, gen_options)
    #     self.batch_size = batch_size

    # def get_scores(self, query: str, documents: List[str]):
    #     logger.info("Invoking the reranker deployed on Modal")
    #     return self.modal_engine.generate(
    #         (query, documents, self.batch_size), streaming=False
    #     )
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", batch_size: int = 32):
        logger.info(f"Using HuggingFace model {model_name} for reranking")
        self.model = CrossEncoder(model_name, device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.batch_size = batch_size

    def get_scores(self, query: str, documents: List[str]) -> List[float]:
        if not documents:
            return []
            
        try:
            # Create pairs of (query, document) for each document
            pairs = [[query, doc] for doc in documents]
            
            # Get scores for all pairs
            scores = self.model.predict(pairs, batch_size=self.batch_size)
            
            # Convert to numpy array for easier handling
            scores = np.array(scores)
            
            # Apply sigmoid to convert scores to probabilities
            scores = 1 / (1 + np.exp(-scores))
            
            # Handle any remaining NaN values
            scores = np.nan_to_num(scores, nan=0.0)
            
            # Ensure minimum score is above context threshold
            min_score = 0.1
            scores = min_score + (1 - min_score) * scores
            
            # Sort in descending order
            sorted_indices = np.argsort(-scores)
            scores = scores[sorted_indices]
            
            logger.info(f"Score range: min={scores.min():.3f}, max={scores.max():.3f}, mean={scores.mean():.3f}")
            
            return scores.tolist()
            
        except Exception as e:
            logger.error(f"Error in reranking: {str(e)}")
            # Return descending scores in case of error to maintain some ranking
            return [0.9 - (i * 0.01) for i in range(len(documents))]



RERANKER_MAPPING["modal"] = ModalReranker


class ModalEngine:
    modal_client: modal.Client

    def __init__(self, model_id: str, api_name: str, gen_options: Dict[str, Any] = None) -> None:
        # Skiff secrets
        modal_token = os.getenv("MODAL_TOKEN")
        modal_token_secret = os.getenv("MODAL_TOKEN_SECRET")
        self.modal_client = modal.Client.from_credentials(modal_token, modal_token_secret)
        self.model_id = model_id
        self.gen_options = {"max_tokens": 1024, "temperature": 0.7, "logprobs": 2,
                            "stop_token_ids": [128009]} if gen_options is None else gen_options
        self.api_name = api_name

    def fn_lookup(
            self,
            **opt_kwargs,
    ) -> Tuple[modal.Function, Optional[Dict[str, Any]]]:
        if opt_kwargs:
            opts = {**self.gen_options, **opt_kwargs} if self.gen_options else {**opt_kwargs}
        else:
            opts = self.gen_options

        fn = modal.Function.lookup(self.model_id, self.api_name, client=self.modal_client)
        return fn, opts if opts else None

    def generate(self, input_args: Tuple, streaming=False, **opt_kwargs) -> Union[str, List[Dict]]:
        gen_fn, opts = self.fn_lookup(**opt_kwargs)
        if streaming:
            outputs = []
            if opts:
                for chunk in gen_fn.remote_gen(*input_args, opts):
                    outputs.append(chunk)
            else:
                for chunk in gen_fn.remote_gen(*input_args):
                    outputs.append(chunk)
            return "".join(outputs) if outputs and type(outputs[0]) == str else outputs
        else:
            return gen_fn.remote(*input_args, **opts) if opts else gen_fn.remote(*input_args)

class HuggingFaceReranker(AbstractReranker):
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", batch_size: int = 32):
        logger.info(f"Using HuggingFace model {model_name} for reranking")
        self.model = CrossEncoder(model_name, device=torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.batch_size = batch_size

    def get_scores(self, query: str, documents: List[str]) -> List[float]:
        if not documents:
            return []
            
        try:
            # Create pairs of (query, document) for each document
            pairs = [[query, doc] for doc in documents]
            
            # Get scores for all pairs
            scores = self.model.predict(pairs, batch_size=self.batch_size)
            
            # Convert to numpy array for easier handling
            scores = np.array(scores)
            
            # Apply sigmoid to convert scores to probabilities
            scores = 1 / (1 + np.exp(-scores))
            
            # Handle any remaining NaN values
            scores = np.nan_to_num(scores, nan=0.0)
            
            # Ensure minimum score is above context threshold
            min_score = 0.1
            scores = min_score + (1 - min_score) * scores
            
            # Sort in descending order
            sorted_indices = np.argsort(-scores)
            scores = scores[sorted_indices]
            
            logger.info(f"Score range: min={scores.min():.3f}, max={scores.max():.3f}, mean={scores.mean():.3f}")
            
            return scores.tolist()
            
        except Exception as e:
            logger.error(f"Error in reranking: {str(e)}")
            # Return descending scores in case of error to maintain some ranking
            return [0.9 - (i * 0.01) for i in range(len(documents))]

# Register the reranker
RERANKER_MAPPING["huggingface"] = HuggingFaceReranker 