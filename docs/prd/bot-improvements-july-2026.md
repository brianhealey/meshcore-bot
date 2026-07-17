# MeshCore Bot Improvements PRD
## Community Feedback - July 2026

**Document Version:** 1.0
**Date:** 2026-07-11
**Source:** #bot channel community feedback

---

## Executive Summary

This PRD captures improvement suggestions gathered from the #bot channel on July 11, 2026. The feedback highlights several areas for improvement: reducing channel noise, adding mesh connectivity metrics, improving the path command accuracy, and fixing identified bugs.

---

## 1. DM-Based Help and Tool Responses

### Problem Statement
When users ask the bot about its capabilities (e.g., `!help`, `!ask what tools do you have`), the verbose responses flood the public channel with information that's only relevant to the requesting user.

### User Feedback
> "Idea: If you ask what tools it has, it tells you to check DMs, and the rest of the conversation is in DM" — CapRock-openHop-desk🐇

> "The path response and HA Relay responses are kind of duplicative, you could have that in DM only or something" — Ave Maritza-📻

### Proposed Solution

#### 1.1 Smart Help Redirect
When `!help` is called on a public channel:
- Send a brief message: "Send !help to me in a DM." (similar to B30-Automatica's behavior)
- Alternatively, send a one-line summary on channel and full details via DM

#### 1.2 LLM Tool Queries in DM
When the LLM command receives capability/tool queries on public channels:
- Respond briefly on channel: "@user Check your DMs for details"
- Send the full response via DM to the user

#### 1.3 Configuration Options
```ini
[Help_Command]
; Behavior when help is requested on a public channel
; "redirect" = Tell user to DM, "brief" = Short response + DM details, "full" = Current behavior
public_channel_mode = redirect

[LLM_Command]
; Move verbose responses (tool lists, long explanations) to DM
verbose_response_to_dm = true
```

### Acceptance Criteria
- [ ] Help command on public channel sends redirect message
- [ ] Full help sent via DM when requested on channel
- [ ] LLM verbose responses (tool queries) sent via DM
- [ ] Configuration options to control behavior
- [ ] DM responses work for users who have DMed the bot before

---

## 2. Mesh Connectivity Health Metrics

### Problem Statement
There's no easy way to understand overall mesh connectivity health. Users want to know how well-connected the mesh is in their area.

### User Feedback
> "A stat I like: how many repeaters does it have in its contacts vs. how many it has heard in the past 48 hours" — Ave Maritza-📻

> "If we had a few bots around the mesh answering this, it'd give us an overall idea of how well connected everything is." — Ave Maritza-📻

> "Ideally everyone on the mesh would see the same amount of repeaters" — Ave Maritza-📟

> "Less connected areas would see less repeaters less often, so you'd know that area was less connected" — Ave Maritza-📟

### Proposed Solution

#### 2.1 New `!connectivity` or `!health` Command
Report mesh connectivity statistics:

```
Mesh Health (Leander):
Repeaters: 45 known / 38 heard (48h) / 29 heard (24h)
Connectivity: 84% (48h) / 64% (24h)
Avg adverts/repeater: 3.2/day
```

#### 2.2 Metrics to Track
| Metric | Description |
|--------|-------------|
| `repeaters_known` | Total repeaters in contact database |
| `repeaters_heard_48h` | Repeaters with adverts in last 48 hours |
| `repeaters_heard_24h` | Repeaters with adverts in last 24 hours |
| `connectivity_48h` | Percentage: heard_48h / known |
| `connectivity_24h` | Percentage: heard_24h / known |
| `avg_adverts_per_day` | Average advert frequency per repeater |
| `unique_paths_observed` | Number of unique routing paths seen |

#### 2.3 Optional: Comparative Data
If multiple bots report this data to a central service (MQTT/webhook), users could compare connectivity across different mesh regions.

### Database Schema Addition
```sql
-- Track repeater advertisement observations
CREATE TABLE repeater_adverts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repeater_pubkey TEXT NOT NULL,
    repeater_name TEXT,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    snr REAL,
    rssi INTEGER,
    hops INTEGER
);

CREATE INDEX idx_repeater_adverts_pubkey ON repeater_adverts(repeater_pubkey);
CREATE INDEX idx_repeater_adverts_time ON repeater_adverts(observed_at);
```

### Acceptance Criteria
- [ ] New command reports connectivity metrics
- [ ] Tracks repeater advertisement observations over time
- [ ] Calculates 24h and 48h connectivity percentages
- [ ] Configurable time windows for metrics
- [ ] Optionally publish metrics via webhook/MQTT

---

## 3. Path Command Improvements

### Problem Statement
The current path command implementation is inferior to other bots (B30-Automatica, HA Relay bots). Key issues include:
- 1-byte path hash collisions make resolution unreliable
- No multi-byte messaging awareness
- Output format less useful than competitors

### User Feedback
> "1b paths can't be evaluated well due to hash collisions." — bp Mobile Ikoka📳

> "Many nodes share the same first byte." — bp Mobile Ikoka📳

> "Most of Austin is using multibyte messaging. It's toggled under Experimental settings" — bp Mobile Ikoka📳

### Current State Analysis

**Our bot (CapRock Leander mcbot) output:**
```
@[🐉] [5h] 90e2,fe27,ebb0,a484,c0ff route: ~13.7mi, direct: ~12.3mi, https://da.gd/m2wiiY
```

**B30-Automatica output:**
```
@[🐉] [8h] 90e2,fe27,ebb0,a484,c0ff,ab2f,d1a9,d690 route: ~53.7mi, direct: ~20.7mi, https://da.gd/oyguT
```

**HA Relay output:**
```
@[🤷‍♂️NodeBody] 5h (Leander) b80e,d0a0,a300,8d1c,c0ff
@[🤷‍♂️NodeBody] 4h b80e,d0a0,2a39,a4bd
```

### Key Differences Observed
1. **B30-Automatica** shows longer paths (8 hops vs 5 hops) - possibly sees more of the path
2. **HA Relay** includes location name "(Leander)" in response
3. **HA Relay** provides multiple responses from different vantage points
4. Our bot may be truncating or not capturing full path data

### Proposed Improvements

#### 3.1 Multi-byte Path Support
- Detect and handle 2-byte and 3-byte node prefixes
- Use `bytes_per_hop` from routing metadata when available
- Warn users when 1-byte paths have high collision probability

#### 3.2 Improve Path Resolution Accuracy
- Increase `min_edge_observations` threshold for confident matches
- Weight recent observations more heavily
- Use bidirectional edge validation
- Consider multi-hop inference for missing segments

#### 3.3 Enhanced Output Format
```
@[user] [5h] (Leander→Austin) a1b2,c3d4,e5f6,g7h8,i9j0
Route: ~25.7mi | Direct: ~20.4mi | Confidence: High
Map: https://da.gd/xxxxx
```

Include:
- Geographic endpoint labels when known
- Confidence indicator (High/Medium/Low based on edge observations)
- Separate route distance vs direct distance

#### 3.4 Path Collision Warning
When 1-byte paths are detected:
```
@[user] [4h] a1,b2,c3,d4 ⚠️ 1-byte path (may have collisions)
Consider enabling multibyte messaging in Experimental settings.
```

#### 3.5 Configuration Options
```ini
[Path_Command]
; Minimum bytes per hop to attempt name resolution (0=auto, 1, 2, 3)
minimum_path_bytes = 2

; Show collision warning for 1-byte paths
show_collision_warning = true

; Include location names in output
include_location_names = true

; Confidence display mode: "symbol" (🎯📍❓), "text" (High/Med/Low), "none"
confidence_display = symbol
```

### Acceptance Criteria
- [ ] Correctly detect and parse multi-byte paths
- [ ] Improve repeater name resolution accuracy for 2-byte+ paths
- [ ] Display collision warnings for 1-byte paths
- [ ] Include geographic context when available
- [ ] Show confidence indicators
- [ ] Match or exceed B30-Automatica path length detection

---

## 4. Fun Command: !ding → "Dong!"

### Problem Statement
Users expect playful responses from bots. The `!ping` → "Pong!" pattern is established, but there's a request for a complementary command.

### User Feedback
> "Gotta add 'Dong!' @[bee-boop-bot]" — J-Horn 🐗 (after using !ding)

### Proposed Solution
Add `!ding` command that responds with "Dong!"

```python
class DingCommand(BaseCommand):
    name = "ding"
    keywords = ["ding"]
    description = "Responds with Dong!"

    async def execute(self, message: MeshMessage) -> bool:
        await self.send_response(message, "Dong!")
        return True
```

### Configuration
```ini
[Ding_Command]
enabled = true
response = Dong!
```

### Acceptance Criteria
- [ ] `!ding` command responds with "Dong!"
- [ ] Configurable response text
- [ ] Rate limited like other commands

---

## 5. Bug Fixes

### 5.1 Message Truncation (FIXED)

**Status:** ✅ Fixed and deployed 2026-07-11

**Problem:** Multi-part LLM responses were being truncated mid-word because the chunking algorithm didn't properly account for chunk indicator overhead (`[1/4]`, `[2/4]`, etc.) during initial chunk building.

**Solution:** Modified `chunk_llm_response()` in `modules/utils.py` to reserve 8 characters for chunk indicators during initial chunking, not after.

### 5.2 LLM Returning Weather Data (NEW)

**Problem:** Some `!ask` queries returned weather data instead of LLM responses.

**Evidence from logs:**
```
command: "ask are bottle nose dolphins more intelligent than humans?"
response: "This Afternoon: ☁️Slight Chance Showers And Thunderst..."
```

**Suspected Cause:**
- Tool execution may be incorrectly routing to weather tool
- Or context confusion between commands

**Investigation Needed:**
- Review tool executor routing logic
- Check if LLM is incorrectly calling weather tool
- Verify system prompt doesn't bias toward weather responses

### Acceptance Criteria
- [ ] Investigate and fix LLM weather response bug
- [ ] Add logging to track tool execution decisions
- [ ] Verify LLM responses match query intent

---

## 6. LLM Database Query Flexibility

### Problem Statement
Current LLM tools have hardcoded `LIMIT` clauses in their SQL queries, preventing the LLM from deciding appropriate limits based on the question context. For example, when asked "what are the closest repeaters", the LLM should be able to decide whether to return 5, 10, or 20 results based on the question.

### Current Issues
- `stats_command.py` has hardcoded `LIMIT 5`, `LIMIT 8`, `LIMIT 20` in various queries
- LLM cannot access raw database schema to understand available data
- No way to query repeater/contact data with custom sorting and filtering
- Tools don't expose `limit` or `order_by` parameters

### Proposed Solution

#### 6.1 New SQL Query Tool
Create a read-only SQL query tool that:
- Exposes database schema (DDL) to the LLM
- Allows SELECT queries with LLM-specified LIMIT
- Rejects write operations (INSERT/UPDATE/DELETE/DROP/ALTER)
- Caps maximum results (e.g., 1000 rows)

#### 6.2 Parameterized Limits in Existing Tools
Update existing LLM-callable commands to accept `limit` parameter:
- `stats` command: Allow LLM to specify result count
- `repeaters` command: New tool for querying contact/repeater data

#### 6.3 Schema-Aware System Prompt
Update LLM system prompt to include:
- Summary of key database tables
- Column descriptions for important fields
- Guidance that LLM should choose appropriate limits

### Key Tables for LLM Access
| Table | Purpose |
|-------|---------|
| `complete_contact_tracking` | All known nodes/repeaters with location, last_seen |
| `message_stats` | Message history with sender, channel, timestamps |
| `repeater_adverts` | Repeater advertisement observations |
| `mesh_connections` | Network graph edges with SNR/RSSI |

### Acceptance Criteria
- [ ] SQL query tool created with read-only enforcement
- [ ] Schema introspection available to LLM
- [ ] Stats command accepts `limit` parameter
- [ ] New repeaters query tool with sorting/filtering
- [ ] System prompt includes database context
- [ ] Security tests for SQL injection prevention

---

## 7. Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | 5.2 LLM Weather Bug | Medium | High - Core functionality broken |
| P1 | 6. LLM Database Query Flexibility | Medium | High - Enables smarter LLM responses |
| P1 | 3. Path Improvements | High | High - Competitive feature |
| P2 | 2. Connectivity Metrics | Medium | Medium - New valuable feature |
| P2 | 1. DM-Based Help | Low | Medium - Reduces channel noise |
| P3 | 4. Ding Command | Low | Low - Fun feature |

---

## 7. Success Metrics

- **Path Command:** Achieve parity with B30-Automatica path detection accuracy
- **Connectivity:** Users report finding the metrics useful for understanding mesh health
- **Channel Noise:** Reduction in verbose bot responses on public channels
- **LLM Bug:** Zero instances of incorrect tool routing in logs

---

## Appendix: Raw User Feedback

### Channel: #bot | Date: 2026-07-11

```
12:36 J-Horn 🐗: Gotta add "Dong!" @[bee-boop-bot]
12:43 Bee-EchoPlus: Gotta fix the truncate issue
12:55 CapRock-openHop-desk🐇: Idea: If you ask what tools it has, it tells you to check DMs, and the rest of the conversation is in DM.
12:57 Ave Maritza-📻: @[Bee-EchoPlus] a stat I like, how many repeaters does it have in its contacts vs. how many it has heard in the past 48 hours
12:59 Ave Maritza-📻: If we had a few bots around the mesh answering this, it'd give us an overall idea of how well connected everything is.
13:03 Ave Maritza-📻: Yeah, those two responses are kind of duplicative, you could have that in DM only or something.
13:57 Ave Maritza-📟: Ideally everyone on the mesh would see the same amount of repeaters
13:58 Ave Maritza-📟: Less connected areas would see less repeaters less often, so you'd know that area was less connected
14:26 bp Mobile Ikoka📳: @[Eron FUTO] most of Austin is using multibyte messaging. It's toggled under Experimental settings
14:26 bp Mobile Ikoka📳: 1b paths can't be evaluated well due to hash collisions.
14:26 bp Mobile Ikoka📳: Many nodes share the same first byte.
```
