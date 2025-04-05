import json
from typing import Dict, List
# import requests
from pathlib import Path
import subprocess
import tempfile
from loguru import logger
import re
from dataclasses import dataclass
import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch

@dataclass
class ProcessedPaper:
    """Represents a processed scientific paper."""
    title: str
    abstract: str
    full_text: str
    sections: List[Dict[str, str]]
    references: List[Dict[str, str]]
    chunks: List[str]
    metadata: Dict[str, any]

class PaperProcessor:
    """Process scientific papers using S2ORC tools."""
   
    def __init__(self, config: Dict):
        self.config = config
        self.s2orc_path = Path(config['retrieval']['s2orc_path'])
        
        # Initialize embeddings model for reranking
        self.tokenizer = AutoTokenizer.from_pretrained(config['retrieval']['embedding_model'])
        self.model = AutoModel.from_pretrained(config['retrieval']['embedding_model'])
        self.model.eval()
        
    def process_pdf(self, pdf_path: str) -> ProcessedPaper:
        """Process a PDF file using S2ORC tools."""
        # Convert PDF to S2ORC JSON format
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.json"
            
            try:
                subprocess.run([
                    "python", 
                    str(self.s2orc_path / "doc2json/grobid2json/process_pdf.py"),
                    "-i", pdf_path,
                    "-o", str(output_path),
                    "--fulltext"
                ], check=True)
                
                with open(output_path, encoding='utf-8') as f:
                    paper_json = json.load(f)
                    
                return self._parse_s2orc_json(paper_json)
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to process PDF: {e}")
                raise
    
    def _parse_s2orc_json(self, paper_json: Dict) -> ProcessedPaper:
        """Parse S2ORC JSON format into ProcessedPaper."""
        # Extract basic metadata
        metadata = {
            "paper_id": paper_json.get("paper_id"),
            "doi": paper_json.get("doi"),
            "authors": paper_json.get("authors", []),
            "year": paper_json.get("year"),
            "venue": paper_json.get("venue")
        }
        
        # Extract sections
        sections = []
        for section in paper_json.get("body_text", []):
            sections.append({
                "heading": section.get("section", ""),
                "text": section.get("text", "")
            })
        
        # Extract references
        references = []
        for ref in paper_json.get("bib_entries", {}).values():
            references.append({
                "title": ref.get("title", ""),
                "authors": ref.get("authors", []),
                "year": ref.get("year"),
                "venue": ref.get("venue")
            })
        
        # Create full text
        full_text = "\n\n".join(
            section["text"] for section in sections
        )
        
        # Create chunks
        chunks = self._create_chunks(full_text)
        
        return ProcessedPaper(
            title=paper_json.get("title", ""),
            abstract=paper_json.get("abstract", [{}])[0].get("text", ""),
            full_text=full_text,
            sections=sections,
            references=references,
            chunks=chunks,
            metadata=metadata
        )
    
    def _create_chunks(self, text: str, chunk_size: int = 512) -> List[str]:
        """Split text into chunks of approximately equal size."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(self.tokenizer.encode(sentence))
            
            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks
    
    def rerank_chunks(
        self,
        query: str,
        chunks: List[str],
        top_k: int = 5
    ) -> List[str]:
        """Rerank chunks based on similarity to query."""
        # Get query embedding
        query_tokens = self.tokenizer(
            query,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )
        
        with torch.no_grad():
            query_embedding = self.model(**query_tokens).last_hidden_state.mean(dim=1)
        
        # Get chunk embeddings
        chunk_embeddings = []
        for chunk in chunks:
            tokens = self.tokenizer(
                chunk,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )
            with torch.no_grad():
                embedding = self.model(**tokens).last_hidden_state.mean(dim=1)
                chunk_embeddings.append(embedding)
        
        # Calculate similarities
        similarities = []
        for emb in chunk_embeddings:
            similarity = torch.cosine_similarity(query_embedding, emb)
            similarities.append(similarity.item())
        
        # Get top-k chunks
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [chunks[i] for i in top_indices]
    
    def summarize_chunks(
        self,
        chunks: List[str],
        max_length: int = 200
    ) -> str:
        """Summarize a list of chunks."""
        # Combine chunks
        combined_text = " ".join(chunks)
        
        # Use the model to generate summary
        inputs = self.tokenizer(
            f"Summarize: {combined_text}",
            return_tensors="pt",
            max_length=1024,
            truncation=True
        )
        
        with torch.no_grad():
            summary_ids = self.model.generate(
                inputs["input_ids"],
                max_length=max_length,
                min_length=50,
                num_beams=4,
                no_repeat_ngram_size=2
            )
            
        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary