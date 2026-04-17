# GOV.UK AI Graph Tools

TODO: Fill in project description

## Local Setup

---

### Prerequisites

- **Python 3.13** - managed via `uv`
- **uv** — Python package manager

Install `uv` if not already installed:

```bash
brew install uv
# or
pip install uv
```

---

### 1. Install dependencies

```bash
uv init --python 3.13
uv python pin 3.13
uv add -r requirements.txt
```

### 2. Run the app

**Debug mode (Flask dev server):**

```bash
uv run app.py
```

**Production mode (Waitress WSGI server):**

```bash
uv run waitress-serve --port 3000 --call 'app:create_app'
```

The app runs on **http://localhost:3000**.

---


### 3. Docker run

Build and run using Docker:

```bash
docker build -t govuk-ai-graph-tools-app .

docker run -p 3000:3000 -t govuk-ai-graph-tools-app
```

---


## Tests

```bash
uv run pytest
```

---

## Licence

[MIT LICENCE](LICENCE)





