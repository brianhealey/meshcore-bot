# Product Requirements Document: LLM Tool Calling Integration

## Document Information
- **Feature Name**: LLM Tool Calling - Command Integration
- **Version**: 1.0
- **Status**: Draft
- **Author**: AI Assistant
- **Created**: 2026-07-04
- **Target Release**: Next minor version

## Executive Summary

Enable the MeshCore Bot's LLM assistant to use existing bot commands as tools, allowing natural language queries that automatically invoke commands like weather, satellite tracking, aircraft monitoring, and network path analysis.

## Problem Statement

Currently, users must know specific command syntax to access bot functionality:
- `!wx 78613` for weather
- `!airplanes` for aircraft
- `!satpass` for satellites
- `!path NodeName` for network analysis

Users cannot ask natural language questions like:
- "What planes are flying overhead?"
- "When will the ISS pass over?"
- "What's the weather in Austin?"
- "How do I reach the NodeX repeater?"

The LLM can answer general questions but cannot access real-time bot data or execute commands on behalf of users.

## Goals and Objectives

### Primary Goals
1. Enable LLM to call bot commands as tools using Ollama's function calling API
2. Provide seamless natural language interface to existing bot functionality
3. Maintain security by whitelisting safe commands
4. Keep responses within LoRa message size constraints
5. Include user mentions in all LLM responses for clarity
6. Track context for ALL bot commands to provide comprehensive conversation history

### Success Metrics
- Users can successfully query bot data using natural language
- LLM correctly selects appropriate tools for user queries
- Tool responses are properly integrated into LLM answers
- Response times remain under 30 seconds
- Message chunking works correctly with tool-enhanced responses

### Non-Goals
- Modifying existing command implementations
- Adding new commands (use existing ones only)
- Supporting commands with side effects (admin, configuration changes)
- Real-time streaming of tool outputs

## User Stories

### US-001: Weather Query via Natural Language
**As a** mesh network user
**I want to** ask "What's the weather in Austin?"
**So that** I don't need to remember `!wx` syntax

**Acceptance Criteria:**
- LLM recognizes weather-related queries
- Calls `wx_command` with extracted location
- Integrates weather data into natural language response
- Response is chunked appropriately for LoRa

### US-002: Aircraft Tracking via Natural Language
**As a** mesh network user
**I want to** ask "What planes are nearby?"
**So that** I can get aircraft info without command syntax

**Acceptance Criteria:**
- LLM calls `airplanes_command` automatically
- Parses aircraft data and formats naturally
- Handles empty results gracefully

### US-003: Satellite Pass Information
**As a** mesh network user
**I want to** ask "When is the ISS passing over?"
**So that** I can track satellite visibility

**Acceptance Criteria:**
- LLM identifies satellite queries
- Calls `satpass_command` with appropriate satellite
- Formats pass times in readable format

### US-004: Network Path Analysis
**As a** mesh network user
**I want to** ask "How can I reach the Hilltop repeater?"
**So that** I understand network routing

**Acceptance Criteria:**
- LLM extracts destination node from query
- Calls `path_command` with destination
- Explains path and signal quality naturally

### US-005: Multi-Tool Queries
**As a** mesh network user
**I want to** ask "What's the weather and are there any satellites passing?"
**So that** I can get multiple types of info at once

**Acceptance Criteria:**
- LLM can call multiple tools in sequence
- Results are combined coherently
- Total response time is reasonable
- Context size is managed

### US-006: Tool Failure Handling
**As a** mesh network user
**I want to** receive clear error messages when tools fail
**So that** I understand what went wrong

**Acceptance Criteria:**
- LLM handles tool execution errors
- Provides user-friendly error messages
- Suggests alternatives when appropriate

### US-007: Configuration Control
**As a** bot administrator
**I want to** enable/disable specific tools
**So that** I can control which commands are available

**Acceptance Criteria:**
- Config file lists available tools
- Tools can be individually enabled/disabled
- Invalid tool calls are rejected gracefully

### US-008: User Mention in Responses
**As a** mesh network user
**I want to** be mentioned when the bot responds to my message
**So that** I can easily identify responses directed at me in busy channels

**Acceptance Criteria:**
- All LLM responses include user mention prefix (e.g., "[@username] ...")
- User mention extracted from message sender information
- Mention format matches mesh network standards
- Works for both channel messages and DMs (DMs may omit mention)

### US-009: Universal Command Context Tracking
**As a** mesh network user
**I want to** have the LLM reference all my previous bot interactions
**So that** the AI can provide contextually aware responses based on my complete activity history

**Acceptance Criteria:**
- Bot stores context for ALL command interactions, not just !ask
- Previous weather queries, path analyses, satellite passes are available to LLM
- Context includes command name, user input, and bot response
- Context is scoped per channel or per user (DM)
- LLM can reference previous command outputs naturally
- Example: "What's changed since the last weather report?" should work

## Technical Requirements

### Architecture

#### Component Modifications

**1. OllamaClient Enhancement**
- Add `chat()` method using `/api/chat` endpoint
- Support tool definitions in request payload
- Parse tool call responses from LLM
- Handle multi-turn conversations with tool results

**2. Tool Registry System**
- Auto-discover available commands
- Generate OpenAI-compatible tool schemas
- Map command parameters to JSON schema
- Filter safe commands (whitelist approach)

**3. Tool Execution Engine**
- Parse tool call requests from LLM
- Create synthetic MeshMessage for context
- Execute command with proper parameters
- Capture and format command output
- Handle errors and timeouts

**4. LLMCommand Integration**
- Modify `execute()` for tool-calling loop
- Manage tool call → execution → response cycle
- Integrate tool results into context
- Handle response chunking with tool data
- Add user mention prefix to all responses

**5. LLMContextManager Enhancement**
- Extend schema to support command-type context entries
- Add `command_name` field to track which command was used
- Store user input and bot response for ALL commands
- Support filtering by role type (user/assistant/command)
- Provide unified context retrieval for LLM

**6. MessageHandler Integration**
- Hook into command execution flow
- Capture all command inputs and outputs
- Store command context via LLMContextManager
- Support per-channel and per-user context scoping

#### Tool Schema Format

```json
{
  "type": "function",
  "function": {
    "name": "wx_command",
    "description": "Get weather conditions and forecast for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "ZIP code or city name"
        },
        "forecast_type": {
          "type": "string",
          "enum": ["current", "tomorrow", "7d", "hourly"],
          "description": "Forecast type (optional)"
        }
      },
      "required": ["location"]
    }
  }
}
```

#### Conversation Flow

```
User: "What planes are overhead?"
  ↓
LLM receives: {messages: [...context, user_query], tools: [...]}
  ↓
LLM responds: {tool_calls: [{name: "airplanes_command", args: {}}]}
  ↓
Bot executes: airplanes_command()
  ↓
Bot receives: "3 aircraft: UAL123 at 35000ft..."
  ↓
LLM receives: {role: "tool", content: "3 aircraft..."}
  ↓
LLM responds: {content: "There are currently 3 planes flying overhead..."}
  ↓
Bot chunks and sends response
```

### Configuration

Add to `config.ini`:

```ini
[LLM_Command]
# Existing settings...

# Enable tool calling
enable_tools = true

# Maximum tools per query (prevent abuse)
max_tools_per_query = 3

# Tool execution timeout (seconds)
tool_timeout = 10

# Available tools (comma-separated)
available_tools = wx,airplanes,satpass,path,stats,moon,sun,aurora

# Include user mention in responses
include_user_mention = true

# Store context for all commands (not just !ask)
track_all_commands = true

# Tool-specific settings
[LLM_Tools]
# Weather command settings
wx_default_forecast = current

# Airplanes command settings
airplanes_default_radius = 50

# Path command settings
path_include_graph = true
```

### Phase 1: Safe Read-Only Tools

**Priority 1 (Core Value):**
- `wx_command` - Weather data
- `airplanes_command` - Aircraft tracking
- `satpass_command` - Satellite passes

**Priority 2 (Network Info):**
- `path_command` - Network path analysis
- `stats_command` - Bot statistics

**Priority 3 (Astronomy):**
- `moon_command` - Moon phase
- `sun_command` - Sunrise/sunset
- `aurora_command` - Aurora forecast

### Phase 2: Advanced Tools (Future)

**Read-Only Info:**
- `hfcond_command` - HF propagation
- `aqi_command` - Air quality
- `earthquake_command` - Recent earthquakes

**Excluded (Security):**
- Any admin commands
- Configuration changes
- Message sending commands
- Channel management

### Data Flow

1. **User Query** → LLMCommand.execute()
2. **Load Context** → get_context() from database (includes ALL previous commands)
3. **Extract Sender Info** → Get username/identifier for mention
4. **LLM Call with Tools** → OllamaClient.chat(tools=schemas)
5. **Parse Response** → Check for tool_calls
6. **Execute Tools** → ToolExecutor.run(tool_call)
7. **Format Results** → Prepare for LLM consumption
8. **LLM Synthesis** → OllamaClient.chat(tool_results)
9. **Add User Mention** → Prefix response with "[@username] ..."
10. **Response Chunking** → chunk_llm_response()
11. **Save Context** → add_message() for user and assistant

### Universal Command Context Flow

1. **Any Command Execution** → User triggers command (e.g., !wx, !path, !airplanes)
2. **Command Executes** → BaseCommand.execute() runs
3. **Capture Context** → MessageHandler hooks command completion
4. **Store Context** → LLMContextManager.add_command_context(context_key, command_name, user_input, bot_response)
5. **Context Available** → Next !ask query can reference this command's output
6. **Example**:
   - User: "!wx Austin" → Bot: "Austin: 72°F, Sunny"
   - User: "!ask Is it warmer than yesterday?" → LLM sees previous weather context

### Error Handling

**Tool Execution Errors:**
- Timeout after 10 seconds
- Capture exceptions and format as error message
- Return error to LLM for natural explanation
- Log all tool failures

**LLM Errors:**
- Invalid tool names → Retry with clarification
- Missing required parameters → Ask user for details
- Multiple tools timeout → Execute partial results

**Context Size Management:**
- Summarize long tool outputs before adding to context
- Limit tool output to 500 chars per tool
- Prune old tool results from context

### Security Considerations

1. **Command Whitelist**: Only explicitly allowed commands
2. **Parameter Validation**: Validate all tool parameters
3. **No Side Effects**: Tools must be read-only
4. **Rate Limiting**: Max 3 tools per query
5. **Timeout Protection**: 10-second execution limit
6. **Context Isolation**: Tool execution uses synthetic message context

### Performance Requirements

- **Tool Execution**: < 10 seconds per tool
- **LLM Response**: < 20 seconds total
- **Total Query Time**: < 30 seconds
- **Context Size**: < 4000 tokens including tool outputs
- **Memory Usage**: < 50MB additional for tool system

## Testing Requirements

### Unit Tests

1. **Tool Schema Generation**
   - Test schema generation for each command
   - Validate JSON schema format
   - Test parameter mapping

2. **Tool Execution**
   - Test each tool individually
   - Test with valid parameters
   - Test with invalid parameters
   - Test timeout handling

3. **OllamaClient Chat**
   - Test `/api/chat` endpoint calls
   - Test tool call parsing
   - Test multi-turn conversations

### Integration Tests

1. **End-to-End Tool Flow**
   - User query → tool call → response
   - Multi-tool queries
   - Tool error handling

2. **Context Management**
   - Tool results in context
   - Context pruning with tools
   - Context size limits

3. **Response Chunking**
   - Tool-enhanced responses
   - Large tool outputs
   - Multiple chunk handling

### Manual Test Cases

**Test Case 1: Simple Weather Query**
```
Input: "What's the weather in Austin?"
Expected: LLM calls wx_command("austin"), returns natural language weather
Verify: Response includes temperature, conditions, is properly chunked
```

**Test Case 2: Aircraft Query**
```
Input: "Any planes overhead?"
Expected: LLM calls airplanes_command(), lists aircraft naturally
Verify: Aircraft data is formatted, distances included
```

**Test Case 3: Multi-Tool Query**
```
Input: "What's the weather and when is the ISS passing?"
Expected: Calls wx_command() and satpass_command("ISS")
Verify: Both results integrated coherently
```

**Test Case 4: Tool Failure**
```
Input: "What's the weather in InvalidLocation?"
Expected: Tool returns error, LLM explains problem
Verify: User-friendly error message, no crash
```

## Dependencies

### External Dependencies
- Ollama server with function calling support
- Gemma4:12b model (supports tools capability)
- Existing bot commands must be functional

### Internal Dependencies
- `OllamaClient` module
- `LLMCommand` module
- `CommandManager` for command access
- All whitelisted command plugins

### New Dependencies
- None (uses existing Ollama/aiohttp)

## Implementation Plan

### Phase 1: Foundation (US-001 through US-004)

**Sprint 1: Core Infrastructure**
- Implement tool schema generator
- Enhance OllamaClient with `/api/chat` support
- Create tool execution engine
- Add basic configuration support

**Sprint 2: Initial Tools**
- Integrate wx_command as tool
- Integrate airplanes_command as tool
- Integrate satpass_command as tool
- Implement error handling

**Sprint 3: Network Tools**
- Integrate path_command as tool
- Integrate stats_command as tool
- Add context management for tool results

### Phase 2: Enhancement (US-005 through US-007)

**Sprint 4: Multi-Tool Support**
- Enable multiple tools per query
- Optimize context size management
- Add tool execution parallelization

**Sprint 5: Configuration & Polish**
- Tool enable/disable controls
- Tool-specific configuration
- Performance optimization
- Documentation

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Model doesn't call tools correctly | High | Medium | Improve prompts, test with different models |
| Tool outputs too large for LoRa | High | Medium | Implement summarization, strict length limits |
| Tool execution too slow | Medium | Medium | Parallel execution, caching, timeouts |
| Context size explodes | Medium | High | Aggressive pruning, tool output limits |
| Security: unintended command execution | High | Low | Strict whitelist, parameter validation |

## Open Questions

1. Should tool results be cached to avoid repeated executions?
2. How should we handle location context (user's location for wx/airplanes)?
3. Should we log all tool calls for analytics?
4. Do we need a separate system prompt for tool-enabled queries?
5. Should failed tool calls be retried automatically?

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ 3 tools working (wx, airplanes, satpass)
- ✅ Natural language queries work
- ✅ Responses properly chunked
- ✅ Configuration controls present
- ✅ Basic error handling

### Full Feature
- ✅ 8 tools available
- ✅ Multi-tool queries supported
- ✅ Robust error handling
- ✅ Performance under 30 seconds
- ✅ Comprehensive testing
- ✅ Documentation complete

## Documentation Requirements

1. **User Guide**: How to use natural language queries
2. **Admin Guide**: Tool configuration and management
3. **Developer Guide**: Adding new tools, tool schema format
4. **API Reference**: Tool schema documentation
5. **Examples**: Common query patterns and responses

## Future Enhancements

- Tool result caching
- Streaming tool execution results
- Tool chaining (output of one tool as input to another)
- Custom tool definitions via config
- Tool usage analytics and optimization
- Context-aware location detection
- Voice-optimized tool responses
