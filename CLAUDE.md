# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MeshCore Bot is a Python bot that connects to MeshCore mesh networks via serial port, BLE, or TCP/IP. It responds to messages with configured keywords, executes commands, and provides various data services. The bot uses a modular plugin architecture with a web-based dashboard for monitoring.

## Development Commands

### Environment Setup

```bash
# Create virtual environment and install all dependencies including test tools
make dev

# Install runtime + optional dependencies only (production)
make install
```

### Configuration

```bash
# Launch interactive ncurses config editor (recommended)
make config

# Or manually copy example config
cp config.ini.example config.ini
# Edit config.ini with your settings
```

### Running the Bot

```bash
# Development
.venv/bin/python meshcore_bot.py

# Or as installed package
.venv/bin/meshcore-bot

# Web viewer standalone
.venv/bin/meshcore-viewer
```

### Testing

```bash
# Full test suite with coverage (coverage threshold: 35%)
make test

# Without coverage (faster iteration)
make test-no-cov

# Run specific test file
.venv/bin/pytest tests/test_message_handler.py -v

# Run specific test class or function
.venv/bin/pytest tests/test_enums.py::TestPayloadType::test_lookup_by_value -v

# Run by marker
pytest -m unit               # unit tests only (fast)
pytest -m integration        # integration tests (real DB)
pytest -m "not slow"         # skip slow tests

# Stop on first failure
pytest -x
```

### Linting and Type Checking

```bash
# Run all linting (ruff + mypy)
make lint

# Auto-fix ruff issues
make fix

# Individual tools
.venv/bin/ruff check modules/ tests/
.venv/bin/mypy modules/
```

### Building

```bash
# Build Debian package
make deb

# Docker deployment
docker compose up -d --build
```

## Production Deployment

**IMPORTANT: Always deploy changes to the production server after committing and pushing to main.**

The production bot runs on `brian@10.100.10.49` at `/opt/meshcore-bot/` as a systemd service.

### Deployment Workflow

After making changes and pushing to main, deploy to production:

```bash
# 1. Sync modules directory to server
rsync -avz --delete modules/ brian@10.100.10.49:/opt/meshcore-bot/modules/

# 2. Fix ownership (modules directory is owned by meshcore:meshcore)
ssh brian@10.100.10.49 "sudo chown -R meshcore:meshcore /opt/meshcore-bot/modules/"

# 3. Restart the bot service
ssh brian@10.100.10.49 "sudo systemctl restart meshcore-bot"

# 4. Verify service is running
ssh brian@10.100.10.49 "sudo systemctl status meshcore-bot --no-pager"

# 5. Monitor logs for startup issues
ssh brian@10.100.10.49 "sudo journalctl -u meshcore-bot --since '1 minute ago' --no-pager | tail -20"
```

### Production Server Details

- **Server**: brian@10.100.10.49
- **Install Path**: /opt/meshcore-bot/
- **Service**: meshcore-bot.service (systemd)
- **User**: meshcore (service runs as this user)
- **Config**: /opt/meshcore-bot/config.ini
- **Logs**: `sudo journalctl -u meshcore-bot -f`
- **Data**: /opt/meshcore-bot/data/

### Deployment Notes

- The server installation is NOT a git repository
- Use `rsync` to sync code changes (not git pull)
- Always fix ownership after rsync (files are owned by meshcore user)
- The bot automatically reloads on service restart
- Configuration changes require manual editing on server or rsync of config.ini
- Database migrations run automatically on startup

### Quick Deploy Script

For convenience, you can run all deployment steps with:

```bash
# One-liner to deploy and verify
rsync -avz --delete modules/ brian@10.100.10.49:/opt/meshcore-bot/modules/ && \
ssh brian@10.100.10.49 "sudo chown -R meshcore:meshcore /opt/meshcore-bot/modules/ && \
sudo systemctl restart meshcore-bot && \
sudo systemctl status meshcore-bot --no-pager"
```

## Architecture Overview

The bot uses a modular plugin architecture with clear separation of concerns:

### Core Components

- **`meshcore_bot.py`** — Entry point; parses CLI args, configures signal handlers, runs main loop
- **`modules/core.py`** — `MeshCoreBot` class; main bot lifecycle, config loading, connection management
- **`modules/message_handler.py`** — `MessageHandler` class; processes incoming messages, routes to commands
- **`modules/command_manager.py`** — `CommandManager` class; keyword matching, rate limiting, command dispatch
- **`modules/scheduler.py`** — `MessageScheduler` class; background thread for scheduled messages and tasks

### Database and State Management

- **`modules/db_manager.py`** — `DBManager` and `AsyncDBManager` classes; SQLite wrapper with migration support
- **`modules/db_migrations.py`** — `MigrationRunner` class; versioned database schema migrations
- **`modules/repeater_manager.py`** — `RepeaterManager` class; tracks repeaters, companions, and contact roles
- **`modules/mesh_graph.py`** — `MeshGraph` class; builds and maintains network topology graph from observed paths
- **`modules/transmission_tracker.py`** — `TransmissionTracker` class; tracks message transmissions and repeater usage

### Command Plugin System

Command plugins live in `modules/commands/` and inherit from `BaseCommand` (`modules/commands/base_command.py`).

**Key concepts:**
- Each command defines `name`, `keywords`, and `description`
- Commands must implement `async def execute(self, message: MeshMessage) -> bool`
- Commands can be enabled/disabled via config sections (e.g., `[Ping_Command] enabled = true`)
- Command aliases are defined via `aliases = ` key in config section
- Plugin loader (`modules/plugin_loader.py`) auto-discovers and loads all command plugins

**Example command structure:**
```python
from .base_command import BaseCommand
from ..models import MeshMessage

class MyCommand(BaseCommand):
    name = "mycommand"
    keywords = ['mycommand']
    description = "My custom command"

    async def execute(self, message: MeshMessage) -> bool:
        await self.send_response(message, "Hello from my command!")
        return True
```

### Service Plugin System

Service plugins live in `modules/service_plugins/` and inherit from `BaseServicePlugin` (`modules/service_plugins/base_service.py`).

**Key concepts:**
- Service plugins are background services (Discord/Telegram bridges, webhook, packet capture, weather, etc.)
- Each service sets `config_section = 'My_Section'` and implements `async start()` and `async stop()`
- Services are enabled/disabled via config (e.g., `[Discord_Bridge] enabled = true`)
- Service plugin loader (`modules/service_plugin_loader.py`) auto-discovers and loads all service plugins

**Example service structure:**
```python
from .base_service import BaseServicePlugin

class MyService(BaseServicePlugin):
    config_section = 'My_Service'

    async def start(self) -> None:
        # Initialize service
        pass

    async def stop(self) -> None:
        # Cleanup
        pass
```

### Web Viewer

The web viewer (`modules/web_viewer/`) is a Flask + SocketIO application providing a browser dashboard.

- **`modules/web_viewer/app.py`** — Flask routes, SocketIO handlers, authentication
- **`modules/web_viewer/integration.py`** — `WebViewerIntegration` class; bridges bot state to web viewer
- **`modules/web_viewer/templates/`** — Jinja2 HTML templates
- **`modules/web_viewer/static/`** — JavaScript, CSS, client-side packet decoder

**Key features:**
- Live contact list, mesh graph visualization, radio settings management
- RSS/API feed subscriptions per channel
- Real-time packet/log monitoring with filtering and pause controls
- In-browser configuration editor for bot settings

### Rate Limiting

Rate limiting is implemented via multiple classes in `modules/rate_limiter.py`:

- **`RateLimiter`** — Global rate limit (minimum seconds between any bot reply)
- **`PerUserRateLimiter`** — Per-user rate limit (identified by pubkey or name)
- **`ChannelRateLimiter`** — Per-channel rate limit (overrides global per channel)
- **`BotTxRateLimiter`** — Bot transmission rate limit (minimum seconds between mesh transmissions)
- **`NominatimRateLimiter`** — Rate limit for Nominatim geocoding API (1 req/sec)

### Utility Modules

- **`modules/utils.py`** — Shared utilities: location parsing, distance calculation, path parsing, timezone handling
- **`modules/response_template.py`** — Template variable substitution for keyword responses
- **`modules/i18n.py`** — `Translator` class; internationalization support (loads JSON translations from `translations/`)
- **`modules/security_utils.py`** — Input validation, path sanitization, API key format checking
- **`modules/profanity_filter.py`** — Profanity filtering (optional `better-profanity` integration)

## Key Architecture Patterns

### Plugin Discovery and Loading

Both command and service plugins are auto-discovered:
1. Loader scans plugin directory for `.py` files
2. Each file is imported as a module
3. Loader finds classes inheriting from `BaseCommand` or `BaseServicePlugin`
4. Plugin is validated (must have async `execute()` or `start()`/`stop()`)
5. Enabled plugins are loaded into the bot's command/service registry

**Local plugins:** Users can add plugins to `local/commands/` or `local/service_plugins/` without modifying core code.

### Database Migration System

Database schema is versioned using `modules/db_migrations.py`:
- Migrations are defined as functions `_mNNNN_short_desc(cursor)`
- Each migration is registered in `MIGRATIONS` list with version number and description
- `MigrationRunner` tracks applied migrations in `schema_migrations` table
- Migrations run once on bot startup if not already applied

**Adding a migration:**
1. Write `_mNNNN_short_desc(cursor)` function in `modules/db_migrations.py`
2. Append `(NNNN, "description", _mNNNN_...)` to `MIGRATIONS` list
3. Never modify or remove existing migrations — always add new ones

### Message Processing Flow

1. MeshCore interface receives packet → `on_receive()` callback
2. `MessageHandler.handle_mesh_message()` processes packet
3. Message is checked against rate limits, ban list, monitored channels
4. `CommandManager.check_keywords()` matches keywords against config
5. If matched, corresponding command plugin's `execute()` method is called
6. Command sends response via `BaseCommand.send_response()` or `send_channel_message()`

### Configuration System

Configuration is loaded from `config.ini` (INI format):
- `[Connection]` — Serial/BLE/TCP connection settings
- `[Bot]` — Bot behavior, rate limits, startup options
- `[Keywords]` — Keyword-response pairs with template variables
- `[Channels]` — Monitored channels, DM settings
- `[Rate_Limits]` — Per-channel rate limit overrides
- Command sections (e.g., `[Ping_Command]`) — Per-command configuration
- Service sections (e.g., `[Discord_Bridge]`) — Per-service configuration

**Config reload:** Send SIGHUP to reload config without restarting (Unix only)

**Local config merge:** `local/config.ini` is automatically merged if present (overrides base config)

### Mesh Graph System

`MeshGraph` (`modules/mesh_graph.py`) builds network topology from observed message paths:

- **Edge tracking:** Records observations of each node-to-node connection with SNR, RSSI, timestamps
- **Multi-byte prefix support:** Handles 1-byte and 2-byte node prefixes
- **Path validation:** Validates paths based on confidence, recency, and bidirectional observations
- **Path inference:** Finds intermediate nodes for multi-hop paths using graph traversal
- **Persistence:** Stores graph data in SQLite with periodic background writes
- **Scoring system:** Ranks candidate paths by edge quality, hop position, and observation count

**Key methods:**
- `add_or_update_edge()` — Add/update edge with RF data
- `find_intermediate_nodes()` — Infer multi-hop paths
- `validate_path()` — Check if path is valid based on confidence thresholds
- `get_candidate_score()` — Score path candidates for selection

## Testing Architecture

### Test Organization

Tests are organized by type:
- **`tests/`** — Root-level tests for core modules
- **`tests/commands/`** — Command plugin tests
- **`tests/unit/`** — Pure unit tests (no DB, no network)
- **`tests/integration/`** — Integration tests with real SQLite DB
- **`tests/regression/`** — Regression guards for past bugs

### Shared Test Infrastructure

**`tests/conftest.py`** provides fixtures:
- `mock_logger` — Mock logger with standard methods
- `minimal_config` — ConfigParser with core sections
- `command_mock_bot` — Lightweight mock bot (no DB)
- `command_mock_bot_with_db` — Mock bot with mock `db_manager`
- `test_db` — Real file-based DBManager at `tmp_path`
- `mock_bot` — Mock bot with logger, config, DB, prefix helpers
- `mesh_graph` — MeshGraph instance (no background thread)
- `populated_mesh_graph` — MeshGraph pre-loaded with test edges

**`tests/helpers.py`** provides factories:
- `create_test_repeater()` — Dict matching contact tracking schema
- `create_test_edge()` — Dict matching MeshGraph edge structure
- `create_test_path()` — Normalized list of node IDs
- `populate_test_graph()` — Populates MeshGraph with edge dicts

### Test Markers

Tests can be marked for selective execution:
- `@pytest.mark.unit` — Fast unit tests (no real DB)
- `@pytest.mark.integration` — Integration tests (real SQLite)
- `@pytest.mark.slow` — Slow tests (skip with `-m "not slow"`)
- `@pytest.mark.mqtt` — MQTT live tests (require broker)

### Writing New Tests

**Conventions:**
- Use class-based test organization (`class TestFeatureName:`)
- Async tests work without `@pytest.mark.asyncio` (set via `pytest.ini`)
- Prefer conftest fixtures over creating mocks inline
- Use `tmp_path` for file-based SQLite (avoids cross-connection issues)
- Use `MagicMock` for sync methods, `AsyncMock` for async methods

**Example skeleton:**
```python
"""Tests for modules/my_module.py — MyClass."""

import pytest
from unittest.mock import Mock, AsyncMock
from modules.my_module import MyClass


@pytest.fixture
def my_obj(mock_logger):
    bot = Mock()
    bot.logger = mock_logger
    return MyClass(bot)


class TestMyFeature:

    def test_pure_logic(self, my_obj):
        result = my_obj.some_method("input")
        assert result == "expected"

    async def test_async_method(self, my_obj):
        my_obj.bot.send = AsyncMock(return_value=True)
        result = await my_obj.async_method("msg")
        assert result is True
```

## Type Checking

`mypy` is configured with incremental strict mode:
- Global baseline: safe non-breaking options
- Per-module overrides tighten settings for fully-typed modules (see `pyproject.toml`)
- New modules should use full type annotations and be added to strict overrides
- Legacy modules have `ignore_errors = true` until they are fully annotated

## Code Style

`ruff` is configured for Python 3.10+ with line length 120:
- Core rules: E, F, W, I, UP, B, C4, SIM
- Many legacy-code tolerances are ignored (see `pyproject.toml` for full list)
- Use `make fix` to auto-fix safe issues before committing

## Important Development Notes

### Database Handling

- Always use `tmp_path` fixtures for test databases (not in-memory `:memory:`)
- Never modify existing migrations — always add new ones
- Database path in config is resolved relative to config file directory

### Async Patterns

- Bot's main loop runs asyncio event loop
- Scheduler runs in background thread; uses `asyncio.run_coroutine_threadsafe()` to dispatch tasks to bot's loop
- Commands must be async (`async def execute()`)
- Use `await self.send_response()` or `await self.send_channel_message()` to send messages

### Plugin Development

- Command plugins: Inherit from `BaseCommand`, implement `async def execute()`
- Service plugins: Inherit from `BaseServicePlugin`, implement `async def start()` and `async def stop()`
- Plugin files must be placed in `modules/commands/` or `modules/service_plugins/`
- Local plugins can be placed in `local/commands/` or `local/service_plugins/`

### Multi-byte Prefix Support

The codebase supports both 1-byte and 2-byte node prefixes:
- Paths can be comma-separated (`12,34,56`) or continuous hex (`123456`)
- Path parsing functions auto-detect format and byte length
- MeshGraph handles 1→2→3 byte promotion when nodes are first seen

### Web Viewer Integration

- Web viewer runs in main asyncio loop via `modules/web_viewer/integration.py`
- SocketIO is used for real-time updates (packets, logs, live activity)
- Web viewer integration registers callbacks for bot events (new contact, packet, etc.)
- Database path resolution for web viewer is relative to config file directory
