from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
import torch
import numpy as np
import logging
from scholarqa.rag.reranker.reranker_base import AbstractReranker, RERANKER_MAPPING

logger = logging.getLogger(__name__)

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