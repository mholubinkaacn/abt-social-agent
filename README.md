# abt-social-agent

Withnail — an AI agent that finds and books a venue for the ABT team social.
Powered by [LangGraph](https://github.com/langchain-ai/langgraph) and Google Gemini 2.5 Flash,
with venue discovery via the Google Places API.

---

## Prerequisites

- Python 3.11+ — [python.org/downloads](https://www.python.org/downloads/)
- Poetry 2.x (see below if not installed)
- Git — [git-scm.com](https://git-scm.com/)

---

## Setup

### 1. Install Poetry

#### macOS / Linux

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

The installer will print a line to add Poetry to your PATH — run it, then open a new terminal. Verify:

```bash
poetry --version  # should print Poetry 2.x.x
```

#### Windows (PowerShell)

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

The installer will print the PATH entry to add. Add it via **System Properties > Environment Variables**, then open a new terminal. Verify:

```powershell
poetry --version
```

For alternative installation methods (pipx, Homebrew, Scoop) see the [Poetry docs](https://python-poetry.org/docs/#installation).

### 2. Clone and install dependencies

```bash
git clone <repo-url>
cd abt-social-agent
poetry install --with dev
```

Poetry creates an isolated virtual environment and installs all runtime and dev dependencies automatically.

### 3. Install pre-commit hooks

```bash
poetry run pre-commit install
```

Hooks run automatically on `git commit`. To run them manually against all files:

```bash
poetry run pre-commit run --all-files
```

The following hooks are configured:

| Hook | Purpose |
|---|---|
| `poetry-check` / `poetry-lock` | Keeps `pyproject.toml` and `poetry.lock` consistent |
| `poetry-export` | Regenerates `requirements.txt` from the lock file |
| `mypy` | Static type checking |
| `isort` | Import ordering (Black-compatible profile) |
| `black` | Code formatting |
| `ruff` | Linting (E501 line length) |

### 4. Configure environment variables

Create a `.env` file in the project root with the following contents:

```
GEMINI_API_KEY=<your-gemini-api-key>
GOOGLE_PLACES_API_KEY=<your-google-places-api-key>
```

#### Getting a Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create an API key
3. The agent uses the `gemini-2.5-flash` model via the OpenAI-compatible endpoint

#### Getting a Google Places API key

1. Open the [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Places API (New)** — the agent uses the v1 Places API (`places.googleapis.com/v1`)
4. Create an API key under **APIs & Services > Credentials**
5. Restrict the key to the Places API (New) for security

---

## Running the agent

### Interactive mode

Starts a conversation with Withnail. He will introduce himself, then guide you through finding and booking a venue.

```bash
poetry run python cli.py
```

To use a different Gemini model:

```bash
poetry run python cli.py --model gemini-2.0-flash
```

Type `quit` or `exit` to end the session.

### Single query mode

Sends one query and prints the response:

```bash
poetry run python cli.py "Find a rooftop bar in Shoreditch for 10 people tonight"
```

---

## Running tests

```bash
poetry run pytest
```
