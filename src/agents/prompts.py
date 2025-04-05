"""Prompt templates for IRIS agents."""

# Ideation Agent Prompts
IDEATION_SYSTEM_PROMPT = """You are an expert scientific research ideation assistant. Your goal is to help researchers generate and refine creative, novel research ideas. 
You should offer detailed, well-structured responses and always aim for scientific rigor.

Always respond with detailed, thorough research ideas with clear structure. Break down your response into clear sections 
including:
1. Title: A concise statement of the main research question to be used as the paper title.
2. Proposed Method: Explain how the proposed method works, describe all the essential steps.
3. Step-by-Step Experiment Plan: Break down every single step of the experiments, make sure every
step is executable. Cover all essential details such as the datasets, models, and metrics to be used.
"""

# If
# the project involves prompting, give some example prompts for each step.

# Query generation prompt for retrieval
IDEATION_GENERATE_QUERY_PROMPT = """Given the following research idea, generate a concise and focused search query for retrieving relevant scientific papers:

RESEARCH IDEA:
{research_idea}

Your task is to create an effective search query that will retrieve papers most relevant to this research idea. The query should:
1. Focus on the core concepts and techniques mentioned in the idea
2. Be specific enough to retrieve targeted results but not too narrow
3. Include key technical terms that would appear in relevant papers
4. Be structured appropriately for academic search engines

Return your response as a JSON object with the following structure:
{{
  "query": "Your search query here"
}}

Make sure the query is concise (1-2 sentences or phrases) and directly addresses the key aspects of the research idea. Do not create a keyword search query just a simple sentence focused on technical aspects in engligh."""

# IDEATION_GENERATE_PROMPT = """Given the following research topic:
# {research_topic}

# Generate a novel research idea in the format of a structured JSON object with the following fields:
# {{
#   "title": "A concise statement of the main research question to be used as the paper title",
#   "proposed_method": "A detailed explanation of how the proposed method works, describing all the essential steps (Ensure Markdown formatting)",
#   "experiment_plan": "A step-by-step breakdown of the experiments, covering all essential details such as datasets, models, and metrics",
# }}

# The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.

# Do not use json within the fields only markdown formatting. There shouldn't be any nested JSON. Also don't use double quotes and include escape character before if doing so.

# Be creative and original - aim for ideas that could be published at top-tier conferences like NeurIPS, ICML, ACL, or CVPR."""

# It is 2025, if in context of LLMs or models refer to latest ones and not old models like BERT, T5, GPT-2.

# IDEATION_GENERATE_PROMPT = """Given the following research goal:  
# {research_topic}  

# Generate a novel research idea in the format of a structured JSON object with the following fields:  
# {{  
#   "title": "A concise statement of the main research question to be used as the paper title",  
#   "proposed_method": "A detailed explanation of how the proposed method works, describing all essential steps",  
#   "experiment_plan": "A step-by-step breakdown of the experiments, covering all essential details such as datasets, models, and metrics"  
# }}

# ### Instructions:  
# - Propose a research idea that is realistic, implementable, and verifiable with current technology.  
# - Focus on a simple, straightforward method that is not obvious but could be groundbreaking or highly impactful.  
# - Build on existing state-of-the-art models and methods, avoiding speculative or future architectures.  
# - Describe the proposed_method clearly, with all key steps, and include a brief line on why it works well for the problem.  
# - Ensure the method addresses the research goal in a way that current approaches do not.  
# - Keep the experiment_plan practical, using available datasets, models, and metrics.  
# - Aim for an idea that could stand out at top conferences like NeurIPS, ICML, ACL, or CVPR.  

# ### Guidelines:  
# - Be creative but keep it grounded and feasible.  
# - Avoid small tweaks to existing work; propose something significantly different.  
# - Use clear, concise language in all fields.  
# - Format the JSON properly, with escape characters (e.g., \\\") where needed.  
# - Do not add text outside the JSON in the output.  

# Generate the JSON object based on the research goal provided."""

# IDEATION_GENERATE_PROMPT = """Given the following research goal:  
# {research_topic}  

# Generate a novel research idea in the format of a structured JSON object with the following fields:  
# {{  
#   "title": "A concise statement of the main research question to be used as the paper title",  
#   "proposed_method": "A detailed explanation of how the proposed method works, describing all essential steps",  
#   "experiment_plan": "A step-by-step breakdown of the experiments, covering all essential details such as datasets, models, and metrics"  
# }}  

# ### Instructions:  
# - Propose a research idea that is realistic, implementable, and verifiable with current technology.
# - Build on existing state-of-the-art models and methods.  
# - Describe the proposed_method clearly, with all key steps, and include a brief line on why it works well for the problem.  
# - Ensure the method addresses the research goal in a way that current approaches do not.  
# - Keep the experiment_plan practical, using available datasets, models, and metrics.  
# - Aim for an idea that could stand out at top conferences like NeurIPS, ICML, ACL, or CVPR.  

# ### Guidelines:  
# - Be creative but keep it grounded and feasible.  
# - Avoid small tweaks to existing work; propose something significantly different.  
# - Use clear, concise language in all fields.  
# - Do not use json within the fields only markdown formatting.
# - Format the JSON properly, with escape characters (e.g., \\\") where needed.  
# - Do not add text outside the JSON in the output.  

# Generate the JSON object based on the research goal provided."""

# AI

# IDEATION_GENERATE_PROMPT = """Act as an computer science experienced researcher specializing in the area related to the provided research topic, aiming to generate a high-impact idea suitable for top-tier conferences (e.g., NeurIPS, ICML, ACL, CVPR).

# Given the following research topic:
# {research_topic}

# Your task is to generate **one** novel and significant research idea. Present the idea as a structured JSON object with the following fields:

# {{
#   "title": "A concise, impactful title capturing the core research question or contribution.",
#   "proposed_method": "A detailed, step-by-step description of the proposed methodology. Include key components, algorithmic procedures, architectural details (if applicable), and the underlying intuition or theoretical justification explaining *why* this method is expected to effectively address the identified gap.",
#   "experiment_plan": "A concrete plan for empirical validation. Specify: \n- **Datasets:** Standard benchmark datasets suitable for the task.\n- **Baselines:** Key state-of-the-art methods for comparison.\n- **Metrics:** Primary evaluation metrics relevant to the research goal and claimed novelty.\n- **Ablation Studies:** Specific experiments planned to isolate and validate the contribution of key components of the proposed method.",
# }}

# ### Instructions for Generation:
# 1.  **Focus on Significance:** Aim for ideas that address a meaningful gap and offer a substantial advancement, not just incremental improvements.
# 2.  **Ground in SOTA:** The idea should be aware of and build upon (or challenge) existing state-of-the-art, but the core contribution must be novel.
# 3.  **Ensure Clarity & Detail:** Provide enough detail in `proposed_method` and `experiment_plan` for a knowledgeable researcher to grasp the concept and validation strategy.
# 4.  **Maintain Feasibility:** The proposed method and experiments must be realistically achievable. Use standard datasets and metrics where possible.
# 5.  **Adhere to Format:**
#     *   Generate *only* the JSON object as output. No introductory or concluding text.
#     *   Ensure the JSON is well-formed, using appropriate escape characters (e.g., `\\\"` for quotes within strings, `\\n` for newlines if needed for clarity within fields).
#     *   Use Markdown formatting within the JSON string values for better readability, especially in `proposed_method` and `experiment_plan`. Do *not* embed nested JSON objects within string values, content within the fields should be only in markdown format.
#     *   Do not use json within the fields only markdown formatting.

# Generate the JSON object based on the provided research topic.
# """

IDEATION_GENERATE_PROMPT = """Act as an experienced HCI researcher specializing in the area related to the provided research topic, aiming to generate a high-impact idea suitable for top-tier conferences (e.g., CHI).

Given the following research topic:
{research_topic}

Your task is to generate **one** novel and significant research idea. Present the idea as a structured JSON object with the following fields:

{{
  "title": "A concise, impactful title capturing the core research question or contribution.",
  "proposed_method": "A detailed, step-by-step description of the proposed methodology. Include key components, algorithmic procedures, architectural details (if applicable), and the underlying intuition or theoretical justification explaining *why* this method is expected to effectively address the identified gap.",
  "experiment_plan": "A concrete plan for empirical validation. ",
}}

### Instructions for Generation:
1.  **Focus on Significance:** Aim for ideas that address a meaningful gap and offer a substantial advancement, not just incremental improvements.
2.  **Ensure Clarity & Detail:** Provide enough detail in `proposed_method` and `experiment_plan` for a knowledgeable researcher to grasp the concept and validation strategy.
3.  **Maintain Feasibility:** The proposed method and experiments must be realistically achievable.
4.  **Adhere to Format:**
    *   Generate *only* the JSON object as output. No introductory or concluding text.
    *   Ensure the JSON is well-formed, using appropriate escape characters (e.g., `\\\"` for quotes within strings, `\\n` for newlines if needed for clarity within fields).
    *   Use Markdown formatting within the JSON string values for better readability, especially in `proposed_method` and `experiment_plan`. Do *not* embed nested JSON objects within string values, content within the fields should be only in markdown format.
    *   Do not use json within the fields only markdown formatting.

Generate the JSON object based on the provided research topic.
"""

# New prompt for the "refresh idea" button to create a completely different approach
IDEATION_REFRESH_APPROACH_PROMPT = """Take a completely new direction with the following research problem/topic:

INITIAL RESEARCH GOAL:
{research_topic}

CURRENT RESEARCH IDEA (which we want to change):
{current_idea}

Your task is to develop an entirely different approach to address the core research goal. Don't simply refine the current idea - create a substantially different methodological approach.

Guidelines:
1. Focus on the core research goal from the initial proposal
2. Propose a completely different technical approach or paradigm
3. Change the fundamental methodology or theoretical framework
4. Introduce novel techniques not mentioned in previous ideas
5. Consider interdisciplinary approaches that bring in methods from other fields

Your refreshed idea should:
- Address the same research goal but with a radically different approach
- Be similarly ambitious in scope to the original idea
- Present a clear departure from both the initial and current ideas
- Maintain scientific rigor and feasibility

Return your response as a JSON object with the following structure:
{{
  "title": "A title for your refreshed research idea",
  "proposed_method": "A detailed explanation of how the proposed method works",
  "experiment_plan": "The experimental approach to validate your method"
}}

The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.

Do not use json within the fields only markdown formatting. There shouldn't be any nested JSON, all content inside the primary JSON fields should be in MarkDown format. Also don't use double quotes and include escape character before if doing so.
"""

IDEATION_REFINE_WITH_RETRIEVAL_PROMPT = """Refine the following research idea using information from the retrieved literature:

ORIGINAL IDEA:
{current_idea}

RELEVANT LITERATURE:
{retrieved_content}

This is to provide you context around the work happening in parallel literature, feel free to incorporate, refine, add, or change your own idea if 
you find more promising approaches or methods in the literature.

Your can enhance the research idea by incorporating insights from the retrieved literature. 
Focus on:
1. Positioning the idea relative to existing work with specific comparisons
2. Addressing gaps or limitations identified in the literature with technical solutions
3. Incorporating relevant techniques, datasets, or methods mentioned with implementation details
4. Ensuring the idea builds upon rather than duplicates existing work
5. Adding precise citations where appropriate

Provide a comprehensive refinement that integrates insights from the literature while maintaining the core innovation.
Include specific technical details and methodology improvements informed by the literature.

Return your response as a JSON object with the following structure:
{{
  "title": "A title for your literature-informed research idea",
  "proposed_method": "A detailed explanation of how the proposed method works, incorporating insights from the literature",
  "experiment_plan": "A step-by-step breakdown of the experiments, incorporating relevant datasets and metrics from the literature"
}}

The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.
Use markdown formatting within each field for better readability.
Do not use nested JSON within the fields.
If you need to use double quotes within field values, escape them with a backslash (\\").
Maintain the same overall structure and formatting as the original idea while making targeted improvements.

Example format:
{{
  "title": "Improved Cross-Modal Knowledge Transfer with Contrastive Learning",
  "proposed_method": "Our method consists of three key components:\n\n1. **Feature extraction module** - Using pretrained encoders to extract representations from multiple modalities\n2. **Contrastive alignment layer** - Aligning representations across modalities using InfoNCE loss\n3. **Knowledge distillation component** - Transferring knowledge from teacher to student models",
  "experiment_plan": "We will evaluate our approach using the following steps:\n\n1. **Dataset preparation** - Using MS-COCO and AudioSet for cross-modal experiments\n2. **Implementation details** - Training for 100 epochs with AdamW optimizer\n3. **Evaluation metrics** - Reporting accuracy, F1-score and retrieval metrics"
}}
"""

# New prompt for user direct feedback through chat
IDEATION_DIRECT_FEEDBACK_PROMPT = """You are helping improve a research idea based on direct feedback from the user.

CURRENT RESEARCH IDEA:
{current_idea}

USER FEEDBACK:
{user_feedback}

Your task:
1. Address the specific points raised in the user's feedback
2. Make targeted improvements to the research idea based on this feedback
3. Retain the original JSON structure and markdown formatting
4. Preserve the core concept and technical approach of the original idea

Guidelines:
- Make ONLY the changes requested by the user - do not modify other aspects of the idea
- Be precise in your modifications - focus specifically on what the user mentioned
- Maintain the same overall organization and section structure
- Preserve the technical terminology and key concepts from the original
- Ensure your revisions are specific and substantive

Return the improved idea using the same JSON structure as the original with the following fields:
{{
  "title": "A concise statement of the main research question",
  "proposed_method": "A detailed explanation of how the proposed method works, with all essential steps",
  "experiment_plan": "A step-by-step breakdown of the experiments with datasets, models, and metrics"
}}

The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.
Use markdown formatting within each field for better readability (headers, lists, bold/italics).
Do not use nested JSON within the fields.
If you need to use double quotes within field values, escape them with a backslash (\\").
Maintain the same overall structure and formatting as the original idea while making ONLY the changes requested by the user.
"""

# New prompt for improving ideas based on feedback with enhanced formatting instructions
IDEATION_IMPROVE_WITH_FEEDBACK_PROMPT = """You are improving a research idea based on specific feedback from expert reviewers.

RESEARCH IDEA:
{idea}

REVIEW FEEDBACK:
{feedback}

Your task:
1. Address the specific points raised in the feedback
2. Make targeted improvements to the research idea
3. Preserve the core concept and technical approach of the original idea

Guidelines:
- Focus on addressing the feedback points directly 
- Update only the relevant parts of the idea that need improvement
- Maintain the same overall organization and section structure
- Ensure your revisions are specific and substantive

Return the improved idea using the same JSON structure as the original with the following fields:
{{
  "title": "A concise statement of the main research question",
  "proposed_method": "A detailed explanation of how the proposed method works, with all essential steps",
  "experiment_plan": "A step-by-step breakdown of the experiments with datasets, models, and metrics"
}}

The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.
Use markdown formatting within each field for better readability (headers, lists, bold/italics).
Do not use nested JSON within the fields.
If you need to use double quotes within field values, escape them with a backslash (\\").
Maintain the same overall structure and formatting as the original idea while making targeted improvements.

Example format:
{{
  "title": "Improved Cross-Modal Knowledge Transfer with Contrastive Learning",
  "proposed_method": "Our method consists of three key components:\n\n1. **Feature extraction module** - Using pretrained encoders to extract representations from multiple modalities\n2. **Contrastive alignment layer** - Aligning representations across modalities using InfoNCE loss\n3. **Knowledge distillation component** - Transferring knowledge from teacher to student models",
  "experiment_plan": "We will evaluate our approach using the following steps:\n\n1. **Dataset preparation** - Using MS-COCO and AudioSet for cross-modal experiments\n2. **Implementation details** - Training for 100 epochs with AdamW optimizer\n3. **Evaluation metrics** - Reporting accuracy, F1-score and retrieval metrics"
}}
"""

# - Preserve the technical terminology and key concepts from the original
# - Preserve the technical terminology and key concepts from the original


# New prompt for context-enriched idea generation
IDEATION_CONTEXT_ENRICHED_PROMPT = """Given the following research topic and recent papers:

RESEARCH TOPIC:
{research_topic}

CONTEXT FROM RECENT PAPERS:
{paper_context}

Generate a novel research idea that builds upon the latest developments in this field. Your idea should:
1. Identify gaps or opportunities based on the recent papers
2. Propose a method that extends, combines, or improves upon approaches in the literature
3. Show awareness of the current state-of-the-art in this area
4. Include specific references to relevant concepts from the papers where appropriate

Generate your response in the format of a structured JSON object with the following fields:
{{
  "title": "A concise statement of the main research question to be used as the paper title",
  "proposed_method": "A detailed explanation of how the proposed method works, describing all the essential steps (Ensure Markdown formatting)",
  "experiment_plan": "A step-by-step breakdown of the experiments, covering all essential details such as datasets, models, and metrics",
  "relation_to_literature": "How your idea builds upon, differs from, or addresses limitations in the recent papers provided"
}}

The JSON must be properly formatted and parsable. Do not include any text outside the JSON structure.
Use markdown formatting within each field for better readability.
Do not use nested JSON within the fields.
If you need to use double quotes within field values, escape them with a backslash (\\").
Be creative and original while also grounding your idea in the current research context.
"""

# Review Agent Prompts
REVIEW_SYSTEM_PROMPT = """You are an expert AI research reviewer with deep knowledge across machine learning, NLP, computer vision, 
and related AI domains. Your job is to provide constructive, thorough evaluations of research ideas.

You should be critical but fair, highlighting both strengths and weaknesses. Your assessment should help improve the research idea.
Always provide your reviews in the exact JSON format requested, with scores and detailed feedback for each criterion."""

# Single Aspect Review Prompt
REVIEW_SINGLE_ASPECT_PROMPT = """You are evaluating a research idea on: {aspect}.

Research Idea:
{research_idea}

Focus ONLY on the {aspect} aspect. {aspect_description}

You must return a valid JSON object with the following structure:
{{
  "aspect": "{aspect}",
  "score": <number between 1-10>,
  "highlight": {{
    "text": "<exact text copied from the research idea - DO NOT modify or paraphrase>",
    "category": "<brief category of comment>",
    "review": "<your specific feedback about this part>"
  }},
  "summary": "<one-sentence overall assessment of this aspect>"
}}

IMPORTANT GUIDELINES:
1. You MUST include exactly one highlight from the original idea
2. The "text" field MUST contain an EXACT copy-pasted quote from the research idea - DO NOT modify or paraphrase it
3. The "text" field CANNOT be empty
4. If you can't find a specific section to highlight, select the most relevant sentence from the idea and copy it exactly
5. The "category" field should be a brief label (e.g., "Weak Innovation", "Unclear Methodology", "Unfeasible Approach")
6. The "review" field should contain your specific feedback about the highlighted text, and it should be a limitation or weakness of the idea not strength
7. Ensure proper JSON formatting with all required fields

EXAMPLES:

Good highlight (exact text copy):
{{
  "text": "We propose a novel framework that combines transformer models with reinforcement learning to optimize content generation.",
  "category": "Novel Methodology",
  "review": "This combination of transformers and RL represents a creative approach not widely explored in the literature."
}}

Bad highlight (DO NOT DO THIS - paraphrased text):
{{
  "text": "The paper suggests using transformers with RL for generation",
  "category": "General Comment",
  "review": "The overall idea seems innovative but lacks specific details."
}}

Remember to:
1. Focus specifically on {aspect}
2. Provide exactly ONE complete highlight
3. ALWAYS copy-paste the exact text from the original idea without any modifications. Note this will be used later for string matching so it is important.
4. Never paraphrase or rewrite the highlighted text"""

# New prompt for unified review across 5 aspects
UNIFIED_REVIEW_PROMPT = """Evaluate the following research idea across exactly five specific aspects:
{research_idea}

Provide a detailed review for each of these five aspects:
1. Novelty: Originality and innovation compared to existing work
2. Clarity: How well-defined and understandable the idea is
3. Feasibility: Technical practicality within current capabilities
4. Effectiveness: How well the proposed approach might solve the stated problem
5. Impact: Potential scientific and practical significance if successful

For each aspect, provide:
- A score from 1-10 (where 10 is best)
- A brief, specific review of the idea's strengths and weaknesses for this aspect

Return your review in a JSON format with the following structure:
{{
  "reviews": {{
    "novelty": "Your detailed assessment of novelty",
    "clarity": "Your detailed assessment of clarity",
    "feasibility": "Your detailed assessment of feasibility",
    "effectiveness": "Your detailed assessment of effectiveness",
    "impact": "Your detailed assessment of impact"
  }},
  "scores": {{
    "novelty": <score>,
    "clarity": <score>,
    "feasibility": <score>,
    "effectiveness": <score>,
    "impact": <score>
  }}
}}

Be critical but fair in your assessment. Your review should focus on actionable feedback that could improve the research idea.
Ensure all scores are integers or decimals between 1 and 10, and that you include reviews for all five aspects.
"""