# IRIS - Interactive Research Ideation System

## Setup

This project uses [uv]for package management.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Anikethh/IRIS-Interactive-Research-Ideation-System.git
    cd IRIS-Interactive-Research-Ideation-System
    ```

2.  **Activate virtual environment:**
    ```bash
    # Sync environment
    uv sync

    # Activate
    source .venv/bin/activate 
    ```

3.  **Set Environment Variables:**
    Setup your API keys:
    ```bash
    export S2_API_KEY="your_semantic_scholar_api_key" 
    export GEMINI_API_KEY="your_google_gemini_api_key" 
    ```

## Running the Application

Ensure your virtual environment is activated, then run:

```bash
python app.py
```

## 🚀 Features

- Monte Carlo Tree Search for AI agent experimentation
- Integration with multiple LLM providers (Google AI Studio, Hugging Face etc.)
- Structured retrieval and analysis pipelines
- Experiment tracking and result visualization

## 📋 Requirements

- Semantic Scholar API Key
- Key for any LLM API service provided by LiteLLM

## 📧 Cite