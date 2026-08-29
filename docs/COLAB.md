# Google Colab

Google Colab is a convenient zero-infrastructure environment for exploring the deterministic engines, running tests and calling the API from a notebook. It is not the recommended production deployment target.

## 1. Clone and install

Run these cells in a fresh Colab notebook:

```python
!git clone https://github.com/rodrigorissettoterra/ultimate-stock-analyzer.git
%cd ultimate-stock-analyzer
!python -m pip install --upgrade pip
!pip install -e ".[dev]"
```

Validate the repository:

```python
!ruff check src tests
!pytest -q
```

Run the synthetic deterministic example:

```python
!python examples/demo_ranking.py
```

## 2. Start the API inside Colab

The API can run as a subprocess and be queried from notebook cells:

```python
import subprocess
import time

server = subprocess.Popen([
    "uvicorn",
    "ultimate_stock_analyzer.api.main:app",
    "--host", "127.0.0.1",
    "--port", "8000",
])
time.sleep(2)
```

Check it from Python:

```python
import httpx

httpx.get("http://127.0.0.1:8000/health").json()
```

Inspect API metadata:

```python
httpx.get("http://127.0.0.1:8000/v1/meta").json()
```

When finished:

```python
server.terminate()
server.wait(timeout=10)
```

The notebook can access the local API directly. Opening the browser dashboard from outside the Colab runtime requires an external tunneling/port-exposure mechanism, which is intentionally not part of this repository.

## 3. Optional LLM synthesis without exposing the key

Set the key interactively before starting the API process:

```python
import getpass
import os

os.environ["USA_LLM_API_KEY"] = getpass.getpass("LLM API key: ")
os.environ["USA_LLM_MODEL"] = "<your-model-name>"
os.environ["USA_LLM_BASE_URL"] = "https://api.openai.com/v1"
```

Do not paste keys into notebook source cells that you intend to save or publish.

If the key/model variables are absent, the agent automatically uses deterministic synthesis.

## 4. Query the conversational agent

After starting the API:

```python
response = httpx.post(
    "http://127.0.0.1:8000/v1/agent/query",
    json={"question": "Explain the strongest evidence in the available ranking."},
    timeout=60,
)
response.json()
```

With the default in-memory repository, a new API process has no persisted live stock-analysis snapshots. That is expected. The endpoint does not fabricate data merely to answer a question.

## 5. What Colab is useful for

Good uses:

- running unit tests and examples;
- experimenting with collectors and normalized datasets;
- inspecting deterministic financial calculations;
- executing point-in-time backtests on a prepared dataset;
- testing LLM synthesis without provisioning a server;
- teaching or demonstrating the architecture.

Not recommended:

- long-running unattended collectors;
- persistent PostgreSQL production storage;
- scheduled production jobs;
- exposing API keys in shared notebooks;
- treating a transient runtime as the production service.

For the persistent local stack, use [`QUICKSTART.md`](QUICKSTART.md). For operational deployment boundaries, see [`M20_PRODUCTION.md`](M20_PRODUCTION.md).
