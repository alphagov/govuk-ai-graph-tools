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

**Production mode (Uvicorn ASGI server):**

```bash
uv run uvicorn 'app:create_asgi_app' --factory --port 3000
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


---

## Development and Code Quality

### 1. Manual Checks
You can run the full suite of checks using the `Makefile`:

```bash
# Run all checks
make lint && make format && make typecheck

# Run individual checks
make lint
make format
make typecheck
```

### 2. Pre-commit Hooks
The project is configured with `pre-commit` to automatically run these checks before every `git commit`. 

To install the hooks in your local repository:
```bash
make install-hooks
```

Once installed, your code will be automatically linted and type-checked whenever you commit. If you need to skip the hooks (e.g., for an urgent WIP commit), you can use `git commit --no-verify`.

---

## Tests

```bash
uv run pytest
```

---

## Licence

[MIT LICENCE](LICENCE)





