# Search Agent Framework

**Agent-to-Agent layered multi-agent system for parallel task execution.**

## Architecture Overview

This is a two-layer system that breaks down complex queries into parallel subtasks executed by dedicated agents:

- **Layer 1 (Orchestrator)**: Top-level LangChain orchestrator that calls `search_worker_pool` via MCP.
- **Layer 2 (SearchAgent)**: Executes concrete search tasks.

## Key Features

- 🚀 **High concurrency**: Up to 50 parallel search workers
- 🏗️ **Two-layer architecture**: Orchestrator → SearchWorkerPool → SearchAgent
- 🔧 **MCP integration**: Process isolation via Model Context Protocol
- 🎯 **Specialized execution**: Search-only
- 🛡️ **Resilience**: Graceful fallback and retry logic

## Quick Start

```python
from search_agent.runtime import create_orchestrator
from search_agent.configuration import SearchAgentConfig
from search_agent.shared import RunPaths
from pathlib import Path

# Create config
config = SearchAgentConfig()

# Create run paths
paths = RunPaths(
    internal_root_dir=Path("./cache"),
    external_root_dir=Path("./cache"),
    run_suffix="test",
    internal_run_dir=Path("./cache/test"),
    external_run_dir=Path("./cache/test"),
)

# Create Orchestrator (connects to search_worker_pool)
orchestrator = await create_orchestrator(config=config, paths=paths)

# Run a query
result = await orchestrator.run("Compare the top 5 AI frameworks in a table")

# Or stream updates
async for chunk in orchestrator.stream("A complex multi-step query..."):
    print(chunk)

# Cleanup
await orchestrator.close()
```

## Project Structure

```
search_agent_framework/
├── README.md                    # This file (EN)
├── README.zh.md                 # Chinese README
├── ARCHITECTURE.md              # Detailed architecture
├── requirements.txt             # Python dependencies
├── pool_config.yaml             # Worker pool config
└── src/
    └── search_agent/
        ├── orchestration/       # Orchestration
        │   └── orchestrator.py  # Orchestrator (connects to search_worker_pool)
        ├── coordination/        # Helper utilities
        │   └── _worker_wrapper.py
        ├── execution/           # Execution layer
        │   └── search_executor.py
        ├── infrastructure/      # Infrastructure
        │   └── firecrawl-mcp-server/  # Firecrawl MCP Server
        ├── configuration/       # Configuration
        ├── runtime/             # Runtime services
        └── shared/              # Shared code
```

See `ARCHITECTURE.md` for full details.

## Tech Stack

- **Orchestration**: LangChain (Orchestrator)
- **Execution**: LangChain (SearchAgent)
- **Transport**: MCP (Model Context Protocol)
- **Parallelism**: asyncio.gather (managed inside search_worker_pool)
- **External service**: Firecrawl (search)

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Build Firecrawl MCP server

The Firecrawl MCP server is located at `src/search_agent/infrastructure/firecrawl-mcp-server/`.

**Manual install**

```bash
cd src/search_agent/infrastructure/firecrawl-mcp-server
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Troubleshooting**: If you see `Cannot find module '../lib/tsc.js'`, delete `node_modules` and `package-lock.json` and reinstall.

## Configuration

### Worker pool size

Edit `pool_config.yaml` to adjust pool size:

```yaml
pools:
  search:
    max_pool_size: 50
```

### Environment variables

```bash
export OPENAI_API_KEY="your-api-key"
export FIRECRAWL_API_KEY="your-firecrawl-key"
```

### Firecrawl API Key

Get one at https://www.firecrawl.dev/app/api-keys

## Examples

See notebooks under `examples/`:

- `examples/agents/search_agent_test.ipynb` - SearchAgent usage
- `examples/managers/search_manager_test.ipynb` - Orchestrator end-to-end test

## Architecture

See `ARCHITECTURE.md` for:

- Full directory structure
- Core components
- Data flow
- Naming conventions
- Usage examples
