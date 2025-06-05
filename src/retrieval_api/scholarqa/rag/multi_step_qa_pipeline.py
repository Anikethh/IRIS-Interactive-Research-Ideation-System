import json
import logging
import re
import os
from enum import Enum
from typing import Tuple, Dict, List, Any, Generator

import pandas as pd
from pydantic import BaseModel, Field
from tqdm import tqdm

from scholarqa.llms.constants import GPT_4o
from scholarqa.llms.litellm_helper import batch_llm_completion, llm_completion
from scholarqa.llms.prompts import USER_PROMPT_PAPER_LIST_FORMAT, USER_PROMPT_QUOTE_LIST_FORMAT, \
    PROMPT_ASSEMBLE_NO_QUOTES_SUMMARY
from scholarqa.utils import CompletionResult, get_ref_author_str, make_int, get_paper_metadata
from anyascii import anyascii

logger = logging.getLogger(__name__)
import litellm
# litellm.set_verbose=True

# Regular expressions to fix weird formatting issues cause after citation linking in the evidences
CLOSE_BRACKET_PATTERN = r'(?<![\[|,\s*\d])(\d+\])'  # (Doe et al., 2024)10] --> (Doe et al., 2024)[10]
OPEN_BRACKET_PATTERN = r"(\[[\d+,]+),(?=[^\[]*$)"  # [8,9,(Doe et al., 2024) --> [8,9](Doe et al., 2024)


class DimFormat(str, Enum):
    SYNTHESIS = "synthesis"
    LIST = "list"


class Dimension(BaseModel):
    name: str = Field(default=None, description=(
        "The name of the dimension"
    ))
    format: DimFormat = Field(default=None, description=(
        "The generation format of the dimension - can be either list of synthesis"
    ))
    quotes: List[int] = Field(default=None, description=(
        "A list of indices of paper quotes in the dimension, can be empty if no relevant quotes are found"
    ))


class ClusterPlan(BaseModel):
    cot: str = Field(default=None, description=(
        "The justification for every dimension name and its format"
    ))
    dimensions: List[Dimension] = Field(default=None, description=(
        "The list of dimensions along with the associated quote indices as per the cot plan"
    ))

    @classmethod
    def get_gemini_schema(cls):
        """Create a Gemini-compatible schema without default values"""
        return {
            "type": "object",
            "properties": {
                "cot": {
                    "type": "string",
                    "description": "The justification for every dimension name and its format"
                },
                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name of the dimension"
                            },
                            "format": {
                                "type": "string",
                                "enum": ["synthesis", "list"],
                                "description": "The generation format of the dimension - can be either list of synthesis"
                            },
                            "quotes": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "A list of indices of paper quotes in the dimension, can be empty if no relevant quotes are found"
                            }
                        },
                        "required": ["name", "format", "quotes"]
                    }
                }
            },
            "required": ["cot", "dimensions"]
        }


def validate_api_keys():
    """Validate that all required API keys are available."""
    # Check if we're in Azure OpenAI deployment mode
    deploy_mode = os.environ.get('DEPLOY', 'false').lower() == 'true'
    
    if deploy_mode:
        # In Azure OpenAI mode, we need Azure OpenAI keys instead of regular OpenAI/Gemini
        required_keys = {
            'AZURE_OPENAI_API_KEY': 'Azure OpenAI API key',
            'AZURE_OPENAI_ENDPOINT': 'Azure OpenAI endpoint',
            'HUGGINGFACE_API_KEY': 'Hugging Face API key',
            'SEMANTIC_SCHOLAR_API_KEY': 'Semantic Scholar API key'
        }
    else:
        # In regular mode, we need the standard API keys
        required_keys = {
            'OPENAI_API_KEY': 'OpenAI API key',
            'HUGGINGFACE_API_KEY': 'Hugging Face API key',
            'SEMANTIC_SCHOLAR_API_KEY': 'Semantic Scholar API key',
            'GEMINI_API_KEY': 'Google AI (Gemini) API key'
        }
    
    missing_keys = []
    for env_var, description in required_keys.items():
        if not os.environ.get(env_var):
            missing_keys.append(f"{description} ({env_var})")
    
    if missing_keys:
        mode_info = "Azure OpenAI mode" if deploy_mode else "LiteLLM mode"
        # Convert to warnings instead of errors as requested
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Missing some API keys for {mode_info}. The following environment variables are not set:\n" + 
            "\n".join(f"- {key}" for key in missing_keys) +
            "\n\nSome features may be disabled. See .env.example for configuration details."
        )


def is_openai_api_key_available():
    """Check if the OpenAI API key is available in the environment."""
    return bool(os.environ.get('OPENAI_API_KEY'))


class MultiStepQAPipeline:
    def __init__(self, llm_model: str, fallback_llm: str = GPT_4o, batch_workers: int=20):
        # Validate API keys on initialization
        validate_api_keys()
        
        self.llm_model = llm_model
        self.fallback_llm = fallback_llm if is_openai_api_key_available() else None
        self.batch_workers = batch_workers

    def step_select_quotes(self, query: str, scored_df: pd.DataFrame, sys_prompt: str) -> Tuple[
        Dict[str, str], List[CompletionResult]]:

        logger.info(f"Querying {self.llm_model} to extract quotes from these papers with {self.batch_workers} parallel workers")
        import time as t
        t.sleep(5)
        tup_items = {k: v for k, v in
                     zip(scored_df["reference_string"], scored_df["relevance_judgment_input_expanded"])}
        messages = [USER_PROMPT_PAPER_LIST_FORMAT.format(query, v) for k, v in tup_items.items()]
        completion_results = batch_llm_completion(self.llm_model, messages=messages, system_prompt=sys_prompt,
                                                  max_workers=self.batch_workers, max_tokens=4096, fallback=self.fallback_llm)
        import time as t
        t.sleep(5)
        quotes = [
            cr.content if cr.content != "None" and not cr.content.startswith("None\n") and not cr.content.startswith(
                "None ")
            else "" for cr in completion_results]
        per_paper_summaries = {t[0]: quote for t, quote in zip(tup_items.items(), quotes) if len(quote) > 10}
        per_paper_summaries = dict(sorted(per_paper_summaries.items(), key=lambda x: x[0]))
        return per_paper_summaries, completion_results

    def step_clustering(self, query: str, per_paper_summaries: Dict[str, str],
                        sys_prompt: str) -> Tuple[Dict[str, Any], CompletionResult]:
        def make_prompt(query: str, paper_paper_quotes_dict: Dict[str, str]) -> str:
            # paper_paper_quotes_dict is a dictionary with keys being the paper titles and values being the quotes
            # need to make a single string with all of the quotes
            quotes = ""
            for idx, (paper, quotes_str) in enumerate(paper_paper_quotes_dict.items()):
                # there are multiple quotes per paper
                quotes_str = quotes_str.replace("\n", "")
                quotes += f"[{idx}]\t{quotes_str}" + "\n"
            prompt = USER_PROMPT_QUOTE_LIST_FORMAT.format(query, quotes)
            return prompt

        user_prompt = make_prompt(query, per_paper_summaries)
        try:
            import time as t
            t.sleep(2)
            # Check if the model is a Gemini model
            if "gemini" in self.llm_model.lower():
                # Use the Gemini-compatible schema
                response = llm_completion(user_prompt=user_prompt,
                                          system_prompt=sys_prompt, fallback=None, model=self.llm_model,
                                          max_tokens=4096,
                                          response_format={"response_schema": ClusterPlan.get_gemini_schema()}
                                          )
            else:
                # For other models like GPT-4, use the standard Pydantic schema
                response = llm_completion(user_prompt=user_prompt,
                                          system_prompt=sys_prompt, fallback=None, model=self.llm_model,
                                          max_tokens=4096,
                                          response_format={"response_schema": ClusterPlan.model_json_schema(
                                              ref_template="/$defs/{model}")}
                                          )
            t.sleep(2)
        except Exception as e:
            logger.warning(f"Error while clustering with LLM: {e}")
            
            # Check if we have a working fallback
            if self.fallback_llm and is_openai_api_key_available():
                logger.info(f"Falling back to {self.fallback_llm}")
                try:
                    response = llm_completion(user_prompt=user_prompt,
                                             system_prompt=sys_prompt, fallback=None, model=self.fallback_llm,
                                             max_tokens=4096,
                                             response_format=ClusterPlan
                                             )
                except Exception as fallback_e:
                    logger.error(f"Fallback also failed: {fallback_e}")
                    # Return a minimal valid response as a last resort
                    minimal_response = CompletionResult(
                        content=json.dumps({
                            "cot": "Error in clustering, providing minimal response",
                            "dimensions": [
                                {"name": "Main points", "format": "synthesis", "quotes": [0]}
                            ]
                        }),
                        model="error_fallback",
                        cost=0.0,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0
                    )
                    return json.loads(minimal_response.content), minimal_response
            else:
                logger.warning("No fallback available (OPENAI_API_KEY not set). Using minimal response.")
                # Return a minimal valid response as a last resort
                minimal_response = CompletionResult(
                    content=json.dumps({
                        "cot": "Error in clustering, providing minimal response",
                        "dimensions": [
                            {"name": "Main points", "format": "synthesis", "quotes": [0]}
                        ]
                    }),
                    model="error_fallback",
                    cost=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0
                )
                return json.loads(minimal_response.content), minimal_response
                
            import time as t
            t.sleep(2)
        return json.loads(response.content), response

    def get_quote_citations(self, retrieval_df: pd.DataFrame, per_paper_summaries: Dict[str, str],
                            plan_json: Dict[str, List[int]]) -> Dict[str, List[str]]:
        """
        Map the quotes extracted in step 1 `per_paper_summaries` to their actual full length versions
        in retrieval_df and make a map of quote ref string --> [inline citations].

        i) First parse the plan json to get the required paper indices to be sent for the final generation in step 3.
        ii) For those papers, find the quotes from per_paper_summaries and passages from retrieval_df
        iii) Try to match the paper quotes as substrings to the corresponding paper passages to get the inline citations along with
        offsets.
        iv) First try matching the raw string (high precision), if unsuccessful, try matching only the alphabet characters (high recall).
        v) Once a match is found, use its offsets in the passage and iterate over the inline citations to find any that occur within the snippet.
        vi) In case of a raw string match, replace any citation mentions (if possible), with the paper id of the corresponding inline citation to be linked later.
        """
        per_paper_inline_cites = dict()
        # get all the ref strings for the clutering plan generated in step 2
        ref_str_list = [k for k in per_paper_summaries]
        req_ref_strs = {ref_str_list[item] for sublist in plan_json.values() for item in sublist if
                        item < len(ref_str_list)}
        if req_ref_strs:
            # filter the quotes according to the plan
            reqd_paper_summaries = {k: v for k, v in per_paper_summaries.items() if k in req_ref_strs}
            # filter the dataframe according to the plan
            reqd_ref_df = retrieval_df[retrieval_df["reference_string"].apply(lambda x: x in req_ref_strs)].copy()
            reqd_ref_df["sentence_alpha"] = reqd_ref_df["sentences"].apply(
                lambda x: [re.sub(r'[^a-zA-Z]', '', sentence["text"]).lower() for sentence in x])
            # iterate over the reqd_ref_df and get the snippets for each row from reqd_paper_summaries
            for row_idx, row in reqd_ref_df.iterrows():
                ref_str = row["reference_string"]
                curr_reqd_quotes = reqd_paper_summaries[ref_str].split("...")
                new_quotes = []
                sentences = row["sentences"]
                sent_alpa = row["sentence_alpha"]
                curr_inline_citations = set()
                curr_reqd_quotes_reg = [re.sub(r'[^a-zA-Z]', '', quote).lower() for quote in curr_reqd_quotes]
                for quote, quote_reg in zip(curr_reqd_quotes, curr_reqd_quotes_reg):
                    new_quote = quote.strip()
                    shift = 0  # keep track of changes to the offsets when the evidence is modified
                    for sidx, sentence in enumerate(sentences):
                        # can lookup exact string now since we prompt the llm to include the citations in the quotes
                        if sentence.get("ref_mentions"):
                            lookup_idx = sentence["text"].lower().find(quote.lower().strip())
                            raw_match = lookup_idx >= 0
                            if not raw_match:
                                lookup_idx = sent_alpa[sidx].find(quote_reg)
                            if lookup_idx >= 0:
                                lookup_end = lookup_idx + len(quote)
                                for sref in sentence["ref_mentions"]:
                                    if sref.get("start") >= lookup_idx and sref.get("end") <= lookup_end:
                                        curr_inline_citations.add(sref["matchedPaperCorpusId"])
                                        if raw_match:
                                            new_start, new_end = sref["start"] - lookup_idx, sref["end"] - lookup_idx
                                            cite_str = f"({sref['matchedPaperCorpusId']})"
                                            new_quote = new_quote[:new_start + shift] + cite_str + new_quote[
                                                                                                   new_end + shift:]
                                            shift += (len(cite_str) - sref["end"] + sref["start"])
                                curr_inline_citations.update(
                                    [sref["matchedPaperCorpusId"] for sref in sentence["ref_mentions"] if
                                     sref.get("start") >= lookup_idx and sref.get("end") <= lookup_end])
                                break

                    new_quotes.append(new_quote)
                per_paper_inline_cites[ref_str] = list(sorted(curr_inline_citations))
                new_quotes = "... ".join(new_quotes)
                # fix weird formatting
                new_quotes = re.sub(CLOSE_BRACKET_PATTERN, r'[\1',
                                    new_quotes)  # (Doe et al., 2024)10] --> (Doe et al., 2024)[10]
                new_quotes = re.sub(OPEN_BRACKET_PATTERN, r'\1]',
                                    new_quotes)  # [8,9,(Doe et al., 2024) --> [8,9](Doe et al., 2024)
                per_paper_summaries[ref_str] = new_quotes

        return per_paper_inline_cites

    def populate_citations_metadata(self, avl_paper_metadata: Dict[str, Dict[str, Any]],
                                    paper_inline_cites: Dict[str, List],
                                    per_paper_summaries: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        retrieve the metadata of the quote inline citations if not already present and update the quotes from string,
        to a dict of {"quote": quote, "inline_citations": {ref_str: abstract, ... }}.
        Also, link the citation mentions to modify them from (corpus_id) to (Doe et al., 2024)
        """
        corpus_id_ref_str_map = {ref_str[1:-1].split(" | ")[0]: ref_str for ref_str in per_paper_summaries}
        additional_citation_ids = {item for sublist in paper_inline_cites.values() for item in sublist if
                                   item not in avl_paper_metadata}
        if additional_citation_ids:
            logger.info(f"Fetching metadata for {len(additional_citation_ids)} additional inline citations")
            additional_metadata = get_paper_metadata(additional_citation_ids)
        else:
            additional_metadata = dict()
        per_paper_summaries = {k: {"quote": quote, "inline_citations": dict()} for k, quote in
                               per_paper_summaries.items()}
        for ref_str, cite_ids in paper_inline_cites.items():
            quote_cid = ref_str[1:-1].split(" | ")[0]
            # 2 sets of ref mentions, one where paper metadata is already available and the rest for which metadata was requested from s2 api
            curr_metadata = [avl_paper_metadata[cite_id] for cite_id in cite_ids if
                             cite_id in avl_paper_metadata]
            curr_metadata += [additional_metadata[cite_id] for cite_id in cite_ids if
                              cite_id in additional_metadata]
            for idx, mdata in enumerate(curr_metadata):
                mref_str = corpus_id_ref_str_map.get(mdata["corpusId"], f"[{mdata['corpusId']} | "
                                                                        f"{get_ref_author_str(mdata['authors'])} | "
                                                                        f"{make_int(mdata.get('year'))} "
                                                                        f"| Citations: {make_int(mdata['citationCount'])}]")
                mref_str = anyascii(mref_str)
                per_paper_summaries[ref_str]["quote"] = per_paper_summaries[ref_str]["quote"].replace(
                    f"({mdata['corpusId']})",
                    f"({get_ref_author_str(mdata['authors'])}, {make_int(mdata.get('year'))})")
                if mdata["corpusId"] in additional_metadata:
                    additional_metadata[mdata["corpusId"]]["relevance_judgement"] = max(
                        additional_metadata[mdata["corpusId"]].get("relevance_judgement", 0),
                        avl_paper_metadata[quote_cid]["relevance_judgement"])
                if mdata.get("abstract"):
                    per_paper_summaries[ref_str]["inline_citations"][mref_str] = mdata["abstract"]
            per_paper_summaries[ref_str]["quote"] = per_paper_summaries[ref_str]["quote"].replace("NULL, ", "")
        avl_paper_metadata.update(additional_metadata)
        return per_paper_summaries

    def extend_quote_citations(self, score_df: pd.DataFrame, per_paper_summaries: Dict[str, str],
                               plan_json: Dict[str, List[int]], paper_metadata: Dict[str, Any]):
        per_paper_inline_cites = self.get_quote_citations(score_df, per_paper_summaries, plan_json)
        per_paper_summaries_extd = self.populate_citations_metadata(paper_metadata, per_paper_inline_cites,
                                                                    per_paper_summaries)
        return per_paper_summaries_extd

    def generate_iterative_summary(self, query: str, per_paper_summaries_extd: Dict[str, Dict[str, Any]],
                                   plan: Dict[str, Any],
                                   sys_prompt: str) -> Generator[CompletionResult, None, None]:
        # first, we need to make a map from the index to the quotes because the llm is using index only

        # now fill in the prompt
        per_paper_summaries_tuples = [(ref_string, response) for ref_string, response in
                                      per_paper_summaries_extd.items()]
        # only use the section headings from the plan, discard the quote indices
        plan_str = "\n".join([k for k in plan])
        existing_sections = []
        i = 0
        for section_name, inds in tqdm(plan.items()):
            # inds are a string like this: "[1, 2, 3]"
            # get the quotes for each index
            quotes = ""
            for ind in inds:
                if ind < len(per_paper_summaries_tuples):
                    quotes += (
                            per_paper_summaries_tuples[ind][0] + ": " + str(per_paper_summaries_tuples[ind][
                                                                                1]) + "\n"
                    )
                else:
                    logger.warning(f"index {ind} out of bounds")
            # existing sections should have their summaries removed because they are confusing.
            # remove anything in []
            already_written = "\n\n".join(existing_sections)
            already_written = re.sub(r"\[.*?\]", "", already_written)
            fill_in_prompt_args = {
                "query": query,
                "plan": plan_str,
                "already_written": already_written,
                "section_name": section_name}
            if quotes:
                fill_in_prompt_args["section_references"] = quotes
                filled_in_prompt = sys_prompt.format(**fill_in_prompt_args)
            else:
                logger.warning(f"No quotes for section {section_name}")
                filled_in_prompt = PROMPT_ASSEMBLE_NO_QUOTES_SUMMARY.format(**fill_in_prompt_args)

            response = llm_completion(user_prompt=filled_in_prompt, model=self.llm_model, fallback=self.fallback_llm,
                                      max_tokens=4096)
            import time as t 
            t.sleep(5)
            existing_sections.append(response.content)
            yield response
