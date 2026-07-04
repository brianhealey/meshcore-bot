# US-015 Deployment Notes - LLM Tool Calling Integration

## Status: Ready for Manual Deployment

All autonomous development work for the LLM tool calling integration is **COMPLETE**. This document provides deployment instructions for the human administrator.

## Quality Verification (Pre-Deployment)

✅ **All quality checks passing:**
- 3077 tests passing
- 44.53% code coverage (above 35% requirement)
- All typechecks passing (mypy strict mode for new modules)
- All lints passing (ruff)
- Code ready on branch: `ralph/llm-tools-integration`

## What Was Implemented (US-001 through US-014)

### Database Schema Extension (US-001)
- Migration `_m0014_extend_llm_context_for_commands` adds:
  - `command_name` column (nullable TEXT) for tracking which command was executed
  - `sender_name` column (nullable TEXT) for user mention support

### User Mention Support (US-002)
- LLM responses automatically prefix with `[@username]` in channels
- DM responses skip the mention prefix
- Configurable via `include_user_mention` setting (default: true)

### Command Context Tracking (US-003, US-004)
- All command executions are now tracked in conversation context
- LLM can reference previous command results (wx, airplanes, path, etc.)
- Configurable via `track_all_commands` setting (default: true)

### Tool Calling Infrastructure (US-005 through US-008)
- `OllamaClient.chat()` method for LLM function calling
- `ToolRegistry` class for discovering commands and generating OpenAI-compatible schemas
- `ToolExecutor` class for safely executing LLM tool calls
- Integration in `LLMCommand` with tool-calling loop

### Tool Schemas (US-009 through US-012)
- Weather command (`wx`) with location and forecast_type parameters
- Aircraft tracking (`airplanes`) with optional radius parameter
- Satellite pass (`satpass`) with optional satellite and visual parameters
- Network path analysis (`path`) with required destination parameter

### Testing and Documentation (US-013, US-014)
- 8 comprehensive integration tests for end-to-end tool calling workflow
- Complete configuration documentation with example queries in `config.ini.example`

## Deployment Steps

### 1. SSH to Production Server
```bash
ssh brian@10.100.10.49
```

### 2. Navigate to Bot Directory
```bash
cd /opt/meshcore-bot
```

### 3. Pull Latest Changes
```bash
git fetch origin
git checkout ralph/llm-tools-integration
git pull
```

### 4. Install Dependencies (if needed)
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Update Configuration

Edit `/opt/meshcore-bot/config.ini` and add/update these settings in the `[LLM_Command]` section:

```ini
[LLM_Command]
# Enable tool calling (allows LLM to invoke bot commands)
enable_tools = true

# Maximum number of tools to call per query (prevents abuse)
max_tools_per_query = 3

# Timeout for tool execution in seconds
tool_timeout = 10

# Available tools (comma-separated whitelist)
available_tools = wx,airplanes,satpass,path,stats,moon,sun,aurora

# Include user mention in responses ([@username] prefix)
include_user_mention = true

# Track all command interactions for context (not just !ask)
track_all_commands = true
```

### 6. Restart Bot Service

**IMPORTANT:** The database migration `_m0014_extend_llm_context_for_commands` will run automatically on startup.

```bash
sudo systemctl restart meshcore-bot
```

### 7. Verify Migration Success

Check the logs to confirm migration applied successfully:

```bash
journalctl -u meshcore-bot -f
```

Look for log entries indicating:
- Migration `_m0014_extend_llm_context_for_commands` applied
- Bot started successfully
- No errors during initialization

### 8. Manual Testing on #beeboopbot Channel

Test these natural language queries to verify tool calling works:

#### Weather Queries
```
"What's the weather in Seattle?"
"Will it rain tomorrow in Portland?"
"Show me the 7-day forecast for San Francisco"
```
**Expected:** Bot calls `wx_command` with location parameter

#### Aircraft Tracking
```
"Any planes overhead?"
"Show me nearby aircraft within 50nm"
```
**Expected:** Bot calls `airplanes_command` with optional radius

#### Satellite Passes
```
"When does ISS pass over?"
"Show me Hubble passes"
"When can I see satellites tonight?"
```
**Expected:** Bot calls `satpass_command` with optional satellite parameter

#### Network Path Analysis
```
"Show path to node !abc123"
"Analyze mesh path to !def456"
```
**Expected:** Bot calls `path_command` with destination parameter

#### Multi-Tool Queries
```
"What's the weather and when does ISS pass over?"
"Show me weather and nearby aircraft"
```
**Expected:** Bot calls multiple tools sequentially

## Verification Checklist

After deployment, verify these acceptance criteria:

- [ ] Migration `_m0014` applied successfully (check logs)
- [ ] Bot responds to natural language weather queries
- [ ] Bot responds to natural language airplane queries
- [ ] Bot responds to satellite pass queries
- [ ] User mentions appear in channel responses (`[@username]` prefix)
- [ ] User mentions are skipped in DM responses
- [ ] Command context is stored in database for `!wx`, `!airplanes`, etc.
- [ ] Multi-tool queries work (e.g., "weather and satellite passes")
- [ ] Tool calling respects `max_tools_per_query` limit
- [ ] Tool execution timeout works (10 seconds default)
- [ ] Invalid tool calls are handled gracefully

## Database Schema Changes

Migration `_m0014_extend_llm_context_for_commands` modifies the `llm_conversation_context` table:

**Before:**
```sql
CREATE TABLE llm_conversation_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL
)
```

**After:**
```sql
CREATE TABLE llm_conversation_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_key TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    command_name TEXT NULL,        -- NEW: Tracks which command was executed
    sender_name TEXT NULL           -- NEW: Supports user mentions
)
```

## Configuration Reference

### Tool Calling Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_tools` | `false` | Enable LLM tool calling feature |
| `max_tools_per_query` | `3` | Maximum tools per query (prevents abuse) |
| `tool_timeout` | `10` | Timeout for tool execution (seconds) |
| `available_tools` | `wx,airplanes,satpass,path,stats,moon,sun,aurora` | Comma-separated whitelist |
| `include_user_mention` | `true` | Add `[@username]` prefix to responses |
| `track_all_commands` | `true` | Track all command context (not just !ask) |

### Available Tools Whitelist

The following commands are approved for LLM tool calling:
- `wx` - Weather conditions and forecast
- `airplanes` - Aircraft tracking (ADS-B data)
- `satpass` - Satellite pass predictions
- `path` - Mesh network path analysis
- `stats` - Bot statistics
- `moon` - Moon phase information
- `sun` - Sunrise/sunset times
- `aurora` - Aurora forecast

## Rollback Plan

If issues occur, rollback to previous version:

```bash
cd /opt/meshcore-bot
git checkout main  # or previous stable branch
sudo systemctl restart meshcore-bot
```

**Note:** The database migration cannot be automatically rolled back. If rollback is needed, the new columns (`command_name`, `sender_name`) will remain in the database but will be unused.

## Support and Troubleshooting

### Common Issues

**Issue:** Migration fails to apply
- Check database permissions (`llm_context.db` file)
- Review migration logs in `journalctl -u meshcore-bot`

**Issue:** Tool calling not working
- Verify `enable_tools = true` in config
- Check Ollama endpoint is accessible
- Verify model supports tool calling (llama3.1+ recommended)

**Issue:** Tools not being called
- Check `available_tools` whitelist includes the command
- Verify command is enabled and loaded
- Check bot logs for ToolRegistry initialization

**Issue:** User mentions not appearing
- Verify `include_user_mention = true` in config
- Check message is not a DM (mentions are skipped for DMs)

### Logs to Monitor

```bash
# Real-time bot logs
journalctl -u meshcore-bot -f

# Filter for LLM-related logs
journalctl -u meshcore-bot | grep -i "llm\|tool\|ollama"

# Check database migrations
journalctl -u meshcore-bot | grep -i "migration"
```

## Next Steps After Deployment

1. Monitor bot behavior on #beeboopbot for first few hours
2. Test all example queries from this document
3. Verify database context is being stored correctly
4. Gather user feedback on tool calling accuracy
5. Adjust `max_tools_per_query` or `tool_timeout` if needed
6. Consider expanding `available_tools` whitelist based on usage

## Technical Contacts

- **Development:** Ralph autonomous agent (completed all code)
- **Deployment:** Human administrator at brian@10.100.10.49
- **Production Server:** 10.100.10.49:/opt/meshcore-bot
- **Git Branch:** ralph/llm-tools-integration

## Additional Resources

- Full PRD: `prd.json`
- Implementation log: `progress.txt`
- Configuration examples: `config.ini.example`
- Test suite: `tests/test_llm_tool_calling.py`

---

**Deployment prepared by:** Ralph autonomous agent
**Date:** 2026-07-04
**Status:** Ready for manual deployment by human administrator
