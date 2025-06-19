# MCP Scaffolding Project

A template for creating Model Context Protocol (MCP) servers using FastMCP with modern Python best practices.

## Overview

This project provides a solid foundation for building MCP servers that work with any MCP-compatible AI agent, including:
- **Claude Desktop** - Anthropic's desktop application
- **Continue** - VS Code AI coding assistant extension
- **Custom MCP clients** - Any application implementing the MCP protocol

The scaffolding includes:
- **FastMCP** for MCP server implementation
- **Modern Python packaging** with pyproject.toml
- **Pydantic models** for data validation
- **Comprehensive testing** with pytest
- **Code quality tools** (black, isort, flake8, mypy, bandit)
- **Pre-commit hooks** for automated quality checks
- **Structured logging** with file and console output
- **Configuration management** with YAML files
- **Authentication utilities** for API keys and tokens

## Quick Start

### Option 1: MCP Client Integration (Recommended)

For immediate testing with MCP-compatible AI agents:

```bash
# Clone this template (or use as template on GitHub)
git clone <your-repo-url> my-new-mcp-server
cd my-new-mcp-server

# Run the automated MCP client setup
python setup_mcp_client.py
```

This interactive script will:
- Install the MCP server and dependencies
- Help you choose your MCP client (Claude Desktop, Continue, or custom)
- Configure the client's `mcp.json` file automatically
- Test the server to ensure it's working
- Show you the available example tools

**Then restart your MCP client and try these prompts:**
- "Test the connection to the MCP scaffolding server"
- "Create an example tool called 'my-first-tool'"
- "Get some example data from the scaffolding server"

### Option 2: Manual Development Setup

For development and customization:

```bash
# Clone this template (or use as template on GitHub)
git clone <your-repo-url> my-new-mcp-server
cd my-new-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 2. Configure Your Project

1. **Update pyproject.toml**: Change project name, description, and author info
2. **Configure environment**: Copy `env.example` to `.env` and set your variables
3. **Update config/config.yaml**: Modify server configuration as needed
4. **Replace example code**: Replace the example handlers and models with your logic

### 3. Run the Server

```bash
# Run the MCP server
python -m web_search_mcp.server

# Or run with custom config
python -m web_search_mcp.server --config config/my_config.yaml

# Or use the console script (after pip install)
web-search-mcp-server
```

### 4. Test Your Server

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test category
pytest -m unit
pytest -m integration
```

## Project Structure

```
my_web_search_mcp/
├── src/
│   └── web_search_mcp/           # Main package
│       ├── __init__.py
│       ├── server.py              # Main MCP server
│       ├── handlers/              # MCP tool handlers
│       │   ├── __init__.py
│       │   └── example_handlers.py
│       ├── models/                # Pydantic models
│       │   ├── __init__.py
│       │   └── example_models.py
│       └── utils/                 # Utility modules
│           ├── __init__.py
│           ├── config.py          # Configuration loading
│           └── auth.py            # Authentication utilities
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
├── config/                        # Configuration files
│   └── config.yaml               # Default configuration
├── docs/                          # Documentation
├── logs/                          # Log files (auto-created)
├── pyproject.toml                 # Modern Python packaging
├── .pre-commit-config.yaml        # Code quality hooks
├── .gitignore                     # Git ignore rules
├── env.example                    # Environment template
└── README.md                      # This file
```

## Available Example Tools

The scaffolding comes with 3 example MCP tools that you can test immediately:

### 1. `test_connection`
**Purpose**: Test the MCP server connection
**Parameters**:
- `message` (string, optional): A test message

**Example usage**: "Test the connection to the MCP scaffolding server"

### 2. `create_example_tool`
**Purpose**: Create a new example tool (demonstrates data creation)
**Parameters**:
- `name` (string, required): The name of the tool
- `description` (string, optional): Description of the tool
- `category` (string, optional): Category (default: "general")

**Example usage**: "Create an example tool called 'data-processor' with description 'Processes user data' in the utility category"

### 3. `get_example_data`
**Purpose**: Retrieve example data from the server (demonstrates data retrieval)
**Parameters**:
- `data_type` (string, optional): Type of data to retrieve (default: "all")
- `limit` (integer, optional): Maximum number of items (default: 10)

**Example usage**: "Get example data of type 'text' with a limit of 5"

> **Note**: These are example tools for demonstration purposes. Replace them with your actual business logic when building your MCP server.

## Customizing Your MCP Server

### 1. Replace Example Code

The scaffolding includes example handlers and models that you should replace:

- `src/web_search_mcp/handlers/example_handlers.py` - Replace with your MCP tool logic
- `src/web_search_mcp/models/example_models.py` - Replace with your data models
- `tests/unit/test_example_*.py` - Update tests for your code

### 2. Add New MCP Tools

To add a new MCP tool:

1. **Create handler function** in `handlers/` directory
2. **Register the tool** in `server.py` using `@self.mcp.tool()` decorator
3. **Add tests** for your new tool
4. **Update configuration** if needed

Example:
```python
@self.mcp.tool()
async def my_new_tool(param1: str, param2: int = 10) -> str:
    """Description of what this tool does."""
    result = await my_new_tool_handler(param1, param2)
    return result
```

### 3. Configuration Management

Update `config/config.yaml` for your needs:

```yaml
server:
  name: "my-mcp-server"
  description: "My custom MCP server"

application:
  my_setting: "my_value"
  api_timeout: 30

external_services:
  my_api:
    base_url: "https://api.example.com"
    timeout: 30
```

### 4. Environment Variables

Add your API keys and secrets to `.env`:

```bash
# Copy from template
cp env.example .env

# Edit with your values
MY_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./data.db
```

## Development Workflow

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

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m "not slow"

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_example_handlers.py
```

### Pre-commit Hooks

Pre-commit hooks automatically run quality checks:

```bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## MCP Tool Development

### Handler Pattern

Follow this pattern for MCP tool handlers:

```python
async def my_tool_handler(
    param1: str,
    param2: Optional[int] = None,
) -> str:
    """
    Handler function for MCP tool.

    Args:
        param1: Description of parameter
        param2: Optional parameter with default

    Returns:
        JSON string with result
    """
    logger.info(f"my_tool_handler called with param1={param1}")

    try:
        # Your business logic here
        result = await some_async_operation(param1, param2)

        return json.dumps({
            "success": True,
            "data": result,
        })
    except Exception as e:
        logger.error(f"my_tool_handler failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })
```

### Model Validation

Use Pydantic models for data validation:

```python
from pydantic import BaseModel, Field, validator

class MyDataModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    value: int = Field(..., ge=0, le=1000)
    category: str = Field(default="general")

    @validator('category')
    def validate_category(cls, v):
        allowed = ['general', 'special', 'admin']
        if v not in allowed:
            raise ValueError(f'Category must be one of: {allowed}')
        return v
```

### Error Handling

Use consistent error handling:

```python
try:
    # Your code here
    result = await operation()
    return json.dumps({"success": True, "data": result})
except ValidationError as e:
    return json.dumps({"success": False, "error": f"Validation error: {e}"})
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return json.dumps({"success": False, "error": "Internal server error"})
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
Description=MCP Scaffolding Server
After=network.target

[Service]
Type=simple
User=mcp
WorkingDirectory=/opt/mcp-server
ExecStart=/opt/mcp-server/venv/bin/python -m web_search_mcp.server
Restart=always

[Install]
WantedBy=multi-user.target
```

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
cd mcp-scaffolding

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

- Create issues for bugs or feature requests
- Check existing issues for solutions
- Contribute improvements via pull requests

## Changelog

### v0.1.0
- Initial scaffolding release
- FastMCP integration
- Modern Python packaging
- Comprehensive testing setup
- Code quality tooling
- Configuration management
- Authentication utilities
