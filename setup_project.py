#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

def create_directory_structure():
    """Create the project directory structure."""
    # Define the directory structure
    directories = [
        "config",
        "data/retrieved",
        "logs",
        "results",
        "src/agents",
        "src/mcts",
        "src/models",
        "src/prompts",
        "src/utils",
        "tests/test_agents",
        "experiments",
    ]
    
    # Create directories
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        # Create __init__.py files in Python package directories
        if directory.startswith(('src/', 'tests/')):
            init_file = Path(directory) / "__init__.py"
            init_file.touch(exist_ok=True)

def create_gitignore():
    """Create .gitignore file."""
    gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
logs/
results/
data/retrieved/*
.env

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
"""
    with open(".gitignore", "w") as f:
        f.write(gitignore_content.strip())

def create_env_template():
    """Create .env template file with all required environment variables."""
    env_content = """# Flask configuration
FLASK_ENV=development  # Set to 'production' in production environment
FLASK_SECRET_KEY=  # Required: Set a secure random key for Flask session encryption

# API Keys for LLM providers
OPENAI_API_KEY=  # Optional: OpenAI API key format: sk-...
ANTHROPIC_API_KEY=  # Optional: Anthropic (Claude) API key format: sk-ant-...
DEEPSEEK_API_KEY=  # Optional: DeepSeek API key 
GEMINI_API_KEY=  # Required: Google Gemini API key format: AIza...
HUGGINGFACE_API_KEY=  # Required: HuggingFace API key for model access

# Search and Retrieval API Keys
SEMANTIC_SCHOLAR_API_KEY=  # Required: Semantic Scholar API key (40 characters)
S2_API_KEY=  # Required: Alias for Semantic Scholar API key

# Model Selection and Configuration
DEFAULT_LLM_MODEL=gemini/gemini-2.0-flash-lite  # Default LLM model to use
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2  # Model for reranking search results

# Project Configuration
PYTHONPATH=${PYTHONPATH}:${PWD}

# Application Settings
MAX_RETRIEVAL_RESULTS=10  # Maximum number of papers to retrieve per search
CONTEXT_THRESHOLD=0.1  # Minimum relevance score for including papers
RERANK_TOP_K=5  # Number of top papers to keep after reranking"""

    # Create both .env and .env.example files
    with open(".env.example", "w") as f:
        f.write(env_content.strip())
        
    # Create .env with same template but empty values
    env_empty = env_content.replace("development", "").replace("gemini/gemini-2.0-flash-lite", "").replace("cross-encoder/ms-marco-MiniLM-L-6-v2", "")
    with open(".env", "w") as f:
        f.write(env_empty.strip())

def setup_virtual_environment():
    """Set up a Python virtual environment."""
    if not Path("venv").exists():
        subprocess.run([sys.executable, "-m", "venv", "venv"])
        print("Virtual environment created.")
    
    # Determine the proper activate script based on OS
    if sys.platform == "win32":
        activate_script = "venv\\Scripts\\activate"
        python_path_cmd = "set"
    else:
        activate_script = "source venv/bin/activate"
        python_path_cmd = "export"
    
    print(f"\nTo activate the virtual environment and set up environment variables:")
    print(f"1. {activate_script}")
    print(f"2. {python_path_cmd} PYTHONPATH=$PYTHONPATH:$(pwd)")
    print("\nThen copy .env.example to .env and fill in your API keys")
    print("See .env.example for descriptions of required keys")

def create_vscode_settings():
    """Create VSCode settings and recommended extensions."""
    vscode_dir = Path(".vscode")
    vscode_dir.mkdir(exist_ok=True)
    
    # settings.json
    settings = {
        "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
        "python.linting.enabled": True,
        "python.linting.pylintEnabled": True,
        "python.formatting.provider": "black",
        "editor.formatOnSave": True,
        "editor.rulers": [88],  # Black's default line length
        "files.exclude": {
            "**/__pycache__": True,
            "**/.pytest_cache": True,
            "**/*.pyc": True
        }
    }
    
    with open(vscode_dir / "settings.json", "w") as f:
        import json
        json.dump(settings, f, indent=4)
    
    # extensions.json
    extensions = {
        "recommendations": [
            "ms-python.python",
            "ms-python.vscode-pylance",
            "ms-python.black-formatter",
            "ms-python.pylint",
            "eamodio.gitlens",
            "yzhang.markdown-all-in-one"
        ]
    }
    
    with open(vscode_dir / "extensions.json", "w") as f:
        json.dump(extensions, f, indent=4)

def main():
    """Main setup function."""
    print("Setting up Research Ideation Assistant project...")
    
    # Create directory structure
    create_directory_structure()
    print("✓ Created directory structure")
    
    # Create .gitignore
    create_gitignore()
    print("✓ Created .gitignore")
    
    # Create .env template
    create_env_template()
    print("✓ Created .env.template")
    
    # Set up virtual environment
    setup_virtual_environment()
    print("✓ Set up virtual environment")
    
    # Create VSCode settings
    create_vscode_settings()
    print("✓ Created VSCode settings")
    
    print("\nSetup complete! Next steps:")
    print("1. Create and activate your virtual environment:")
    print("   python -m venv venv")
    if sys.platform == "win32":
        print("   .\\venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print("2. Install requirements:")
    print("   pip install -r requirements.txt")
    print("3. Copy .env.example to .env and fill in your API keys")
    print("4. Open VSCode with 'code .' and install recommended extensions")

if __name__ == "__main__":
    main()