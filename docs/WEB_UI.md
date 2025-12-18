# Gradio Web UI

The Gradio Web UI provides an intuitive interface for interacting with the Git RAG Chat system.

## Features

### 1. Chat Interface
- Natural language querying of code repositories
- Message history with markdown rendering
- Code syntax highlighting in responses
- Source code snippets with file locations
- Adjustable temperature and result count settings

### 2. Repository Management
- Directory picker with real-time Git validation
- Add and index repositories via path input
- View repository information (branch, commits, file count)
- List all indexed repositories
- Switch between repositories

### 3. Settings & Help
- Configuration display
- Usage tips and troubleshooting
- LLM provider information

## Usage

### Starting the UI

```bash
# From project root
docker-compose up web-ui

# Or start all services
docker-compose up
```

The UI will be available at: http://localhost:7860

### Adding a Repository

1. Navigate to the **Repository** tab
2. Enter the full path to your Git repository in the text box
3. Watch for real-time validation feedback
4. Click **Add & Index Repository** to start indexing
5. View repository information and indexing status

Example paths:
- `/Users/yourname/projects/my-app`
- `/home/user/code/my-project`

### Querying Your Code

1. Ensure a repository is indexed (check Repository tab)
2. Navigate to the **Chat** tab
3. Type your question in natural language
4. Click **Send** or press Enter
5. View the response with source code references

Example queries:
- "How does authentication work?"
- "Show me the database connection logic"
- "What are the API endpoints?"
- "Where is error handling implemented?"

### Query Settings

- **Temperature** (0.0 - 1.0): Controls LLM creativity
  - Lower (0.1): Focused, factual responses
  - Higher (0.7): More creative, exploratory responses

- **Max Results** (1 - 20): Number of code chunks to retrieve
  - Lower (5): Faster, more focused
  - Higher (15): More comprehensive context

## Components

### Chat Interface ([chat.py](src/components/chat.py))
- Handles user queries
- Formats responses with code highlighting
- Manages chat history
- Integrates with RAG API

### Repository Manager ([repo_manager.py](src/components/repo_manager.py))
- Directory path validation
- Repository addition and indexing
- Status monitoring
- Repository listing

### Repository Validator ([repo_validator.py](src/components/repo_validator.py))
- Real-time Git repository validation
- Path security checks
- Repository metadata extraction

## Environment Variables

Configure via `.env` or `docker-compose.yml`:

```bash
# RAG Pipeline API
RAG_API_URL=http://rag-pipeline:8001

# Server Configuration
GRADIO_SERVER_PORT=7860

# Security: Allowed parent directories
GRADIO_ALLOWED_PATHS=/Users,/home

# Logging
LOG_LEVEL=INFO
```

## Security

### Path Restrictions

The `GRADIO_ALLOWED_PATHS` environment variable restricts which directories users can select:

```bash
# Only allow repositories under /Users and /home
GRADIO_ALLOWED_PATHS=/Users,/home

# Allow all paths (not recommended for production)
GRADIO_ALLOWED_PATHS=
```

### Validation

- All paths are validated before indexing
- Git repository checks ensure only valid repos are processed
- Path traversal protection prevents accessing restricted directories

## Testing

Run the test suite:

```bash
cd services/web-ui
python test_phase7.py
```

Tests cover:
- Component imports
- Repository validation
- Chat interface formatting
- Gradio app structure

## Troubleshooting

### UI Not Loading

1. Check if the container is running:
   ```bash
   docker ps | grep git-rag-ui
   ```

2. Check logs:
   ```bash
   docker logs git-rag-ui
   ```

3. Verify RAG pipeline is accessible:
   ```bash
   curl http://localhost:8001/api/health
   ```

### Repository Not Indexing

1. Check if path is valid and is a Git repository
2. Verify path is within allowed directories
3. Check RAG pipeline logs:
   ```bash
   docker logs git-rag-pipeline
   ```

### No Query Results

1. Ensure repository is fully indexed (check Status)
2. Try increasing Max Results setting
3. Rephrase query to be more specific
4. Check if LLM provider is configured correctly

### Connection Errors

If you see "Connection Error" messages:

1. Verify RAG pipeline is running:
   ```bash
   docker-compose ps rag-pipeline
   ```

2. Check network connectivity:
   ```bash
   docker exec git-rag-ui ping rag-pipeline
   ```

3. Restart services:
   ```bash
   docker-compose restart
   ```

## Development

### Local Development

Run the UI locally for development:

```bash
cd services/web-ui

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export RAG_API_URL=http://localhost:8001
export GRADIO_SERVER_PORT=7860
export GRADIO_ALLOWED_PATHS=/Users,/home

# Run the app
python src/app.py
```

### File Structure

```
services/web-ui/
├── src/
│   ├── app.py                 # Main Gradio application
│   └── components/
│       ├── __init__.py
│       ├── chat.py            # Chat interface logic
│       ├── repo_manager.py    # Repository management
│       └── repo_validator.py  # Git validation
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container definition
├── test_phase7.py            # Test suite
└── README.md                  # This file
```

## API Integration

The UI communicates with the RAG pipeline via REST API:

- `POST /api/repos` - Add repository
- `GET /api/repos` - List repositories
- `GET /api/repos/{id}/status` - Get indexing status
- `POST /api/query` - Query repository
- `POST /api/query/stream` - Streaming query (future)

See RAG pipeline API docs at http://localhost:8001/docs

## Future Enhancements

- Streaming responses for real-time LLM output
- Repository comparison across multiple repos
- Export chat history
- Advanced search filters
- Code snippet preview before indexing
- Visual file explorer (alternative to text path input)
