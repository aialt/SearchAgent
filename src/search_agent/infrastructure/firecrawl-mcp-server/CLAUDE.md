# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server implementation that integrates with [Firecrawl](https://github.com/firecrawl/firecrawl) for web scraping capabilities. The server provides MCP tools for scraping, crawling, mapping, searching, and extracting structured data from websites.

The server supports both cloud API (via Firecrawl API keys) and self-hosted Firecrawl instances. It includes automatic retries, rate limiting, credit usage monitoring, and comprehensive logging.

## Commands

### Build
```bash
npm run build
```
Compiles TypeScript to JavaScript in `dist/` and sets executable permissions on the binary.

### Test
```bash
npm test
```
Runs Jest tests using ES modules configuration.

### Development
```bash
# Start server (stdio mode)
npm start

# Start server (cloud service mode)
npm run start:cloud
```

### Linting and Formatting
```bash
npm run lint
npm run lint:fix
npm run format
```

### Running via npx
```bash
env FIRECRAWL_API_KEY=fc-YOUR_API_KEY npx -y firecrawl-mcp
```

## Architecture

### Entry Point
- `src/index.ts` - Main server implementation

### Core Components

**FastMCP Server Setup (lines 87-120)**
- Uses `firecrawl-fastmcp` library for MCP protocol implementation
- Session-based authentication with API key extraction from headers
- Health endpoint at `/health` for load balancer checks
- Supports both stdio and HTTP streaming transports

**Authentication Flow**
- Cloud service mode: Requires API key from HTTP headers (`authorization` or `x-firecrawl-api-key`)
- Self-hosted mode: Uses `FIRECRAWL_API_KEY` environment variable or allows unauthenticated access if `FIRECRAWL_API_URL` is provided

**Transport Modes (lines 625-643)**
- Default: stdio (for desktop integration)
- HTTP streaming: enabled via `CLOUD_SERVICE`, `SSE_LOCAL`, or `HTTP_STREAMABLE_SERVER` environment variables
- HTTP server runs on `PORT` (default 3000) and `HOST` (default localhost, 0.0.0.0 for cloud)

**Safe Mode**
- Enabled automatically in cloud service mode for ChatGPT safety requirements
- Disables interactive actions (click, write, executeJavascript) in scrape/crawl tools
- Limits action types to safe operations: wait, screenshot, scroll, scrape

### Available Tools

All tools are registered via `server.addTool()` and follow the pattern:
1. Zod schema for parameter validation
2. Description with usage examples
3. Execute function that calls Firecrawl client

**Tool List:**
1. `firecrawl_scrape` - Single page content extraction
2. `firecrawl_batch_scrape` - Multiple URLs scraping (removed from current version based on source)
3. `firecrawl_map` - Discover URLs on a website
4. `firecrawl_search` - Web search with optional scraping
5. `firecrawl_crawl` - Crawl entire websites
6. `firecrawl_check_crawl_status` - Check crawl job status
7. `firecrawl_extract` - LLM-powered structured data extraction

### Configuration

**Environment Variables:**
- `FIRECRAWL_API_KEY` - Required for cloud API, optional for self-hosted
- `FIRECRAWL_API_URL` - Custom API endpoint for self-hosted instances
- `FIRECRAWL_RETRY_MAX_ATTEMPTS` - Max retry attempts (default: 3)
- `FIRECRAWL_RETRY_INITIAL_DELAY` - Initial retry delay in ms (default: 1000)
- `FIRECRAWL_RETRY_MAX_DELAY` - Max retry delay in ms (default: 10000)
- `FIRECRAWL_RETRY_BACKOFF_FACTOR` - Exponential backoff multiplier (default: 2)
- `FIRECRAWL_CREDIT_WARNING_THRESHOLD` - Credit warning threshold (default: 1000)
- `FIRECRAWL_CREDIT_CRITICAL_THRESHOLD` - Credit critical threshold (default: 100)
- `CLOUD_SERVICE` - Enable cloud service mode (default: false)
- `SSE_LOCAL` - Enable local SSE mode
- `HTTP_STREAMABLE_SERVER` - Enable HTTP streaming server
- `PORT` - Server port (default: 3000)
- `HOST` - Server host (default: localhost, 0.0.0.0 for cloud)

### Key Implementation Details

**API Key Extraction (lines 15-32)**
- Supports multiple header formats: `x-firecrawl-api-key`, `x-api-key`, `authorization: Bearer <token>`
- Handles both string and array header values

**Empty Value Cleanup (lines 34-52)**
- `removeEmptyTopLevel()` function removes null, empty strings, empty arrays, and empty objects from top-level options
- Ensures clean API requests to Firecrawl

**Firecrawl Client Creation (lines 122-135)**
- Creates client with optional API URL for self-hosted instances
- API key is optional when using self-hosted instances

**Logging**
- `ConsoleLogger` class implements structured logging with timestamps
- Only logs in cloud service, SSE local, or HTTP streamable server modes
- Log levels: debug, error, info, log, warn

## Module System

This project uses ES modules (`"type": "module"` in package.json):
- Import statements use `.js` extensions for relative paths
- TypeScript compiled to ES2022 with NodeNext module resolution
- Jest configured for ESM with `ts-jest`

## Testing

- Test framework: Jest with ts-jest preset for ESM
- Test files: `**/*.test.ts`
- Setup file: `jest.setup.ts`
- Module name mapping handles `.js` extensions in imports
