# Web Search MCP Server

A Model Context Protocol (MCP) server that provides web search capabilities to AI assistants like Claude Desktop. Search the web in real-time using DuckDuckGo without requiring API keys.

## Overview

This MCP server enables AI assistants to perform web searches and retrieve up-to-date information from the internet. It's designed to work with any MCP-compatible AI agent, including:
- **Claude Desktop** - Anthropic's desktop application  
- **Continue** - VS Code AI coding assistant extension
- **Custom MCP clients** - Any application implementing the MCP protocol

### Key Features

- 🔍 **Web Search**: Real-time web search using DuckDuckGo (no API keys required)
- 📚 **MCP Resources**: Expose search configurations and history as MCP resources
- 🎯 **MCP Prompts**: Pre-built prompt templates for common search scenarios
- ⚙️ **Configurable**: Flexible configuration for search parameters and behavior
- 🧪 **Well Tested**: Comprehensive test suite with 22+ unit tests
- 🔒 **Secure**: Input validation and error handling built-in
- 📊 **Modern**: Built with FastMCP, Pydantic v2, and modern Python practices
- 🔌 **MCP Compliant**: Follows Model Context Protocol best practices and standards

### Available MCP Tools

The server provides 2 primary MCP tools for AI assistants:

1. **`web_search`** - Search the web for information
2. **`get_search_config`** - Get current search configuration

### Available MCP Resources

The server exposes MCP resources for enhanced context:

1. **`search-configuration`** - Current search backend configuration and settings
2. **`search-history`** - Recent search queries and results (last 100 searches)

### Available MCP Prompts

The server provides reusable prompt templates:

1. **`web-search`** - General web search prompt template
2. **`news-search`** - News-specific search prompt template

## Quick Start

### Option 1: MCP Client Integration (Recommended)

For immediate use with MCP-compatible AI agents:

```bash
# Clone the repository
git clone https://github.com/thepeacefulprogrammer/web_search_mcp.git
cd web_search_mcp

# Run the automated MCP client setup
python setup_mcp_client.py
```

This interactive script will:
- Install the web search MCP server and dependencies
- Help you choose your MCP client (Claude Desktop, Continue, or custom)
- Configure the client's MCP configuration file automatically
- Test the server to ensure web search is working
- Show you the available search tools

**Then restart your MCP client and try these prompts:**
- "Search the web for the latest news about artificial intelligence"
- "What's the current weather in San Francisco?"
- "Find information about the latest Python 3.12 features"
- "Show me the current search configuration"
- "Use the web-search prompt template to find information about climate change"

### Option 2: Manual Development Setup

For development and customization:

```bash
# Clone the repository
git clone https://github.com/thepeacefulprogrammer/web_search_mcp.git
cd web_search_mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (for development)
pre-commit install
```

### Run the Server

```bash
# Run the MCP server
python -m web_search_mcp.server

# Or run with custom config
python -m web_search_mcp.server --config config/config.yaml

# Or use the console script (after pip install)
web-search-mcp-server
```

### Test the Server

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/test_search_handlers.py
pytest tests/unit/test_search_models.py
```

## Project Structure

```
web_search_mcp/
├── src/
│   └── web_search_mcp/           # Main package
│       ├── __init__.py
│       ├── server.py              # Main MCP server
│       ├── handlers/              # MCP tool handlers
│       │   ├── __init__.py
│       │   └── search_handlers.py # Web search handlers
│       ├── models/                # Pydantic models
│       │   ├── __init__.py
│       │   └── search_models.py   # Search data models
│       ├── search/                # Search implementations
│       │   ├── __init__.py
│       │   └── duckduckgo.py      # DuckDuckGo search backend
│       └── utils/                 # Utility modules
│           ├── __init__.py
│           ├── config.py          # Configuration loading
│           └── auth.py            # Authentication utilities
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   │   ├── test_search_handlers.py
│   │   └── test_search_models.py
│   └── integration/               # Integration tests (future)
├── config/                        # Configuration files
│   └── config.yaml               # Default configuration
├── examples/                      # Example scripts (future)
├── tools/                         # Development tools (future)
├── tasks/                         # Project management
│   ├── prd-web-search-mcp.md     # Product requirements
│   └── tasks-prd-web-search-mcp.md # Task breakdown
├── logs/                          # Log files (auto-created)
├── pyproject.toml                 # Modern Python packaging
├── requirements.txt               # Dependencies
├── .pre-commit-config.yaml        # Code quality hooks
├── .gitignore                     # Git ignore rules
├── env.example                    # Environment template
└── README.md                      # This file
```

## Available MCP Tools

### 1. `web_search`
**Purpose**: Search the web for information using DuckDuckGo
**Parameters**:
- `query` (string, required): The search query to execute
- `max_results` (integer, optional): Maximum number of results to return (default: 10, max: 20)

**Example usage**: 
- "Search the web for 'Python async programming best practices'"
- "Find recent news about renewable energy with 5 results"

**Response**: JSON with search results including titles, URLs, descriptions, and snippets.

### 2. `get_search_config`
**Purpose**: Get the current search configuration and settings
**Parameters**: None

**Example usage**: "What are the current search configuration settings?"

**Response**: JSON with current search backend, limits, timeouts, and caching settings.

## MCP Resources

### `search-configuration`
**Purpose**: Provides current search backend configuration and settings
**Type**: Resource (read-only)
**Content**: JSON with search backend settings, rate limits, and feature flags

### `search-history`  
**Purpose**: Provides recent search queries and results for context
**Type**: Resource (read-only)
**Content**: JSON array of recent searches with queries, results, and timestamps

## MCP Prompts

### `web-search`
**Purpose**: General web search prompt template
**Arguments**: 
- `query` (string): The search query
- `max_results` (optional): Maximum number of results

### `news-search`
**Purpose**: News-specific search prompt template  
**Arguments**:
- `topic` (string): News topic to search for
- `time_range` (optional): Time range for news (e.g., "last 24 hours")

## Search Capabilities

### Current Features

- **DuckDuckGo Search**: Primary search backend (no API keys required)
- **Result Parsing**: Structured results with titles, URLs, descriptions, and snippets
- **Input Validation**: Query validation and parameter limits
- **Error Handling**: Graceful error handling with informative messages
- **MCP Resources**: Expose configuration and search history as MCP resources
- **MCP Prompts**: Reusable prompt templates for common search scenarios
- **Session Management**: Proper MCP session lifecycle handling

### Configuration Options

The server supports various configuration options in `config/config.yaml`:

```yaml
server:
  name: "web-search-mcp"
  description: "Web Search MCP Server"
  transport: "stdio"  # stdio, sse, or streamable-http

search:
  backend: "duckduckgo"
  max_results_limit: 20
  default_max_results: 10
  timeout: 30
  cache_enabled: true
  cache_ttl: 3600

mcp:
  resources:
    search_config:
      enabled: true
      name: "search-configuration"
    search_history:
      enabled: true
      name: "search-history"
      max_entries: 100
  
  prompts:
    web_search:
      name: "web-search"
      description: "Search the web for information"
    news_search:
      name: "news-search"
      description: "Search for recent news articles"

logging:
  level: "INFO"
  file_enabled: true
```

### Environment Variables

Set environment variables in `.env` for configuration:

```bash
# Copy from template
cp env.example .env

# Optional: Override default settings
SEARCH_MAX_RESULTS=15
SEARCH_TIMEOUT=45
LOG_LEVEL=DEBUG
```

## Data Models

The server uses Pydantic v2 models for data validation:

### SearchRequest
```python
{
  "query": "search terms",
  "max_results": 10,
  "search_type": "web"
}
```

### SearchResult
```python
{
  "title": "Page Title",
  "url": "https://example.com",
  "description": "Page description",
  "snippet": "Text snippet from page",
  "timestamp": "2025-01-01T12:00:00Z",
  "source": "duckduckgo",
  "relevance_score": 1.0
}
```

### SearchResponse
```python
{
  "success": true,
  "query": "search terms",
  "max_results": 10,
  "results": [...],
  "timestamp": "2025-01-01T12:00:00Z"
}
```

## Development

### Code Quality

This project enforces code quality with:
- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning
- **pre-commit**: Automated checks

```bash
# Format code
black src tests

# Sort imports  
isort src tests

# Lint code
flake8 src tests

# Type check
mypy src

# Security scan
bandit -r src
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test files
pytest tests/unit/test_search_handlers.py
pytest tests/unit/test_search_models.py

# Run tests with verbose output
pytest -v
```

### Adding New Search Features

To extend the search functionality:

1. **Add new models** in `src/web_search_mcp/models/search_models.py`
2. **Create handlers** in `src/web_search_mcp/handlers/search_handlers.py`
3. **Register MCP tools** in `src/web_search_mcp/server.py`
4. **Add tests** for your new functionality
5. **Update configuration** if needed

Example of adding a new MCP tool:

```python
@self.mcp.tool()
async def advanced_search(
    query: str,
    domain_filter: Optional[str] = None,
    time_range: Optional[str] = None,
) -> str:
    """Advanced web search with filtering options."""
    result = await advanced_search_handler(query, domain_filter, time_range)
    return result
```

## Deployment

### Environment Setup

1. **Production environment**:
   ```bash
   cp env.example .env
   # Edit .env with production values
   ```

2. **Install production dependencies**:
   ```bash
   pip install .
   ```

3. **Run server**:
   ```bash
   python -m web_search_mcp.server --config config/production.yaml
   ```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install .

EXPOSE 8000
CMD ["python", "-m", "web_search_mcp.server"]
```

### Systemd Service

Create a systemd service file:

```ini
[Unit]
Description=Web Search MCP Server
After=network.target

[Service]
Type=simple
User=websearch
WorkingDirectory=/opt/web-search-mcp
ExecStart=/opt/web-search-mcp/venv/bin/python -m web_search_mcp.server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Roadmap

### Phase 1: Foundation ✅
- [x] Basic project structure and MCP server setup
- [x] DuckDuckGo search integration (placeholder)
- [x] Core data models and validation
- [x] Comprehensive testing framework

### Phase 2: Core Search (In Progress)
- [ ] Full DuckDuckGo search implementation
- [ ] MCP resource support for configuration and search history
- [ ] MCP prompt templates for common search scenarios
- [ ] Content extraction and summarization
- [ ] Search result caching
- [ ] Advanced error handling

### Phase 3: Enhanced Features (Planned)
- [ ] Multiple search backends (Google, Bing)
- [ ] Domain filtering and time-based search
- [ ] Search result ranking and relevance
- [ ] Rate limiting and quota management
- [ ] Advanced MCP resource management

### Phase 4: Production Ready (Planned)
- [ ] Performance optimization
- [ ] MCP-compliant authentication and security
- [ ] Documentation and deployment guides
- [ ] Integration examples

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and quality checks
5. Submit a pull request

### Development Setup

```bash
# Clone your fork
git clone <your-fork-url>
cd web_search_mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Contributing**: See CONTRIBUTING.md for development guidelines

## Changelog

### v0.1.0 (Current)
- Initial web search MCP server release
- DuckDuckGo search integration (placeholder)
- Core MCP tools: web_search, get_search_config
- MCP resources: search-configuration, search-history
- MCP prompts: web-search, news-search templates
- Comprehensive Pydantic v2 data models
- Full test suite with 22+ unit tests
- Modern Python packaging and development tools
- FastMCP integration with proper tool registration
- MCP best practices compliance
