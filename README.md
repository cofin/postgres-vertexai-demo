# ☕ PostgreSQL + pgvector + Vertex AI Coffee Demo

An intelligent coffee recommendation system showcasing PostgreSQL with pgvector for vector search and Google Vertex AI integration.

## 🚀 Quick Start

```bash
# Install dependencies with uv
make install-uv # Installs Astral's UV Python manager
make install

# Setup environment
cp .env.example .env  # Edit with your API keys

# Start PostgreSQL
make start-infra
uv run cymbal load-fixtures

# Start the application
uv run cymbal run
```

**Note: Embedding are included in the gzipped fixtures.**
If you'd like to regenerate embeddings, you can use:

```sh
uv run cymbal load-vectors
```

Visit [http://localhost:5006](http://localhost:5006) to try the demo!

## 🖼️ Screenshots

### Coffee Chat Interface

![Cymbal Coffee Chat Interface](docs/screenshots/cymbal_chat.png)
_AI-powered coffee recommendations with real-time performance metrics_

### Performance Dashboard

![Performance Dashboard](docs/screenshots/performance_dashboard.png)
_Live monitoring of PostgreSQL pgvector search performance and system metrics_

## 📚 Documentation

For complete implementation and development guides, see the [`docs/system/`](docs/system/) directory:

- **[Technical Overview](docs/system/01-technical-overview.md)** - High-level technical concepts
- **[PostgreSQL Architecture](docs/system/02-postgresql-architecture.md)** - PostgreSQL with pgvector extension
- **[Implementation Guide](docs/system/05-implementation-guide.md)** - Step-by-step build guide

### Recent Architecture Updates

- **[Architecture Updates](docs/architecture-updates.md)** - Recent improvements including:
    - Native HTMX integration with Litestar
    - Centralized exception handling system
    - Unified cache information API
    - Enhanced cache hit tracking
- **[HTMX Events Reference](docs/htmx-events.md)** - Complete list of custom HTMX events
- **[HTMX Migration Summary](docs/htmx-migration-summary.md)** - Details of the HTMX native integration
- **[Demo Scenarios](docs/system/07-demo-scenarios.md)** - Live demonstration scripts

## 🏗️ Architecture

This demo uses:

- **PostgreSQL + pgvector** - Open-source database with vector similarity search extension
- **Vertex AI** - Google's generative AI platform for embeddings and chat
- **Minimal Abstractions** - Direct PostgreSQL database access for clarity (and performance). No ORM
- **Litestar** - High-performance async Python framework
- **HTMX** - Real-time UI updates without JavaScript complexity

## 🎯 Key Features

This implementation is designed for conference demonstration with:

- **Real-time Chat Interface** - Personalized coffee recommendations with AI personas
- **Live Performance Metrics** - PostgreSQL pgvector search timing and cache hit rates
- **In-Memory Caching** - High-performance response caching using PostgreSQL
- **Native Vector Search** - Semantic similarity search without external dependencies
- **Intent Routing** - Natural language understanding via exemplar matching
- **Performance Dashboard** - Real-time monitoring of all system components

## 🔧 Development Commands

```bash
# Database operations
uv run cymbal load-fixtures        # Load sample data
uv run cymbal load-vectors         # Generate embeddings
uv run cymbal truncate-tables      # Reset all data
uv run cymbal clear-cache          # Clear response cache

# Export/Import (for faster demo startup)
uv run cymbal dump-data           # Export all data with embeddings
uv run cymbal dump-data --table intent_exemplar  # Export specific table
uv run cymbal dump-data --path /tmp/backup --no-compress  # Custom options

# Development
uv run cymbal run                 # Start the application
uv run pytest                  # Run tests
make lint                      # Code quality checks
```

## 📖 Additional Resources

- **PostgreSQL pgvector** - Open-source vector similarity search for AI applications
- [pgvector Documentation](https://github.com/pgvector/pgvector) - PostgreSQL extension for vector similarity search
- [Litestar Documentation](https://docs.litestar.dev) - Framework documentation
- [System Documentation](docs/system/) - Complete technical guides
