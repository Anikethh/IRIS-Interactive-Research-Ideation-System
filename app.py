from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit
import os
import math  # Add math module for UCT calculations
from src.mcts.node import MCTSState, MCTSNode
from src.mcts.tree import MCTS
from pathlib import Path
from werkzeug.utils import secure_filename
import uuid
from src.agents.structured_review import StructuredReviewAgent
from src.agents.ideation import IdeationAgent
from src.agents.review import ReviewAgent
import json
import re
import yaml
import traceback
import sys
import logging
import click

logger = logging.getLogger(__name__)

# Remove the old external path and use local scholarqa package
sys.path.insert(0, str(Path(__file__).parent / "src" / "retrieval_api"))
from scholarqa import ScholarQA
from scholarqa.rag.retrieval import PaperFinder, PaperFinderWithReranker
from scholarqa.rag.retriever_base import FullTextRetriever
from scholarqa.rag.reranker.modal_engine import ModalReranker
from scholarqa.rag.reranker.modal_engine import HuggingFaceReranker
import pymupdf  # PyMuPDF for PDF parsing
# Import the key manager
# from src.utils.key_manager import encrypt_api_key, decrypt_api_key, get_client_encryption_script

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'secret!')
socketio = SocketIO(app)

# Create uploads directory if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Create a secure key directory for storing encrypted keys if not exists
SECURE_KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secure_keys')
os.makedirs(SECURE_KEYS_DIR, exist_ok=True)

# Initialize knowledge storage
knowledge_chunks = []

# Initialize empty storage
chat_messages = []
main_idea = "Generating Research Idea..."
retrieval_results = {}

def allowed_file(filename):
    """Check if the file extension is allowed"""
    # Get file extension (last part after the dot)
    extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return extension in {
        "txt",
        "pdf",
        "doc",
        "docx",
    }

# Function to safely load API keys from environment or config file
def get_api_key(key_name, config_dict):
    """Get API key from environment variable with preference to environment variable"""
    env_var_name = f"{key_name.upper()}_API_KEY"
    env_key = os.environ.get(env_var_name)
    
    if env_key:
        return env_key
    
    # Never return sensitive keys from config in production
    if os.environ.get('FLASK_ENV') == 'production':
        return None
        
    # Only fall back to config file in development
    if "keys" in config_dict and key_name in config_dict["keys"]:
        return config_dict["keys"][key_name]
    
    return None

def extract_abstract(pdf_text):
    full_text = "\n".join(pdf_text)
    match = re.search(r"(Abstract.*?)(\n|Introduction|Keywords|1\.)", full_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "No abstract found."

# Initialize MCTS
mcts = MCTS("config/config.yaml")
current_root = None
current_node = None
current_state = None
exploration_in_progress = False

# Initialize agents
structured_review_agent = StructuredReviewAgent("config/config.yaml")
ideation_agent = IdeationAgent("config/config.yaml")
review_agent = ReviewAgent("config/config.yaml")  # Initialize review agent directly

# Get the configuration from config.yaml
import yaml
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Set Semantic Scholar API key
s2_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
if not s2_api_key:
    logger.warning("SEMANTIC_SCHOLAR_API_KEY environment variable is not set. Semantic Scholar API features will be disabled.")
    os.environ['SEMANTIC_SCHOLAR_API_KEY'] = ''
else:
    os.environ['SEMANTIC_SCHOLAR_API_KEY'] = s2_api_key

# Set Google API key securely only if not in Azure OpenAI deployment mode
deploy_mode = os.environ.get('DEPLOY', 'false').lower() == 'true'
if not deploy_mode:
    gemini_key = get_api_key("googleaistudio", config)
    if gemini_key:
        os.environ['GEMINI_API_KEY'] = gemini_key
else:
    # In Azure OpenAI mode, ensure Azure OpenAI keys are available
    azure_key = os.environ.get("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not azure_key:
        logger.warning("AZURE_OPENAI_API_KEY not set while in deployment mode")
    if not azure_endpoint:
        logger.warning("AZURE_OPENAI_ENDPOINT not set while in deployment mode")

retriever = FullTextRetriever(n_retrieval=10, n_keyword_srch=10)
# paper_finder = PaperFinder(retriever, context_threshold=0.1)
reranker = HuggingFaceReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", batch_size=256)
paper_finder = PaperFinderWithReranker(retriever, reranker=reranker, n_rerank=5, context_threshold=0.1)
scholar_qa = ScholarQA(paper_finder=paper_finder, llm_model="gemini/gemini-2.0-flash-lite")

# API Key management endpoints with improved security
@app.route("/api/set_api_key", methods=["POST"])
def set_api_key():
    """Save an API key securely"""
    try:
        # Verify request contains required data
        data = request.get_json()
        if not data or "provider" not in data or "key" not in data:
            return jsonify({"error": "Missing required fields"}), 400
            
        provider = data["provider"]
        api_key = data["key"]
        
        # Validate API key format based on provider
        key_formats = {
            "openai": r"^sk-[A-Za-z0-9]{48}$",
            "claude": r"^sk-ant-[A-Za-z0-9]{32,}$",
            "deepseek": r"^[A-Za-z0-9]{32,}$",
            "gemini": r"^AIza[A-Za-z0-9_-]{35}$",
            "semantic_scholar": r"^[A-Za-z0-9]{40}$"
        }
        
        if provider in key_formats:
            if not re.match(key_formats[provider], api_key):
                return jsonify({"error": f"Invalid {provider} API key format"}), 400
                
        # Encrypt the API key if not in local development mode
        is_production = os.environ.get('FLASK_ENV') == 'production'
        
        # Read the current config for local development
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
            
        # Ensure the keys section exists
        if "keys" not in config:
            config["keys"] = {}
            
        # Set environment variable immediately for current session
        provider_key_mapping = {
            "openai": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "semantic_scholar": "SEMANTIC_SCHOLAR_API_KEY"
        }
        
        # Save the key to environment variable for immediate use
        if provider in provider_key_mapping:
            os.environ[provider_key_mapping[provider]] = api_key
        
        # In production, encrypt keys for storage
        if is_production:
            # Use app secret key as encryption password
            encrypted_data = encrypt_api_key(api_key, app.config['SECRET_KEY'])
            
            # Store encrypted key by provider
            encrypted_key_path = os.path.join(SECURE_KEYS_DIR, f"{provider}.json")
            with open(encrypted_key_path, 'w') as f:
                json.dump(encrypted_data, f)
                
            return jsonify({
                "status": "success", 
                "message": f"API key for {provider} saved securely"
            })
        else:
            # For local development, save in config file
            if provider == "openai":
                config["keys"]["openai_key"] = api_key
            elif provider == "claude":
                config["keys"]["anthropic_key"] = api_key
            elif provider == "deepseek":
                config["keys"]["deepseek_key"] = api_key
            elif provider == "gemini":
                config["keys"]["googleaistudio_key"] = api_key
                
            # Save the updated config
            with open("config/config.yaml", "w") as f:
                yaml.dump(config, f, default_flow_style=False)
                
            return jsonify({
                "status": "success", 
                "message": f"API key for {provider} saved successfully"
            })
        
    except Exception as e:
        error_message = f"Error saving API key: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route("/api/delete_api_key", methods=["POST"])
def delete_api_key():
    """Delete an API key"""
    try:
        data = request.get_json()
        if not data or "provider" not in data:
            return jsonify({"error": "Missing provider field"}), 400
            
        provider = data["provider"]
        is_production = os.environ.get('FLASK_ENV') == 'production'
        
        if is_production:
            # For production, remove the encrypted key file
            encrypted_key_path = os.path.join(SECURE_KEYS_DIR, f"{provider}.json")
            if os.path.exists(encrypted_key_path):
                os.remove(encrypted_key_path)
                return jsonify({
                    "status": "success", 
                    "message": f"API key for {provider} deleted successfully"
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"No API key found for {provider}"
                }), 404
        else:
            # For local development, remove from config file
            with open("config/config.yaml", "r") as f:
                config = yaml.safe_load(f)
                
            # Check if keys section exists
            if "keys" not in config:
                return jsonify({"status": "error", "message": "No API keys found"}), 404
                
            # Remove appropriate key based on provider
            key_removed = False
            if provider == "openai" and "openai_key" in config["keys"]:
                del config["keys"]["openai_key"]
                key_removed = True
            elif provider == "claude" and "anthropic_key" in config["keys"]:
                del config["keys"]["anthropic_key"]
                key_removed = True
            elif provider == "deepseek" and "deepseek_key" in config["keys"]:
                del config["keys"]["deepseek_key"]
                key_removed = True
            elif provider == "gemini" and "googleaistudio_key" in config["keys"]:
                del config["keys"]["googleaistudio_key"]
                key_removed = True
                
            if key_removed:
                # Save the updated config
                with open("config/config.yaml", "w") as f:
                    yaml.dump(config, f, default_flow_style=False)
                return jsonify({
                    "status": "success", 
                    "message": f"API key for {provider} deleted successfully"
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"No API key found for {provider}"
                }), 404
            
    except Exception as e:
        error_message = f"Error deleting API key: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.route("/api/get_api_keys", methods=["GET"])
def get_api_keys():
    """Get a list of configured API keys (without exposing the actual key values)"""
    try:
        is_production = os.environ.get('FLASK_ENV') == 'production'
        configured_keys = []
        
        if is_production:
            # In production, check for encrypted key files
            for provider in ["openai", "claude", "deepseek", "gemini"]:
                encrypted_key_path = os.path.join(SECURE_KEYS_DIR, f"{provider}.json")
                if os.path.exists(encrypted_key_path):
                    configured_keys.append({
                        "provider": provider,
                        "configured": True
                    })
        else:
            # In local development, check the config file
            with open("config/config.yaml", "r") as f:
                config = yaml.safe_load(f)
                
            # Check if keys section exists
            if "keys" in config:
                # Create a list of configured providers (without exposing the actual keys)
                key_mapping = {
                    "openai_key": "openai",
                    "anthropic_key": "claude", 
                    "deepseek_key": "deepseek",
                    "googleaistudio_key": "gemini"
                }
                
                for key_name, provider_name in key_mapping.items():
                    if key_name in config["keys"] and config["keys"][key_name]:
                        configured_keys.append({
                            "provider": provider_name,
                            "configured": True
                        })
                
        return jsonify({"keys": configured_keys})
        
    except Exception as e:
        error_message = f"Error retrieving API keys: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

# Endpoint to provide client-side encryption code
@app.route("/api/encryption-script")
def get_encryption_script():
    """Return JavaScript code for client-side encryption"""
    return get_client_encryption_script(), 200, {'Content-Type': 'application/javascript'}

@app.route("/api/llm_client_info")
def get_llm_client_info():
    """Get information about which LLM client is being used"""
    try:
        from src.agents.llm_utils import get_client_info
        client_info = get_client_info()
        
        # Add environment variable info
        env_info = {
            "DEPLOY": os.environ.get('DEPLOY', 'false'),
            "AZURE_OPENAI_API_KEY_SET": bool(os.environ.get('AZURE_OPENAI_API_KEY')),
            "AZURE_OPENAI_ENDPOINT_SET": bool(os.environ.get('AZURE_OPENAI_ENDPOINT')),
            "AZURE_OPENAI_API_VERSION": os.environ.get('AZURE_OPENAI_API_VERSION', '2024-06-01')
        }
        
        return jsonify({
            "client_info": client_info,
            "environment": env_info
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to get client info: {str(e)}"}), 500

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/knowledge", methods=["GET"])
def get_knowledge():
    return jsonify(knowledge_chunks)


@app.route("/api/add_knowledge", methods=["POST"])
def add_knowledge():
    data = request.get_json()
    if not data or "text" not in data or "source" not in data:
        return jsonify({"error": "Invalid payload"}), 400
    new_id = len(knowledge_chunks) + 1
    chunk = {
        "id": new_id,
        "text": data["text"],
        "full_text": data["text"],
        "source": data["source"],
    }
    knowledge_chunks.append(chunk)
    return jsonify(chunk), 201


@app.route("/api/chat", methods=["GET", "POST"])
def chat():
    global main_idea, current_root, current_node, current_state, exploration_in_progress
    if request.method == "GET":
        return jsonify(chat_messages)
    else:
        data = request.get_json()
        if not data or "content" not in data:
            return jsonify({"error": "Invalid payload"}), 400
        
        user_message = data["content"]
        chat_messages.append({"role": "user", "content": user_message})
        
        try:
            # First message: Initialize MCTS with research goal
            if current_root is None:
                # Store initial research goal in state
                chat_messages.append(
                    {"role": "system", "content": "Generating initial idea..."}
                )

                # Extract the abstract from the knowledge chunks (if available)
                abstract_text = ""
                for chunk in knowledge_chunks:
                    if "abstract" in chunk:
                        abstract_text = chunk["abstract"]
                        break 
                
                # Create a root state that represents just the research goal
                root_state = MCTSState(
                    research_goal=user_message,
                    current_idea=user_message,  # Root node "idea" is the research goal itself
                    retrieved_knowledge=[abstract_text],  # Pass abstract as retrieved knowledge
                    feedback={},
                    reward=0.0,
                    depth=0,
                )
                
                # Create root node with the research goal
                current_root = MCTSNode(state=root_state)
                
                # Use the ideation agent to generate the idea
                response = mcts.ideation_agent.execute_action(
                    "generate", 
                    {
                        "research_goal": user_message,
                        "current_idea": None,
                        "action_type": "execute"
                    }
                )
                llm_response = response["content"]
                chat_messages.append({"role": "system", "content": "Initial idea generated by AI."})
                
                main_idea = llm_response
                
                # Create a state for the first generated idea
                first_idea_state = MCTSState(
                    research_goal=user_message,
                    current_idea=llm_response,
                    retrieved_knowledge=[],
                    feedback={},
                    reward=0.0,
                    depth=1,  # Depth 1 since it's a child of the root
                )
                
                # Get review using the unified review method
                review_data = review_agent.unified_review(llm_response)
                print(f"Review score: {review_data['average_score']}")
                if review_data:
                    if "scores" in review_data:
                        first_idea_state.review_scores = review_data["scores"]
                    if "reviews" in review_data:
                        first_idea_state.review_feedback = review_data["reviews"]
                    if "average_score" in review_data:
                        first_idea_state.average_score = review_data["average_score"]
                        first_idea_state.reward = review_data["average_score"]
                
                # Add the first generated idea as a child of the root node
                first_idea_node = current_root.add_child(first_idea_state, "generate")
                
                # Set current node to the first idea node
                current_node = first_idea_node
                
                chat_messages.append({"role": "assistant", "content": llm_response})
                
            # Subsequent messages: Treat as direct feedback to improve the current idea
            else:
                # Add system message indicating feedback processing
                chat_messages.append(
                    {"role": "system", "content": "Processing your feedback to improve the research idea..."}
                )
                
                # Process user feedback using the ideation agent
                improved_content, raw_output = ideation_agent.process_feedback(
                    idea=main_idea,
                    user_feedback=user_message,
                    original_raw_output=getattr(current_node.state, "raw_llm_output", None)
                )
                
                # Get the current feedback dictionary and add the new message
                current_feedback = current_node.state.feedback.copy() if hasattr(current_node.state, "feedback") else {}
                # Add the new feedback with a timestamp as key
                from datetime import datetime
                feedback_key = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_feedback[feedback_key] = user_message
                
                # Create a new state with updated idea based on feedback
                new_state = MCTSState(
                    research_goal=current_node.state.research_goal,
                    current_idea=improved_content,
                    retrieved_knowledge=current_node.state.retrieved_knowledge.copy(),
                    feedback=current_feedback,  # Pass feedback as dictionary
                    depth=current_node.state.depth + 1,
                    reward=0.0  # Initial reward will be updated with review score
                )
                
                # Get review using the unified review method
                review_data = review_agent.unified_review(improved_content)
                print(f"Review score: {review_data['average_score']}")
                if review_data:
                    if "scores" in review_data:
                        new_state.review_scores = review_data["scores"]
                    if "reviews" in review_data:
                        new_state.review_feedback = review_data["reviews"]
                    if "average_score" in review_data:
                        new_state.average_score = review_data["average_score"]
                        new_state.reward = review_data["average_score"]
                
                # Create new node and add as child of current node
                new_node = current_node.add_child(new_state, "direct_feedback")
                current_node = new_node
                
                # Update main idea
                main_idea = improved_content
                
                # Add system message acknowledging feedback incorporation
                chat_messages.append(
                    {"role": "system", "content": "Research idea updated based on your feedback."}
                )
                
                # Add the improved idea as an assistant message
                chat_messages.append({"role": "assistant", "content": improved_content})
                
            # Return the updated state
            return jsonify(
                {
                    "messages": chat_messages,
                    "idea": main_idea,
                    "initial_proposal": current_root.state.research_goal if current_root else user_message,
                    "review_scores": getattr(current_node.state, "review_scores", {}),
                    "average_score": getattr(current_node.state, "average_score", 0.0),
                }
            )
                
        except Exception as e:
            error_message = f"Error processing chat: {str(e)}"
            traceback.print_exc()  # Print the stack trace for debugging
            chat_messages.append({"role": "system", "content": error_message})
            return jsonify({"error": error_message}), 500


@app.route("/api/step", methods=["POST"])
def step():
    global main_idea, current_node, current_state
    if current_node is None:
        return jsonify({"error": "Please enter an initial research idea first"}), 400

    data = request.get_json()
    if not data or "action" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    action = data["action"]

    try:
        # Handle the automatic generation action using UCT algorithm
        if action == "generate":
            # Automatically select an action using UCT algorithm
            # First get valid actions
            valid_actions = ["review_and_refine", "retrieve_and_refine", "refresh_idea"]
            
            # Simple UCT action selection
            def uct_score(action):
                # Get the child node for this action if it exists
                child = None
                for c in current_node.children:
                    if c.action == action:
                        child = c
                        break
                
                # If no child exists for this action, it's unexplored (high potential)
                if not child:
                    return float('inf')
                
                # Calculate UCT score with exploration constant 1.414 (standard)
                exploitation = child.value  # Use existing value property 
                exploration = 1.414 * math.sqrt(math.log(current_node.visits) / max(child.visits, 1))
                
                # Add domain-specific heuristics
                bonus = 0
                # If low novelty score, prefer retrieve_and_refine
                if action == "retrieve_and_refine" and hasattr(current_node.state, "review_scores"):
                    if current_node.state.review_scores.get("novelty", 10) < 7:
                        bonus += 0.2
                
                # If iteration count is high, prefer refresh_idea occasionally
                if action == "refresh_idea" and current_node.depth > 3:
                    bonus += 0.15
                
                return exploitation + exploration + bonus
            
            # Select action with highest UCT score
            selected_action = max(valid_actions, key=uct_score)
            
            # Add system message about the selected action
            chat_messages.append({
                "role": "system", 
                "content": f"Auto-generating using '{selected_action.replace('_', ' ')}' strategy..."
            })
            
            # Recursively call this function with the selected action
            return step_action(selected_action)
            
        # Add handler for the judge action - needed by review_and_refine
        elif action == "judge":
            # Use the review agent to get a unified review of the current idea
            review_data = review_agent.unified_review(current_node.state.current_idea)
            
            # Add the review scores to the current node's state
            if review_data:
                if not hasattr(current_node.state, "review_scores") or not current_node.state.review_scores:
                    current_node.state.review_scores = {}
                if "scores" in review_data:
                    current_node.state.review_scores = review_data["scores"]
                if "reviews" in review_data:
                    current_node.state.review_feedback = review_data["reviews"]
                if "average_score" in review_data:
                    current_node.state.average_score = review_data["average_score"]
            
            # Add system message with review summary
            avg_score = review_data.get("average_score", 0)
            chat_messages.append({
                "role": "system", 
                "content": f"Review complete. Overall score: {avg_score:.1f}/10"
            })
            
            # Return the review data
            return jsonify({
                "idea": main_idea,
                "nodeId": current_node.id,
                "action": action,
                "depth": current_node.state.depth,
                "review_scores": review_data.get("scores", {}),
                "average_score": review_data.get("average_score", 0.0),
                "review_feedback": review_data.get("reviews", {})
            })
        
        # Handle regular actions with their existing implementation
        elif action == "review_and_refine":
            # First get unified review
            review_data = review_agent.unified_review(current_node.state.current_idea)
            
            # Sort aspects by score to find lowest scoring ones
            aspect_scores = []
            if "scores" in review_data:
                aspect_scores = sorted(
                    review_data["scores"].items(),
                    key=lambda x: x[1]
                )[:3]  # Get 3 lowest scoring aspects
            
            # Get detailed reviews for lowest aspects
            detailed_reviews = []
            for aspect, score in aspect_scores:
                review = structured_review_agent.review_aspect(
                    current_node.state.current_idea,
                    aspect
                )
                if review:
                    detailed_reviews.append(review)
            
            # Create improvement prompt with focused feedback
            improvement_state = MCTSState(
                research_goal=current_node.state.research_goal,
                current_idea=current_node.state.current_idea,
                retrieved_knowledge=current_node.state.retrieved_knowledge.copy(),
                feedback=detailed_reviews,
                depth=current_node.state.depth + 1
            )
            
            # Get improved idea from ideation agent
            response = mcts.ideation_agent.execute_action(
                "review_and_refine",
                {
                    "current_idea": current_node.state.current_idea,
                    "reviews": detailed_reviews,
                    "action_type": "execute"
                }
            )
            
            # Update state with improved idea
            improvement_state.current_idea = response["content"]
            
            # Get new review scores
            new_review = review_agent.unified_review(improvement_state.current_idea)
            if new_review:
                improvement_state.review_scores = new_review.get("scores", {})
                improvement_state.review_feedback = new_review.get("reviews", {})
                improvement_state.average_score = new_review.get("average_score", 0.0)
                improvement_state.reward = new_review.get("average_score", 0.0) / 10
            
            # Create new node and update current
            new_node = current_node.add_child(improvement_state, action)
            current_node = new_node
            main_idea = improvement_state.current_idea

        elif action == "retrieve_and_refine":
            # Generate query based on current idea
            query_state = {
                "current_idea": current_node.state.current_idea,
                "action_type": "generate_query"
            }
            query_response = mcts.ideation_agent.execute_action("generate_query", query_state)
            
            # Add system message about query generation
            chat_messages.append({
                "role": "system",
                "content": "Generating search query..."
            })
            
            # Get search query
            query = None
            try:
                if isinstance(query_response.get("content"), str):
                    import json
                    # Try to extract query from JSON in content
                    match = re.search(r'{.*}', query_response["content"])
                    if match:
                        query_json = json.loads(match.group())
                        query = query_json.get("query")
                    if not query:
                        # Fallback to using first sentence
                        query = query_response["content"].split(".")[0]

                    # Add message showing the generated query
                    chat_messages.append({
                        "role": "system", 
                        "content": f"Generated search query: {query}"
                    })

            except Exception as e:
                print(f"Error parsing query: {e}")
                query = current_node.state.current_idea[:100]  # Fallback to using truncated idea
                chat_messages.append({
                    "role": "system",
                    "content": f"Failed to parse query, using fallback: {query}"
                })
            
            # Retrieve relevant papers
            chat_messages.append({
                "role": "system",
                "content": "Searching for relevant papers..."
            })
            
            search_results = scholar_qa.answer_query(query)
            
            # Add message showing search results
            if search_results and "sections" in search_results:
                chat_messages.append({
                    "role": "system",
                    "content": f"Found {len(search_results['sections'])} relevant sections from papers"
                })

            # Create new state with retrieved knowledge
            retrieval_state = MCTSState(
                research_goal=current_node.state.research_goal,
                current_idea=current_node.state.current_idea,
                retrieved_knowledge=current_node.state.retrieved_knowledge + [search_results],
                feedback=current_node.state.feedback.copy(),
                depth=current_node.state.depth + 1
            )
            
            # Improve idea with retrieved knowledge
            improvement_response = mcts.ideation_agent.execute_action(
                "retrieve_and_refine",
                {
                    "current_idea": current_node.state.current_idea,
                    "retrieved_content": search_results,
                    "action_type": "execute"
                }
            )
            
            # Update state with improved idea
            retrieval_state.current_idea = improvement_response["content"]
            
            # Get new review scores
            new_review = review_agent.unified_review(retrieval_state.current_idea)
            if new_review:
                retrieval_state.review_scores = new_review.get("scores", {})
                retrieval_state.review_feedback = new_review.get("reviews", {})
                retrieval_state.average_score = new_review.get("average_score", 0.0)
                retrieval_state.reward = new_review.get("average_score", 0.0) / 10
            
            # Create new node and update current
            new_node = current_node.add_child(retrieval_state, action)
            current_node = new_node
            main_idea = retrieval_state.current_idea

        elif action == "refresh_idea":
            # Get the research goal from the root node
            research_goal = None
            if hasattr(current_root.state, "research_goal"):
                research_goal = current_root.state.research_goal

            # Get fresh perspective on the idea
            response = mcts.ideation_agent.execute_action(
                "refresh_idea",
                {
                    "research_goal": research_goal,
                    "current_idea": current_node.state.current_idea,
                    "action_type": "execute"
                }
            )
            
            # Create a new state with trajectory-level memory
            # Start with depth 1 since this is directly connected to the root
            refresh_state = MCTSState(
                research_goal=research_goal,
                current_idea=response["content"],
                retrieved_knowledge=[],  # Start with empty retrieved knowledge for new approach
                feedback={},  # Start with empty feedback for new approach
                depth=1  # Directly connected to root, so depth is 1
            )
            
            # Get new review scores
            new_review = review_agent.unified_review(refresh_state.current_idea)
            if new_review:
                refresh_state.review_scores = new_review.get("scores", {})
                refresh_state.review_feedback = new_review.get("reviews", {})
                refresh_state.average_score = new_review.get("average_score", 0.0)
                refresh_state.reward = new_review.get("average_score", 0.0) / 10
            
            # Create new node and add as child of the ROOT node instead of current node
            new_node = current_root.add_child(refresh_state, action)
            
            # Update current node to the newly created node
            current_node = new_node
            main_idea = refresh_state.current_idea

            # Add system message about the refresh
            chat_messages.append({
                "role": "system", 
                "content": "Created a new approach based on the original research goal."
            })

        else:
            return jsonify({"error": "Invalid action"}), 400

        # Return updated state
        return jsonify({
            "idea": main_idea,
            "nodeId": current_node.id,
            "action": action,
            "depth": current_node.state.depth,
            "review_scores": getattr(current_node.state, "review_scores", {}),
            "average_score": getattr(current_node.state, "average_score", 0.0),
            "retrieved_knowledge": bool(current_node.state.retrieved_knowledge),
            "has_feedback": bool(current_node.state.feedback)
        })

    except Exception as e:
        error_message = f"Error executing {action}: {str(e)}"
        traceback.print_exc()
        return jsonify({"error": error_message}), 500

# Helper function to avoid code duplication
def step_action(action):
    """Execute a step with a specific action and return the result"""
    # We simulate a new request with the selected action
    request_data = {"action": action}
    
    # Create a mock Request object
    class MockRequest:
        def get_json(self):
            return request_data
    
    # Store the original request
    original_request = request
    
    # Set the global request to our mock
    globals()["request"] = MockRequest()
    
    try:
        # Call the step function with our mock request
        result = step()
        return result
    finally:
        # Restore the original request
        globals()["request"] = original_request

@app.route("/api/tree", methods=["GET"])
def get_tree():
    if current_root is None:
        return jsonify({}), 200  # Return empty object instead of error

    def node_to_dict(node):
        # Get basic info about the node
        is_root = node.parent is None
        
        # For root node, use special formatting to show it's the research goal
        if is_root:
            node_data = {
                "id": node.id,
                "action": "research_goal",  # Special action type for root
                "idea": "RESEARCH GOAL: " + (node.state.research_goal[:80] + "..." if len(node.state.research_goal) > 80 else node.state.research_goal),
                "depth": node.state.depth,
                "reward": node.state.reward,
                "value": node.value,
                "visits": node.visits,
                "isCurrentNode": node.id == current_node.id if current_node else False,
                "state": {
                    "current_idea": node.state.research_goal,  # For root, use research_goal as current_idea
                    "depth": node.state.depth,
                    "reward": node.state.reward,
                    "hasReviews": False,  # Root node has no reviews
                    "hasRetrieval": False,  # Root node has no retrieval
                    "hasFeedback": False,  # Root node has no feedback
                    "isResearchGoal": True  # Flag to identify it's the research goal
                },
                "children": [node_to_dict(child) for child in node.children]
            }
        else:
            # Regular node formatting for ideas
            node_data = {
                "id": node.id,
                "action": node.action or "unknown",
                "idea": node.state.current_idea[:100] + "..." if len(node.state.current_idea) > 100 else node.state.current_idea,
                "depth": node.state.depth,
                "reward": node.state.reward,
                "value": node.value,
                "visits": node.visits,
                "isCurrentNode": node.id == current_node.id if current_node else False,
                "state": {
                    "current_idea": node.state.current_idea,
                    "depth": node.state.depth,
                    "reward": node.state.reward,
                    "hasReviews": hasattr(node.state, "review_scores") and bool(node.state.review_scores),
                    "hasRetrieval": bool(node.state.retrieved_knowledge),
                    "hasFeedback": bool(node.state.feedback),
                    "isResearchGoal": False  # Regular nodes are not research goals
                },
                "children": [node_to_dict(child) for child in node.children]
            }
            
            # Add review data if available
            if hasattr(node.state, "review_scores") and node.state.review_scores:
                node_data["reviews"] = {
                    "scores": node.state.review_scores,
                    "summary": getattr(node.state, "review_summary", {})
                }
        
        return node_data

    tree_data = node_to_dict(current_root)
    return jsonify(tree_data)


@app.route("/api/node", methods=["POST"])
def select_node():
    global current_node, main_idea, chat_messages
    data = request.get_json()
    if not data or "node_id" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    node_id = data["node_id"]
    
    def find_node(root, target_id):
        """Recursively find a node by ID in the tree."""
        if root.id == target_id:
            return root
        for child in root.children:
            result = find_node(child, target_id)
            if result:
                return result
        return None

    # Find the node in the tree
    node = find_node(current_root, node_id)
    
    if node:
        # Update current node and idea
        current_node = node
        main_idea = node.state.current_idea
        
        # Log this action in chat
        chat_messages.append({
            "role": "system", 
            "content": f"Navigated to node {node_id} with action '{node.action or 'root'}'."
        })
        
        # Prepare response data
        response = {
            "idea": main_idea,
            "node_data": {
                "id": node.id,
                "action": node.action or "root",
                "depth": node.state.depth,
                "reward": node.state.reward
            },
            "review_scores": getattr(node.state, "review_scores", {}),
            "average_score": getattr(node.state, "average_score", 0.0),
        }
        
        # Include review data if available
        if hasattr(node.state, "review_scores") and node.state.review_scores:
            response["reviews"] = {
                "scores": node.state.review_scores,
                "feedback": node.state.review_feedback,
                "summary": getattr(node.state, "review_summary", {})
            }
        
        # Include trajectory history
        if node.parent:
            trajectory = []
            current = node
            while current.parent:
                trajectory.append({
                    "id": current.id,
                    "action": current.action,
                    "depth": current.state.depth
                })
                current = current.parent
            response["trajectory"] = list(reversed(trajectory))
        
        return jsonify(response)
    else:
        return jsonify({"error": f"Node with ID {node_id} not found"}), 404


@app.route("/api/idea", methods=["GET"])
def get_idea():
    if current_node is None:
        return jsonify({"idea": main_idea})
    
    return jsonify({
        "idea": main_idea,
        "review_scores": getattr(current_node.state, "review_scores", {}),
        "average_score": getattr(current_node.state, "average_score", 0.0),
    })


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # Initialize abstract variable
    abstract = "Abstract could not be extracted"  # Default value in case no abstract is found

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

        try:
            file.save(file_path)
            file_content = "File content could not be extracted"
            
            # Extract text content from PDF using PyMuPDF if it's a PDF
            if file_path.lower().endswith('.pdf'):
                try:
                    pdf_text = []
                    with pymupdf.open(file_path) as doc:
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            pdf_text.append(page.get_text())
                    file_content = "\n".join(pdf_text)
                    # Extract the abstract from the PDF content
                    abstract = extract_abstract(pdf_text)
                except Exception as pdf_err:
                    print(f"Error extracting PDF content: {pdf_err}")
            
            # Add file info to knowledge chunks
            new_id = len(knowledge_chunks) + 1
            chunk = {
                "id": new_id,
                "text": f"Uploaded file: {filename}",
                "full_text": file_content,
                "abstract": abstract,  # Added abstract here
                "source": file_path,
                "file_type": "attachment",
            }
            knowledge_chunks.append(chunk)

            return (
                jsonify(
                    {
                        "message": "File uploaded successfully",
                        "filename": filename,
                        "abstract": abstract,
                        "chunk": chunk,
                    }
                ),
                201,
            )

        except Exception as e:
            return jsonify({"error": f"Error saving file: {str(e)}"}), 500

    return jsonify({"error": "File type not allowed"}), 400


@app.route("/api/review_aspect", methods=["POST"])
def review_aspect():
    data = request.get_json()
    if not data or "idea" not in data or "aspect" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    idea = data["idea"]
    aspect = data["aspect"]
    aspect_index = data.get("aspect_index", 0)

    try:
        print(f"\n=== REQUEST DATA ===")
        print(f"Aspect: {aspect}")
        print(f"Aspect Index: {aspect_index}")
        print(f"Idea length: {len(idea)} chars")
        
        review_data = structured_review_agent.review_aspect(idea, aspect)
        
        print(f"\n=== RESPONSE DATA ===")
        print(f"Review Data Keys: {review_data.keys()}")
        if 'highlight' in review_data:
            print(f"Highlight Data Keys: {review_data['highlight'].keys()}")
            print(f"Highlight Text: '{review_data['highlight'].get('text')}'")
            
            # Add debugging to check if highlight text exists in idea
            highlight_text = review_data['highlight'].get('text')
            if highlight_text:
                # Check for exact match
                exact_match = highlight_text in idea
                print(f"Exact match found in idea: {exact_match}")
                
                # Check for case-insensitive match
                case_insensitive_match = highlight_text.lower() in idea.lower()
                print(f"Case-insensitive match found in idea: {case_insensitive_match}")
                
                # Check if text might be affected by markdown formatting
                if not exact_match:
                    # Try to find position where highlight might be with markdown formatting
                    stripped_highlight = highlight_text.replace('*', '').replace('_', '')
                    stripped_match = stripped_highlight in idea
                    print(f"Match after removing markdown chars: {stripped_match}")
                    
                    # Additional check: Look for parts of the highlight text
                    if len(highlight_text) > 15:
                        partial_text = highlight_text[5:15]
                        partial_match = partial_text in idea
                        print(f"Partial match with '{partial_text}': {partial_match}")
        
        response = {"review_data": review_data, "aspect_index": aspect_index}
        print(f"\n=== SENDING RESPONSE ===")
        print(f"Response Keys: {response.keys()}")
        
        return jsonify(response)
    except Exception as e:
        error_message = f"Error reviewing {aspect}: {str(e)}"
        print(f"\n=== ERROR ===")
        print(error_message)
        return jsonify({"error": error_message}), 500


@app.route("/api/improve_idea", methods=["POST"])
def improve_idea():
    global main_idea, current_node
    data = request.get_json()
    if not data or "idea" not in data or "accepted_reviews" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    idea = data["idea"]
    accepted_reviews = data["accepted_reviews"]

    print("Accepted reviews:", accepted_reviews)
    # print("Idea:", idea)

    try:
        # Use ideation_agent instead of structured_review_agent
        improved_idea = ideation_agent.improve_idea(idea, accepted_reviews)

        # Update the main idea in our application state
        main_idea = improved_idea

        # Create a new state with trajectory-level memory
        new_state = MCTSState(
            research_goal=current_node.state.research_goal,
            current_idea=improved_idea,
            retrieved_knowledge=current_node.state.retrieved_knowledge.copy(),
            feedback=current_node.state.feedback.copy(),
            depth=current_node.state.depth + 1
        )
        
        # Get review using the unified review method
        review_data = review_agent.unified_review(improved_idea)
        print(f"Review score: {review_data['average_score']}")
        if review_data:
            if "scores" in review_data:
                new_state.review_scores = review_data["scores"]
            if "reviews" in review_data:
                new_state.review_feedback = review_data["reviews"]
            if "average_score" in review_data:
                new_state.average_score = review_data["average_score"]
                new_state.reward = review_data["average_score"]
        
        # Create new node and add as child of current node
        new_node = current_node.add_child(new_state, "review_and_refine")
        current_node = new_node

        # Add a system message about the improvement
        chat_messages.append(
            {
                "role": "system",
                "content": "Idea improved based on accepted review suggestions.",
            }
        )

        # Add the improved idea as an assistant message
        chat_messages.append({"role": "assistant", "content": improved_idea})

        return jsonify({
            "improved_idea": improved_idea,
            "review_scores": getattr(current_node.state, "review_scores", {}),
            "average_score": getattr(current_node.state, "average_score", 0.0),
        })
        
    except Exception as e:
        error_message = f"Error improving idea: {str(e)}"
        return jsonify({"error": error_message}), 500


@app.route("/api/generate_query", methods=["POST"])
def generate_query():
    """Generate a research query based on the current idea"""
    data = request.get_json()
    
    if not data or "idea" not in data:
        return jsonify({"error": "Missing idea in request"}), 400
    
    idea = data["idea"]
    
    try:
        # Log the attempt in chat
        global chat_messages
        chat_messages.append({
            "role": "system",
            "content": "Generating search query based on your research idea..."
        })
        
        # Use the ideation agent to generate a query
        prompt = "Given the following research idea, generate a concise and specific query for retrieving relevant scientific papers. The query should be focused on the key aspects of the research idea. Format your response as a JSON object with a single field named 'query'."
        
        # Call the ideation agent
        response = ideation_agent.execute_action(
            "generate_query",
            {"current_idea": idea, "prompt": prompt}
        )
        
        # Extract the query from the response
        content = response.get("content", "")
        
        # Try to parse JSON response
        try:
            # Look for JSON in the response
            json_match = re.search(r'```json\s*(.*?)\s*```|{.*}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1) or json_match.group(0)
                query_data = json.loads(json_str)
                query = query_data.get("query", "")
            else:
                # Try to extract query directly
                query_match = re.search(r'query["\']?\s*:\s*["\']([^"\']+)["\']', content)
                if query_match:
                    query = query_match.group(1)
                else:
                    # Fallback - use the first sentence as query
                    query = content.split(".")[0]
        except Exception as e:
            # If JSON parsing fails, use a simple text extraction approach
            lines = content.split("\n")
            for line in lines:
                if "query" in line.lower():
                    query = line.split(":", 1)[1].strip().strip('"\'')
                    break
            else:
                query = content.strip()
        
        # Add the generated query to chat
        chat_messages.append({
            "role": "assistant",
            "content": f"**Generated search query:** \"{query}\"\n\nI'll use this query to find relevant papers. You can click 'Retrieve Knowledge' to proceed with this query."
        })
        
        return jsonify({"query": query})
    
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Query generation error: {str(e)}\n{error_trace}")
        chat_messages.append({
            "role": "system",
            "content": f"Error generating query: {str(e)}"
        })
        return jsonify({"error": f"Failed to generate query: {str(e)}"}), 500

@app.route("/api/retrieve_knowledge", methods=["POST"])
def retrieve_knowledge():
    """Retrieve knowledge based on a query"""
    data = request.get_json()
    
    if not data or "query" not in data:
        return jsonify({"error": "Missing query in request"}), 400
    
    query = data["query"]
    
    try:
        # Log the attempt in chat
        global chat_messages
        chat_messages.append({
            "role": "system",
            "content": f"Searching for relevant papers using query: \"{query}\"..."
        })

        print(f"Retrieving knowledge for query: {query}")
        
        # Use ScholarQA to retrieve knowledge
        result = scholar_qa.answer_query(query)
        
        # Store the retrieval results globally
        global retrieval_results
        retrieval_results = result
        
        # Parse the sections and format for display
        formatted_sections = []
        
        for section in result.get("sections", []):
            formatted_section = {
                "title": section.get("title", "Untitled Section"),
                "summary": section.get("tldr", "No summary available"),
                "content": section.get("text", ""),
                "citations": []
            }
            
            # Extract citations
            for citation in section.get("citations", []):
                citation_id = citation.get("id", "")
                paper = citation.get("paper", {})
                
                formatted_citation = {
                    "id": citation_id,
                    "title": paper.get("title", "Unknown paper"),
                    "authors": [author.get("name", "") for author in paper.get("authors", [])],
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", ""),
                    "url": f"https://api.semanticscholar.org/CorpusID:{paper.get('corpus_id', '')}"
                }
                
                formatted_section["citations"].append(formatted_citation)
            
            formatted_sections.append(formatted_section)
        
        # Add success message to chat
        sections_count = len(formatted_sections)
        citations_count = sum(len(section["citations"]) for section in formatted_sections)
        
        chat_messages.append({
            "role": "assistant",
            "content": f"✅ **Retrieval complete!** Found {sections_count} content sections with {citations_count} paper citations.\n\nPlease check the left panel to see the retrieved information."
        })
        
        return jsonify({
            "query": query,
            "sections": formatted_sections
        })
    
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Retrieval error: {str(e)}\n{error_trace}")
        chat_messages.append({
            "role": "system",
            "content": f"Error retrieving knowledge: {str(e)}"
        })
        return jsonify({"error": f"Failed to retrieve knowledge: {str(e)}"}), 500

@app.route("/api/improve_idea_with_knowledge", methods=["POST"])
def improve_idea_with_knowledge():
    """Improve the research idea based on retrieved knowledge."""
    global main_idea, current_node, retrieval_results
    
    data = request.get_json()
    if not data or "idea" not in data:
        return jsonify({"error": "Missing idea in request"}), 400
    
    idea = data["idea"]
    
    # Check if we have any retrieval results to use
    if not retrieval_results or "sections" not in retrieval_results:
        return jsonify({"error": "No retrieved knowledge available"}), 400
    
    try:
        # Format the retrieved knowledge for the ideation agent
        retrieved_content = []
        for section in retrieval_results.get("sections", []):
            section_text = f"## {section.get('title', 'Untitled')}\n\n"
            section_text += f"{section.get('text', '')}\n\n"
            
            # Add citations if available
            if section.get("citations"):
                section_text += "### References:\n"
                for citation in section.get("citations", []):
                    paper = citation.get("paper", {})
                    authors = ", ".join([author.get("name", "") for author in paper.get("authors", [])[:3]])
                    if len(paper.get("authors", [])) > 3:
                        authors += " et al."
                    section_text += f"- {paper.get('title', 'Untitled')} ({authors}, {paper.get('year', 'n.d.')})\n"
            
            retrieved_content.append(section_text)
        
        # Join all sections into a single text
        formatted_knowledge = "\n\n".join(retrieved_content)
        
        # Add system message about the improvement process
        chat_messages.append({
            "role": "system",
            "content": "Improving research idea with retrieved knowledge..."
        })
        
        # Add instructions to ensure markdown format and making only relevant improvements
        prompt_instructions = {
            "current_idea": idea,
            "retrieved_content": formatted_knowledge,
        }
        
        # Call the ideation agent to improve the idea based on the retrieved knowledge
        response = ideation_agent.execute_action(
            "refine_with_retrieval",
            prompt_instructions
        )
        
        # Extract the improved idea, handling potential JSON format
        content = response.get("content", "")
        improved_idea = content
        
        # Try to extract content from JSON if present
        try:
            # Look for JSON in response
            import re
            import json
            
            # Check if the response contains JSON
            json_match = re.search(r'```json\s*(.*?)\s*```|{.*}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1) or json_match.group(0)
                # Clean up the extracted JSON string
                json_str = json_str.replace('\\n', ' ').strip()
                
                # Parse the JSON
                parsed_json = json.loads(json_str)
                if "content" in parsed_json:
                    improved_idea = parsed_json["content"]
                elif "text" in parsed_json:
                    improved_idea = parsed_json["text"]
                # If no content/text key but other text field exists, use that
                else:
                    for key in ["body", "description", "idea"]:
                        if key in parsed_json:
                            improved_idea = parsed_json[key]
                            break
        except Exception as json_error:
            print(f"JSON extraction error (continuing with raw content): {str(json_error)}")
            # If JSON parsing fails, keep the original content
            pass
        
        # Ensure improved_idea isn't empty
        if not improved_idea or improved_idea.strip() == "":
            improved_idea = content
        
        print(f"Improved idea length: {len(improved_idea)} characters")
        
        # Update the main idea in our application state
        main_idea = improved_idea
        
        # Create a new state with trajectory-level memory
        new_state = MCTSState(
            research_goal=current_node.state.research_goal,
            current_idea=improved_idea,
            retrieved_knowledge=current_node.state.retrieved_knowledge.copy() + [retrieval_results.get("query", "")],
            feedback=current_node.state.feedback.copy(),
            depth=current_node.state.depth + 1
        )
        
        # Get review using the unified review method
        review_data = review_agent.unified_review(improved_idea)
        print(f"Review score: {review_data['average_score']}")
        if review_data:
            if "scores" in review_data:
                new_state.review_scores = review_data["scores"]
            if "reviews" in review_data:
                new_state.review_feedback = review_data["reviews"]
            if "average_score" in review_data:
                new_state.average_score = review_data["average_score"]
                new_state.reward = review_data["average_score"]
        
        # Create new node and add as child of current node
        new_node = current_node.add_child(new_state, "retrieve_and_refine")
        current_node = new_node
        
        # Add a system message about the improvement
        chat_messages.append({
            "role": "system",
            "content": "Idea improved based on retrieved knowledge."
        })
        
        # Add the improved idea as an assistant message
        chat_messages.append({"role": "assistant", "content": improved_idea})
        
        return jsonify({
            "improved_idea": improved_idea,
            "content_length": len(improved_idea),
            "review_scores": getattr(new_state, "review_scores", {}),
            "average_score": getattr(new_state, "average_score", 0.0),
        })
        
    except Exception as e:
        error_message = f"Error improving idea with knowledge: {str(e)}"
        error_trace = traceback.format_exc()
        print(f"{error_message}\n{error_trace}")
        return jsonify({"error": error_message}), 500

@app.route("/api/refresh_idea", methods=["POST"])
def refresh_idea():
    """Dedicated endpoint for refreshing research ideas"""
    global main_idea, current_node, chat_messages, current_root
    
    # Check if current_node exists
    if current_node is None:
        return jsonify({"error": "No active research idea found. Please start by entering a research topic."}), 400
    
    try:
        # Add system message before refresh
        chat_messages.append(
            {"role": "system", "content": "Generating a completely new approach to the research goal..."}
        )
        
        # Get the research goal from the root node
        research_goal = None
        if hasattr(current_root.state, "research_goal"):
            research_goal = current_root.state.research_goal
        
        # Call the ideation agent to get a refreshed idea
        response = mcts.ideation_agent.execute_action(
            "refresh_idea", 
            {
                "research_goal": research_goal,
                "current_idea": main_idea, 
                "action_type": "execute"
            }
        )
        
        # Extract the idea content from the response
        new_idea = response.get("content", "")
        
        # Create a new state with trajectory-level memory
        # Start with depth 1 since this is directly connected to the root
        new_state = MCTSState(
            research_goal=research_goal,
            current_idea=new_idea,
            retrieved_knowledge=[],  # Start with empty retrieved knowledge for new approach
            feedback={},  # Start with empty feedback for new approach
            depth=1  # Directly connected to root, so depth is 1
        )
        
        # Get review using the unified review method
        review_data = review_agent.unified_review(new_idea)
        print(f"Review score: {review_data['average_score']}")
        if review_data:
            if "scores" in review_data:
                new_state.review_scores = review_data["scores"]
            if "reviews" in review_data:
                new_state.review_feedback = review_data["reviews"]
            if "average_score" in review_data:
                new_state.average_score = review_data["average_score"]
                new_state.reward = review_data["average_score"]
        
        # Create new node and add as child of the ROOT node instead of current node
        new_node = current_root.add_child(new_state, "refresh_idea")
        
        # Update current node to the newly created node
        current_node = new_node
        
        # Update main idea
        main_idea = new_idea

        # Add completion message to chat
        chat_messages.append({"role": "system", "content": "Created a new approach based on the original research goal."})

        return jsonify({
            "idea": new_idea,
            "messages": chat_messages,
            "review_scores": getattr(new_state, "review_scores", {}),
            "average_score": getattr(new_state, "average_score", 0.0),
        })
        
    except Exception as e:
        error_message = f"Error refreshing idea: {str(e)}"
        chat_messages.append({"role": "system", "content": error_message})
        return jsonify({"error": error_message, "messages": chat_messages}), 500

# WebSocket endpoints for real-time MCTS exploration
@socketio.on('start_exploration')
def handle_start_exploration():
    global exploration_in_progress, current_state
    
    if exploration_in_progress:
        return {'error': 'Exploration already in progress'}
    
    exploration_in_progress = True
    
    try:
        # Create initial state if none exists
        if not current_state:
            current_state = MCTSState()
        
        # Start MCTS exploration with callback for updates
        def exploration_callback(message):
            emit('exploration_update', {
                'type': 'progress',
                'message': message
            })
        
        # Run MCTS with callback
        root = mcts.run(current_state, num_iterations=5, callback=exploration_callback)
        
        # Store best path
        best_node = root
        while best_node.children:
            best_node = max(best_node.children, key=lambda n: n.value)
            
        # Update current state
        current_state = best_node.state
        
        # Send final results
        emit('exploration_complete', {
            'idea': current_state.current_idea,
            'score': current_state.average_score if hasattr(current_state, 'average_score') else None,
            'tree_data': root.to_dict()
        })
        
    except Exception as e:
        emit('exploration_error', {'error': str(e)})
    finally:
        exploration_in_progress = False

@socketio.on('stop_exploration')
def handle_stop_exploration():
    global exploration_in_progress
    exploration_in_progress = False
    emit('exploration_stopped')

@app.route("/api/set_aspect_weights", methods=["POST"])
def set_aspect_weights():
    """Update the weights for different review aspects."""
    try:
        data = request.get_json()
        if not data or "weights" not in data:
            return jsonify({"error": "Missing weights"}), 400
            
        weights = data["weights"]
        # Validate that we have all required aspects
        required_aspects = ["novelty", "clarity", "feasibility", "effectiveness", "impact"]
        if not all(aspect in weights for aspect in required_aspects):
            return jsonify({"error": "Missing required aspects"}), 400
            
        # Update weights in review agent
        review_agent.set_aspect_weights(weights)
        
        return jsonify({
            "success": True,
            "message": "Aspect weights updated successfully"
        })
        
    except Exception as e:
        error_message = f"Error setting aspect weights: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500

@app.cli.command("check-config")
def check_configuration():
    """Check the application configuration and environment."""
    issues = []
    warnings = []
    
    # Check Flask configuration
    if not os.environ.get('FLASK_SECRET_KEY'):
        if os.environ.get('FLASK_ENV') == 'production':
            issues.append("FLASK_SECRET_KEY must be set in production")
        else:
            warnings.append("FLASK_SECRET_KEY not set - using default (unsafe for production)")
            
    # Check required API keys
    required_keys = {
        'GEMINI_API_KEY': 'Google Gemini',
        'HUGGINGFACE_API_KEY': 'HuggingFace',
        'SEMANTIC_SCHOLAR_API_KEY': 'Semantic Scholar'
    }
    
    for env_var, provider in required_keys.items():
        if not os.environ.get(env_var):
            issues.append(f"Missing required {provider} API key ({env_var})")
            
    # Check optional API keys
    optional_keys = {
        'OPENAI_API_KEY': 'OpenAI',
        'ANTHROPIC_API_KEY': 'Anthropic/Claude',
        'DEEPSEEK_API_KEY': 'DeepSeek'
    }
    
    for env_var, provider in optional_keys.items():
        if not os.environ.get(env_var):
            warnings.append(f"Optional {provider} API key not configured ({env_var})")
            
    # Check secure directories
    if not os.path.exists(SECURE_KEYS_DIR):
        issues.append(f"Secure keys directory {SECURE_KEYS_DIR} does not exist")
    elif os.environ.get('FLASK_ENV') == 'production':
        # Check directory permissions in production
        import stat
        key_dir_stat = os.stat(SECURE_KEYS_DIR)
        if key_dir_stat.st_mode & stat.S_IROTH or key_dir_stat.st_mode & stat.S_IWOTH:
            issues.append(f"Secure keys directory {SECURE_KEYS_DIR} has unsafe permissions")
            
    # Check upload directory
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        issues.append(f"Upload directory {app.config['UPLOAD_FOLDER']} does not exist")
        
    # Print results
    if issues:
        click.secho("\n❌ Configuration issues found:", fg='red', bold=True)
        for issue in issues:
            click.secho(f"  - {issue}", fg='red')
            
    if warnings:
        click.secho("\n⚠️  Configuration warnings:", fg='yellow', bold=True)
        for warning in warnings:
            click.secho(f"  - {warning}", fg='yellow')
            
    if not issues and not warnings:
        click.secho("\n✅ Configuration valid!", fg='green', bold=True)
    elif not issues:
        click.secho("\n✅ No critical issues found (see warnings above)", fg='green')
        
    return len(issues) == 0

if __name__ == "__main__":
    socketio.run(app, debug=True)
