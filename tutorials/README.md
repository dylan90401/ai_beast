# AI Beast Tutorials

Interactive Jupyter notebooks to help you learn AI Beast.

## Getting Started

### Prerequisites

1. Install Jupyter:
   ```bash
   pip install jupyterlab notebook
   ```

2. Start Jupyter:
   ```bash
   jupyter lab
   # Or
   jupyter notebook
   ```

3. Open any `.ipynb` file from this directory.

## Tutorial Index

### Beginner

| Tutorial | Description | Time |
|----------|-------------|------|
| [01_getting_started.ipynb](01_getting_started.ipynb) | First steps with AI Beast | 15 min |
| [02_chat_with_models.ipynb](02_chat_with_models.ipynb) | Interactive chat with LLMs | 20 min |

### Intermediate

| Tutorial | Description | Time |
|----------|-------------|------|
| [03_rag_basics.ipynb](03_rag_basics.ipynb) | Build your first RAG pipeline | 30 min |
| [04_custom_agents.ipynb](04_custom_agents.ipynb) | Create custom AI agents | 45 min |

### Advanced

| Tutorial | Description | Time |
|----------|-------------|------|
| [05_advanced_rag.ipynb](05_advanced_rag.ipynb) | Advanced RAG techniques | 60 min |
| [06_monitoring.ipynb](06_monitoring.ipynb) | Set up monitoring and metrics | 30 min |

## Running in AI Beast Environment

If you're using the AI Beast Jupyter extension:

```bash
beast extension enable jupyter
make up-jupyter
```

Then open http://localhost:8888 in your browser.

## Tips

- Run cells in order (Shift+Enter)
- Restart kernel if you make changes to AI Beast code
- Check that services are running: `!beast status`
