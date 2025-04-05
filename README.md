# IRIS: Interactive Research Ideation System

IRIS is an AI research and experimentation framework that integrates with various LLM APIs to conduct structured experiments using Monte Carlo Tree Search (MCTS) techniques.

## 🚀 Features

- Monte Carlo Tree Search for AI agent experimentation
- Integration with multiple LLM providers (Google AI Studio, Hugging Face, Groq)
- Structured retrieval and analysis pipelines
- Experiment tracking and result visualization
- Web interface for review and analysis

## 📋 Requirements

- Python 3.8+
- Required packages listed in `requirements.txt`
- API keys for supported LLM providers

## 🛠️ Installation

1. Clone this repository
   ```bash
   git clone https://github.com/yourusername/IRIS.git
   cd IRIS
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables (see Environment Setup section below)

4. Run setup script
   ```bash
   python setup_project.py
   ```

## 🔧 Environment Setup

Copy the `.env.example` file to create a `.env` file and add your API keys:

```bash
cp .env.example .env
```

Then edit the `.env` file with your actual API keys:

```
GOOGLEAI_API_KEY=your_google_ai_key
HF_API_KEY=your_huggingface_key
GROQ_API_KEY=your_groq_key
```

## 🎮 Usage

Run the main application:

```bash
python app.py
```

For experiments:

```bash
cd experiments
python run_experiments.py
```

## 📝 Configuration

Configuration files are stored in the `config/` directory:
- `config.yaml`: General settings and API configurations
- `model_config.yaml`: Model-specific parameters
- `prompts.yaml`: Prompt templates for agents

## 📧 Cite