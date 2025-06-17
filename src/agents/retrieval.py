from typing import Dict, List, Optional
import requests
from scholarly import scholarly
import tempfile
from pathlib import Path
from loguru import logger
from .base import BaseAgent
from ..utils.paper_processing import PaperProcessor, ProcessedPaper
import json

class RetrievalAgent(BaseAgent):
    """Agent responsible for retrieving and processing scientific papers."""
    
    def __init__(self, config_path: str):
        super().__init__(config_path)
        self.processor = PaperProcessor(self.config)
        self.processed_papers: Dict[str, ProcessedPaper] = {}
        # ADD: Query memory as described
        self.past_queries = []  # Track past retrieval queries
        self.memory_size = 3

    def record_query(self, query: str):
        """Record a retrieval query in memory"""
        self.past_queries.append(query)
        if len(self.past_queries) > self.memory_size:
            self.past_queries.pop(0)
    
    def get_memory_context(self) -> Dict[str, Any]:
        """Get memory context for query diversification"""
        return {
            "past_queries": self.past_queries,
            "processed_papers_count": len(self.processed_papers)
        }
    
    def act(self, state: Dict) -> Dict:
        """Take retrieval action based on current state."""
        action_type = state.get("action_type", "search")
        
        if action_type == "search":
            return self._search_papers(state)
        elif action_type == "process":
            return self._process_papers(state)
        elif action_type == "analyze":
            return self._analyze_papers(state)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    def _search_papers(self, state: Dict) -> Dict:
        """Search for relevant papers."""
        query = state["query"]
        max_papers = self.config["retrieval_agent"]["max_papers"]
        
        # Search Google Scholar
        scholar_results = []
        search_query = scholarly.search_pubs(query)
        for i in range(max_papers):
            try:
                result = next(search_query)
                scholar_results.append({
                    "title": result.bib.get("title"),
                    "url": result.bib.get("url"),
                    "year": result.bib.get("year"),
                    "author": result.bib.get("author"),
                    "abstract": result.bib.get("abstract")
                })
            except StopIteration:
                break
        
        return {
            "action": "search",
            "results": scholar_results
        }
    
    def _process_papers(self, state: Dict) -> Dict:
        """Process retrieved papers."""
        papers = state["papers"]
        results = []
        
        for paper in papers:
            paper_url = paper["url"]
            
            # Skip if already processed
            if paper_url in self.processed_papers:
                results.append(self.processed_papers[paper_url])
                continue
            
            try:
                # Download PDF
                with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
                    response = requests.get(paper_url)
                    temp_pdf.write(response.content)
                    temp_pdf.flush()
                    
                    # Process PDF
                    processed_paper = self.processor.process_pdf(temp_pdf.name)
                    self.processed_papers[paper_url] = processed_paper
                    results.append(processed_paper)
                    
            except Exception as e:
                logger.error(f"Failed to process paper {paper['title']}: {e}")
                continue
        
        return {
            "action": "process",
            "processed_papers": results
        }
    
    def _analyze_papers(self, state: Dict) -> Dict:
        """Analyze processed papers based on query."""
        query = state["query"]
        papers = state.get("processed_papers", [])
        if not papers:
            papers = list(self.processed_papers.values())
        
        analysis_results = []
        
        for paper in papers:
            # Rerank chunks
            relevant_chunks = self.processor.rerank_chunks(
                query,
                paper.chunks,
                top_k=self.config["retrieval_agent"]["rerank_top_k"]
            )
            
            # Summarize relevant chunks
            summary = self.processor.summarize_chunks(
                relevant_chunks,
                max_length=self.config["retrieval_agent"]["summary_max_length"]
            )
            
            analysis_results.append({
                "title": paper.title,
                "relevant_chunks": relevant_chunks,
                "summary": summary
            })
        
        return {
            "action": "analyze",
            "analysis": analysis_results
        }
    
    def update_state(self, action_result: Dict) -> None:
        """Update agent's internal state based on action results."""
        self.state.update(action_result)
        
        # Save processed papers to disk if configured
        if self.config["experiment"]["save_intermediate"]:
            papers_dir = Path(self.config["experiment"]["results_dir"]) / "processed_papers"
            papers_dir.mkdir(exist_ok=True)
            
            for url, paper in self.processed_papers.items():
                paper_path = papers_dir / f"{paper.metadata['paper_id']}.json"
                with open(paper_path, "w") as f:
                    json.dump(paper.__dict__, f, indent=2)