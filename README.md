# IRIS - Interactive Research Ideation System

Official repository for the paper [IRIS](https://arxiv.org/abs/2504.16728)

![IRIS Diagram](assets/Diagram.png)

## 🔗 Setup

This project uses ```uv``` for package management, but you can use any virtual environment.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Anikethh/IRIS-Interactive-Research-Ideation-System.git
    cd IRIS-Interactive-Research-Ideation-System
    ```

2.  **Activate virtual environment:**
    ```bash
    uv sync
    source .venv/bin/activate 
    ```

3.  **Set Environment Variables:**
    Setup your API keys:
    ```bash
    export S2_API_KEY="your_semantic_scholar_api_key" 
    export GEMINI_API_KEY="your_google_gemini_api_key" 
    ```

## 🖥️ Running the Application

Ensure your virtual environment is activated, then run:

```bash
python app.py
```

![IRIS Interface](assets/Interface.png)

## 📋 Requirements

- Semantic Scholar API Key
-  LLM API Key for any provider supported by LiteLLM

## 📧 Cite
```
@misc{garikaparthi2025irisinteractiveresearchideation,
      title={IRIS: Interactive Research Ideation System for Accelerating Scientific Discovery}, 
      author={Aniketh Garikaparthi and Manasi Patwardhan and Lovekesh Vig and Arman Cohan},
      year={2025},
      eprint={2504.16728},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2504.16728}, 
}
```
