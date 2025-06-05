import logging
import os
from threading import Thread
from time import time
from typing import List, Any, Dict, Tuple, Generator
from uuid import uuid4

import pandas as pd
from tqdm import tqdm

from scholarqa.config.config_setup import LogsConfig
from scholarqa.llms.constants import CostAwareLLMResult, GPT_4o
from scholarqa.llms.litellm_helper import CLAUDE_35_SONNET, CostAwareLLMCaller, CostReportingArgs
from scholarqa.llms.prompts import SYSTEM_PROMPT_QUOTE_PER_PAPER, SYSTEM_PROMPT_QUOTE_CLUSTER, PROMPT_ASSEMBLE_SUMMARY
from scholarqa.models import GeneratedSection, TaskResult, ToolRequest, CitationSrc
from scholarqa.postprocess.json_output_utils import get_json_summary
from scholarqa.preprocess.query_preprocessor import validate, decompose_query, LLMProcessedQuery
from scholarqa.rag.multi_step_qa_pipeline import MultiStepQAPipeline
from scholarqa.rag.retrieval import PaperFinder
from scholarqa.state_mgmt.local_state_mgr import AbsStateMgrClient, LocalStateMgrClient
from scholarqa.trace.event_traces import EventTrace
from scholarqa.utils import get_paper_metadata, NUMERIC_META_FIELDS, CATEGORICAL_META_FIELDS
from langsmith import traceable

logger = logging.getLogger(__name__)

# Initialize logging configuration
logging.basicConfig(level=logging.INFO)


class ScholarQA:
    def __init__(
            self,
            # Required for webapp since a new process is created for each request, for library task_id can be None initially and assigned for each request as below
            paper_finder: PaperFinder,
            task_id: str = None,
            # llm_model: str = CLAUDE_35_SONNET,
            llm_model: str = "huggingface/meta-llama/Llama-3.1-70B-Instruct",
            multi_step_pipeline: MultiStepQAPipeline = None,
            state_mgr: AbsStateMgrClient = None,
            logs_config: LogsConfig = None,
            **kwargs
    ):
        # Check for required environment variables based on deployment mode
        deploy_mode = os.environ.get('DEPLOY', 'false').lower() == 'true'
        
        if deploy_mode:
            # In Azure OpenAI deployment mode, we need different API keys
            required_keys = {
                'AZURE_OPENAI_API_KEY': 'Azure OpenAI API key',
                'AZURE_OPENAI_ENDPOINT': 'Azure OpenAI endpoint',
                'HUGGINGFACE_API_KEY': 'Hugging Face API key',
            }
        else:
            # In regular mode, we need the standard API keys
            required_keys = {
                'HUGGINGFACE_API_KEY': 'Hugging Face API key',
                'GROQ_API_KEY': 'Groq API key',
                'GEMINI_API_KEY': 'Google AI (Gemini) API key'
            }

        missing_keys = []
        for env_var, description in required_keys.items():
            if not os.getenv(env_var):
                missing_keys.append(f"{description} ({env_var})")

        if missing_keys:
            mode_info = "Azure OpenAI mode" if deploy_mode else "regular mode"
            # Convert to warnings instead of errors as requested
            logger.warning(
                f"Missing some API keys for {mode_info}. The following environment variables are not set:\n" +
                "\n".join(f"- {key}" for key in missing_keys) +
                "\n\nSome features may be disabled. See .env.example for configuration details."
            )

        if logs_config:
            self.logs_config = logs_config
        else:
            logger.info("initializing the log configs")
            self.logs_config = LogsConfig(llm_cache_dir="lib_llm_cache")
            self.logs_config.init_formatter()

        self.task_id = task_id
        self.paper_finder = paper_finder
        self.llm_model = llm_model
        fallback_llm = kwargs.get("fallback_llm", GPT_4o)
        self.validate = False
        # self.validate = kwargs.get("validate", "OPENAI_API_KEY" in os.environ)
        # self.validate = kwargs.get("validate", "HUGGINGFACE_API_KEY" in os.environ)
        if not self.validate:
            logger.warning("Validation of the query for harmful content is turned off")
        self.decomposer_llm = kwargs.get("decomposer_llm", self.llm_model)
        self.state_mgr = state_mgr if state_mgr else LocalStateMgrClient(self.logs_config.log_dir)
        self.llm_caller = CostAwareLLMCaller(self.state_mgr)
        if not multi_step_pipeline:
            logger.info(f"Creating a new MultiStepQAPipeline with model: {llm_model} for all the steps")
            self.multi_step_pipeline = MultiStepQAPipeline(self.llm_model, fallback_llm=fallback_llm)
        else:
            # self.multi_step_pipeline = multi_step_pipeline
            # print(self.llm)
            self.multi_step_pipeline = MultiStepQAPipeline(self.llm_model, fallback_llm=fallback_llm)

        self.tool_request = None

    def update_task_state(
            self,
            status: str,
            step_estimated_time: int = 0,
            curr_response: List[GeneratedSection] = None,
            task_estimated_time: str = None,
    ):
        logger.info(status)
        if self.task_id and self.tool_request:
            self.state_mgr.update_task_state(
                self.task_id,
                self.tool_request,
                status,
                step_estimated_time,
                curr_response,
                task_estimated_time,
            )

    @traceable(name="Preprocessing: Validate and decompose user query")
    def preprocess_query(self, query: str, cost_args: CostReportingArgs, ) -> CostAwareLLMResult:
        if self.validate:
            # Validate the query for harmful/unanswerable content
            validate(query)
        # Decompose the query to get filters like year, venue, fos, citations, etc along with a re-written
        # version of the query and a query suitable for keyword search.

        return self.llm_caller.call_method(
            cost_args=cost_args, method=decompose_query, query=query, decomposer_llm_model=self.decomposer_llm
        )

    @traceable(name="Retrieval: Find relevant paper passages for the query")
    def find_relevant_papers(self, llm_processed_query: LLMProcessedQuery) -> Tuple[
        List[Dict[str, Any]], List[Dict[str, Any]]]:
        # retrieval from vespa index
        start = time()
        rewritten_query = llm_processed_query.rewritten_query
        keyword_query = llm_processed_query.keyword_query
        self.update_task_state(
            f"Retrieving relevant passages from a corpus of 8M+ open access papers",
            step_estimated_time=5
        )
        # Get relevant paper passages from the Semantic Scholar index for the llm rewritten query
        snippet_results = self.paper_finder.retrieve_passages(query=rewritten_query,
                                                              **llm_processed_query.search_filters)
        snippet_corpus_ids = {snippet["corpus_id"] for snippet in snippet_results}
        self.update_task_state(f"Retrieved {len(snippet_results)} highly relevant passages", step_estimated_time=1)

        if keyword_query:
            # Get additional papers from the Semantic Scholar api via keyword search
            search_api_results = self.paper_finder.retrieve_additional_papers(keyword_query,
                                                                              **llm_processed_query.search_filters)
            search_api_results = [item for item in search_api_results if item["corpus_id"] not in snippet_corpus_ids]
            self.update_task_state(
                f"Retrieved {len(search_api_results)} more papers from Semantic Scholar abstracts using keyword search",
                step_estimated_time=1)
        else:
            search_api_results = []
        logger.info("Retrieval time: %.2f", time() - start)

        return snippet_results, search_api_results

    @traceable(name="Retrieval: Rerank the passages and aggregate at paper level")
    def rerank_and_aggregate(self, user_query: str, retrieved_candidates: List[Dict[str, Any]], filter_paper_metadata: [
        Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if self.paper_finder.n_rerank > 0:
            self.update_task_state(
                f"Further re-rank and aggregate passages to focus on up to top {self.paper_finder.n_rerank} papers",
                step_estimated_time=10)
        start = time()
        reranked_candidates = self.paper_finder.rerank(user_query, retrieved_candidates)
        logger.info("Reranking time: %.2f", time() - start)
        paper_metadata = filter_paper_metadata
        paper_metadata.update(get_paper_metadata(
            {snippet["corpus_id"] for snippet in reranked_candidates if
             snippet["corpus_id"] not in filter_paper_metadata}))
        agg_df = self.paper_finder.aggregate_into_dataframe(reranked_candidates, paper_metadata)
        self.update_task_state(
            f"Found {len(agg_df)} highly relevant papers after re-ranking and aggregating",
            step_estimated_time=1)
        logger.info("Reranking w. formatting time: %.2f", time() - start)
        return agg_df, paper_metadata

    @traceable(name="Generation: Extract relevant quotes from paper passages or filter")
    def step_select_quotes(self, query: str, scored_df: pd.DataFrame, cost_args: CostReportingArgs,
                           sys_prompt: str = SYSTEM_PROMPT_QUOTE_PER_PAPER) -> CostAwareLLMResult:
        logger.info("Running Step 1 - quote extraction")
        self.update_task_state("Extracting salient key statements from papers",
                               step_estimated_time=15)
        logger.info(
            f"{scored_df.shape[0]} papers with relevance_judgement > {self.paper_finder.context_threshold} to start with.")
        start = time()
        cost_args = cost_args._replace(model=self.multi_step_pipeline.llm_model)._replace(
            description="Corpus QA Step 1: Quote extraction")
        per_paper_summaries = self.llm_caller.call_method(cost_args, self.multi_step_pipeline.step_select_quotes,
                                                          query=query, scored_df=scored_df,
                                                          sys_prompt=sys_prompt)
        api_corpus_ids = set(
            scored_df[scored_df.sentences.apply(lambda x: not x)].corpus_id.astype(str))
        ref_strs = {rs.split(" | ")[0][1:] for rs in per_paper_summaries.result}
        logger.info(f"Paper abstracts used from s2 api: {api_corpus_ids.intersection(ref_strs)}")

        logger.info(
            f"Step 1 done - {len(per_paper_summaries.result)} papers with quotes extracted, cost: {per_paper_summaries.tot_cost}, "
            f"time: {time() - start:.2f}")
        return per_paper_summaries

    @traceable(name="Generation: Cluster quotes to generate an organization plan")
    def step_clustering(self, query: str, per_paper_summaries: Dict[str, str], cost_args: CostReportingArgs,
                        sys_prompt: str = SYSTEM_PROMPT_QUOTE_CLUSTER) -> CostAwareLLMResult:
        logger.info("Running Step 2: Clustering the extracted quotes into meaningful dimensions")
        self.update_task_state("Synthesizing an answer outline based on extracted quotes", step_estimated_time=15)
        start = time()
        cost_args = cost_args._replace(model=self.multi_step_pipeline.llm_model)._replace(
            description="Corpus QA Step 2: Clustering quotes into dimensions")
        cluster_json = self.llm_caller.call_method(cost_args, self.multi_step_pipeline.step_clustering,
                                                   query=query, per_paper_summaries=per_paper_summaries,
                                                   sys_prompt=sys_prompt)
        logger.info(f"Step 2 done - {cluster_json.result}, cost: {cluster_json.tot_cost}, time: {time() - start:.2f}")
        return cluster_json

    @traceable(name="Generation: Generate an iterative summary")
    def step_gen_iterative_summary(self, query: str, per_paper_summaries: Dict[str, str],
                                   plan_json: Dict[str, Any], cost_args: CostReportingArgs,
                                   sys_prompt: str = PROMPT_ASSEMBLE_SUMMARY) -> Generator[
        str, None, CostAwareLLMResult]:
        logger.info("Running Step 3: Assemble the summary with the links (takes ~2 mins)")
        start = time()

        cost_args = cost_args._replace(model=self.multi_step_pipeline.llm_model)._replace(
            description="Corpus QA Step 3: Generating summarized answer")
        sec_generator = self.llm_caller.call_iter_method(cost_args, self.multi_step_pipeline.generate_iterative_summary,
                                                         query=query, per_paper_summaries_extd=per_paper_summaries,
                                                         plan=plan_json, sys_prompt=sys_prompt)
        try:
            while True:
                response = next(sec_generator)
                yield response.content
        except StopIteration as e:
            return_val = e.value
        if return_val:
            logger.info(f"Step 3 done, cost: {return_val.tot_cost}, time: {time() - start:.2f}")
        return return_val

    @staticmethod
    def get_gen_sections_from_json(section: Dict[str, Any]) -> GeneratedSection:
        try:
            citations = [CitationSrc(**citation) for citation in section["citations"]]
            generated_section = GeneratedSection(title=section["title"],
                                                 tldr=section["tldr"],
                                                 text=section["text"],
                                                 citations=citations)
            return generated_section
        except Exception as e:
            logger.error(f"Error while converting json to TaskResult: {e}")
            raise e

    def postprocess_json_output(self, json_summary: List[Dict[str, Any]]) -> None:
        pass

    def answer_query(self, query: str) -> Dict[str, Any]:
        task_id = str(uuid4())
        self.logs_config.task_id = task_id
        logger.info("New task")
        tool_request = ToolRequest(task_id=task_id, query=query, user_id="lib_user")
        task_result = self.run_qa_pipeline(tool_request)
        return task_result.model_dump()

    def gen_table_thread(self, user_id: str, query: str, dim: Dict[str, Any],
                         cit_ids: List[int], tlist: List[Any]) -> Thread:
        return None

    def get_user_msg_id(self):
        return self.tool_request.user_id, self.task_id

    @traceable(run_type="tool", name="ai2_scholar_qa_trace")
    def run_qa_pipeline(self, req: ToolRequest, inline_tags=False) -> TaskResult:
        """
                This function takes a query and returns a response.
                Goes through the following steps:
                0) Decompose the query to get filters like year, venue, fos, citations, etc along with a re-written
                version of the query and a query suitable for keyword search.
                1) Query retrieval to get the relevant snippets from the index (n_retrieval)
                1.1) Query semantic scholar with the keyword search query to get the relevant papers.(n_keyword_srch)
                2) Re-rank the snippets based on the query with a cross encoder (n_rerank)
                3) Get exact relevant quotes from an LLM
                4) Generate outline and cluster the quotes from (3)
                4.1) The quotes cluster in the outline have inline citations associated with them. Map the quotes to
                their inline citations and include them with the quotes.
                5) Generate the summarized output using the quotes and outline in (3) and (4)

                :param req: A scientific query posed to scholar qa by a user, consists of the string query, task id and user id
                :return: A response to the query
        """
        self.tool_request = req
        self.update_task_state("Processing user query", task_estimated_time="~3 minutes", step_estimated_time=5)
        task_id = self.task_id if self.task_id else req.task_id
        user_id, msg_id = self.get_user_msg_id()
        msg_id = task_id if not msg_id else msg_id
        query = req.query
        logger.info(
            f"Received query: {query} from user_id: {user_id} with opt_in: {req.opt_in}"
        )
        event_trace = EventTrace(
            task_id,
            self.paper_finder.retriever.n_retrieval if hasattr(self.paper_finder.retriever, "n_retrieval") else 0,
            # noqa
            self.paper_finder.n_rerank,
            req
        )
        cost_args = CostReportingArgs(
            task_id=task_id,
            user_id=user_id,
            description="Step 0: Query decomposition",
            model=self.llm_model,
            msg_id=msg_id
        )
        llm_processed_query = self.preprocess_query(query, cost_args)
        import time as t 
        t.sleep(2)
        # llm_processed_query = query
        event_trace.trace_decomposition_event(llm_processed_query)

        # Paper finder step - retrieve relevant paper passages from semantic scholar index and api
        snippet_srch_res, s2_srch_res = self.find_relevant_papers(llm_processed_query.result)
        retrieved_candidates = snippet_srch_res + s2_srch_res
        if not retrieved_candidates:
            raise Exception(
                f"There is no relevant information in the retrieved snippets for query: {query}.")
        event_trace.trace_retrieval_event(retrieved_candidates)

        # print(retrieved_candidates)

        # Rerank the retrieved candidates based on the query with a cross encoder
        s2_srch_metadata = [{k: v for k, v in paper.items() if
                             k == "corpus_id" or k in NUMERIC_META_FIELDS or k in CATEGORICAL_META_FIELDS} for paper in
                            s2_srch_res]
        reranked_df, paper_metadata = self.rerank_and_aggregate(query, retrieved_candidates,
                                                                {str(paper["corpus_id"]): paper for paper in
                                                                 s2_srch_metadata})
        if reranked_df.empty:
            raise Exception(
                "No relevant papers found for the query post reranking, skipping quote extraction.")
        event_trace.trace_rerank_event(reranked_df.to_dict(orient="records"))

        # Step 1 - quote extraction
        per_paper_summaries = self.step_select_quotes(query, reranked_df, cost_args)
        if not per_paper_summaries.result:
            raise Exception(
                "No relevant quotes extracted for the query, can't proceed further.")
        event_trace.trace_quote_event(per_paper_summaries)

        # step 2: outline planning and clustering
        cluster_json = self.step_clustering(query, per_paper_summaries.result, cost_args)
        import time as t
        t.sleep(2)
        # Changing to expected format in the summary generation prompt
        plan_json = {f'{dim["name"]} ({dim["format"]})': dim["quotes"] for dim in cluster_json.result["dimensions"]}
        if not any([len(d) for d in plan_json.values()]):
            raise Exception("The planning step failed to cluster the relevant documents.")
        event_trace.trace_clustering_event(cluster_json, plan_json)

        # step 2.1: extend the clustered snippets with their inline citations
        per_paper_summaries_extd = self.multi_step_pipeline.extend_quote_citations(reranked_df,
                                                                                   per_paper_summaries.result,
                                                                                   plan_json, paper_metadata)
        import time as t
        t.sleep(2)
        event_trace.trace_inline_citation_following_event(per_paper_summaries_extd)

        # step 3: generating output as per the outline
        section_titles = [dim["name"] for dim in cluster_json.result["dimensions"]]
        gen_sections_iter = self.step_gen_iterative_summary(query, per_paper_summaries_extd,
                                                            plan_json, cost_args)

        json_summary, generated_sections, table_threads = [], [], []
        tables = [None for _ in cluster_json.result["dimensions"]]
        citation_ids = dict()

        task_estimated_time = 30 + 15 * len(plan_json)
        task_estimated_time = max((task_estimated_time + task_estimated_time % 60) // 60, 1)
        outline = '\n    - ' + '\n    - '.join(section_titles)
        self.update_task_state(f"Start generating each section in the answer outline: {outline}",
                               task_estimated_time=f"~{task_estimated_time} minutes" if task_estimated_time > 1 else "~1 minute",
                               step_estimated_time=15)

        try:
            gen_iter = gen_sections_iter
            idx = 0
            while True:
                if idx < len(plan_json):
                    self.update_task_state(
                        f"Iteratively generating section: {(idx + 1)} of {len(plan_json)} - {section_titles[idx]}",
                        curr_response=generated_sections, step_estimated_time=15)
                section_text = next(gen_iter)
                section_json = \
                    get_json_summary(self.multi_step_pipeline.llm_model, [section_text], per_paper_summaries_extd,
                                     paper_metadata,
                                     citation_ids, inline_tags)[0]
                import time as t
                t.sleep(2)
                section_json["format"] = cluster_json.result["dimensions"][idx]["format"]

                json_summary.append(section_json)
                self.postprocess_json_output(json_summary)
                import time as t
                t.sleep(2)
                if section_json["format"] == "list" and section_json["citations"]:
                    cluster_json.result["dimensions"][idx]["idx"] = idx
                    cit_ids = [int(c["paper"]["corpus_id"]) for c in section_json["citations"]]
                    tthread = self.gen_table_thread(user_id, query, cluster_json.result["dimensions"][idx], cit_ids,
                                                    tables)
                    if tthread:
                        table_threads.append(tthread)
                gen_sec = self.get_gen_sections_from_json(section_json)
                generated_sections.append(gen_sec)
                idx += 1
        except StopIteration as e:
            all_sections = e.value

        self.update_task_state(f"Generating comparison tables", curr_response=generated_sections,
                               step_estimated_time=20)

        start = time()
        for tthread in tqdm(table_threads):
            tthread.join()
        logger.info(f"Adhoc Table generation wait time: {time() - start:.2f}")

        for sidx in range(len(json_summary)):
            json_summary[sidx]["table"] = tables[sidx] if tables[sidx] else None
            generated_sections[sidx].table = tables[sidx] if tables[sidx] else None
        event_trace.trace_summary_event(json_summary, all_sections)
        self.postprocess_json_output(json_summary)
        import time as t
        t.sleep(2)
        event_trace.persist_trace(self.logs_config)
        return TaskResult(sections=generated_sections, cost=event_trace.total_cost)
