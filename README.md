# Pyrove

**Pyrove** is an asynchronous command-line application designed to synthesize topic-driven datasets for LoRA (Low-Rank Adaptation) fine-tuning of Large Language Models.

## Features
- **Multi-Source Scraping:** Pulls information from GitHub repositories, general web articles, and arXiv papers.
- **Token-Aware Chunking:** Slices extracted content into manageable 512-token chunks.
- **Local AI Transformation:** Leverages a local Ollama instance to transform chunks into high-quality instruction-response pairs.
- **Validation & Storage:** Validates pairs based on quality score and stores state in a local SQLite database for resumability.
- **Format Exporters:** Exports datasets to popular fine-tuning formats like Alpaca and ShareGPT.

## Prerequisites
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) (recommended project manager)
- [Ollama](https://ollama.com/) (installed and running locally)
  - You must pull the default model: `ollama pull llama3`

## Installation
Clone the repository and install dependencies using `uv`:

```bash
git clone <repository_url> pyrove
cd pyrove
uv sync
```

## Configuration
Pyrove supports configuration via environment variables. You can set these in your shell or an `.env` file:
- `OLLAMA_API_URL`: URL to the Ollama instance (default: `http://localhost:11434`)
- `OLLAMA_TIMEOUT`: Timeout for Ollama generation requests in seconds (default: `120.0`)
- `GITHUB_TOKEN`: Your GitHub Personal Access Token to avoid rate limiting when scraping GitHub.

## Usage
Run the CLI using `uv run`:

```bash
uv run rove <command> [options]
```

Or if installed globally:
```bash
pyrove <command> [options]
```

## Running Tests
Tests are written using `pytest`. You can run them via:

```bash
uv run pytest
```
