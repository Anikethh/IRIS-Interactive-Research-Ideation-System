import os
import sys
sys.path.insert(0, "/Users/aniketh/TCS Research/IRIS/src/retrieval_api")

from scholarqa import ScholarQA
from scholarqa.rag.retrieval import PaperFinder, PaperFinderWithReranker
from scholarqa.rag.retriever_base import FullTextRetriever
from scholarqa.rag.reranker.modal_engine import HuggingFaceReranker

# API key should be set in environment variable
if not os.getenv('SEMANTIC_SCHOLAR_API_KEY'):
    raise ValueError("SEMANTIC_SCHOLAR_API_KEY environment variable must be set")

retriever = FullTextRetriever(n_retrieval=10, n_keyword_srch=10)
reranker = HuggingFaceReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", batch_size=256)
paper_finder = PaperFinderWithReranker(retriever, reranker=reranker, n_rerank=5, context_threshold=0.1)
scholar_qa = ScholarQA(paper_finder=paper_finder, llm_model="gemini/gemini-2.0-flash-lite")

query = "Adversarial training for large language models (LLMs) in code generation; prompt engineering; puzzle-based frameworks; constraint-guided code generation; language model adversarial attack detection"
print(scholar_qa.answer_query(query))