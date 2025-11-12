# Contributing to AI Automotive Service Scheduler

Thank you for your interest in contributing to this project! This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/khvni/automotive-service-scheduler-voice-agent.git
cd automotive-service-scheduler-voice-agent
```

2. **Run setup**

```bash
make setup
```

This will:
- Install all dependencies
- Set up Docker services
- Initialize the database
- Install pre-commit hooks

3. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your API keys
```

## Development Workflow

### Starting Services

```bash
# Start all services
make dev

# Or start individually
make server   # FastAPI server
make worker   # Background worker
make web      # React admin UI
```

### Using Docker

```bash
# Start Docker services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

### Available Make Commands

Run `make help` to see all available commands:

```bash
make help         # Show all commands
make install      # Install dependencies
make test         # Run tests
make lint         # Run linters
make format       # Format code
make security     # Run security checks
make clean        # Clean temporary files
```

## Code Style

This project follows strict code style guidelines enforced by pre-commit hooks.

### Python

- **Formatting**: Black (line length: 100)
- **Import sorting**: isort
- **Linting**: Flake8
- **Type checking**: MyPy
- **Security**: Bandit

### JavaScript/TypeScript

- **Formatting**: Prettier
- **Linting**: ESLint (if configured)

### Running Code Quality Checks

```bash
# Format code
make format

# Run linters
make lint

# Run security checks
make security
```

## Testing

### Writing Tests

- Place unit tests in `server/tests/` or `worker/tests/`
- Use pytest fixtures for common setup
- Mock external services (Twilio, Deepgram, OpenAI)

Example test structure:

```python
# server/tests/test_crm_tools.py
import pytest
from app.tools.crm_tools import lookup_customer

@pytest.mark.asyncio
async def test_lookup_customer(db_session):
    customer = await lookup_customer(db_session, "+15551234567")
    assert customer is not None
    assert customer["name"] == "John Doe"
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
cd server && source venv/bin/activate && pytest tests/test_crm_tools.py -v

# Run with coverage
cd server && source venv/bin/activate && pytest --cov=app tests/
```

## Commit Guidelines

This project uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by Commitizen.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semi-colons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

### Examples

```bash
# Feature
feat(voice): add WebSocket audio streaming support

# Bug fix
fix(crm): resolve customer lookup by phone number

# Documentation
docs(readme): update setup instructions

# Refactor
refactor(tools): extract calendar service to separate module
```

### Using Commitizen

```bash
# Interactive commit
cz commit

# Or use git commit (will be checked by hook)
git commit -m "feat(server): add health check endpoint"
```

## Pull Request Process

1. **Create a branch**

```bash
git checkout -b feat/your-feature-name
```

2. **Make your changes**

- Write code following style guidelines
- Add tests for new functionality
- Update documentation as needed

3. **Run quality checks**

```bash
make format
make lint
make test
```

4. **Commit your changes**

```bash
git add .
git commit -m "feat(scope): description"
```

Pre-commit hooks will automatically run and must pass before the commit succeeds.

5. **Push to your fork**

```bash
git push origin feat/your-feature-name
```

6. **Create a Pull Request**

- Use a clear, descriptive title
- Reference any related issues
- Describe your changes in detail
- Include screenshots for UI changes

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow conventional commits
- [ ] No sensitive data (API keys, secrets) committed

## Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality. Hooks are automatically installed when you run `make setup` or `make install-hooks`.

### Hooks Configured

1. **Black** - Code formatting
2. **isort** - Import sorting
3. **Flake8** - Linting
4. **MyPy** - Type checking
5. **Bandit** - Security linting
6. **detect-secrets** - Prevent API keys from being committed
7. **Prettier** - Frontend formatting
8. **Commitizen** - Commit message linting

### Running Hooks Manually

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## Architecture Overview

```
automotive-voice/
├── server/         # FastAPI backend
│   ├── app/
│   │   ├── models/     # SQLAlchemy models
│   │   ├── routes/     # API endpoints
│   │   ├── services/   # Core services
│   │   └── tools/      # AI agent tools
│   └── tests/
├── worker/         # Background jobs
│   └── jobs/
├── web/            # React admin UI
│   └── src/
├── infra/          # Docker configuration
└── scripts/        # Utility scripts
```

## Questions?

If you have questions or need help:

1. Check existing issues on GitHub
2. Open a new issue with the `question` label
3. Contact the maintainer: [@khvni](https://github.com/khvni)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
