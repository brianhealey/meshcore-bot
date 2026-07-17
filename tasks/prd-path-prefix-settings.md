# PRD: Path Prefix Bytes Settings

## Introduction

Add the ability to view and configure the path prefix bytes setting on the radio page. This setting controls how many bytes are used for node identification in mesh routing paths (1, 2, or 3 bytes). The feature includes impact analysis showing which contacts and paths would be affected by changes, helping operators understand the implications before modifying this critical routing parameter.

Currently, the bot reads `prefix_bytes` from config.ini with a fallback of 1, but there's no way to view or change the actual radio setting through the web interface. This feature will read the current value directly from the radio and allow operators to change it.

## Goals

- Display current prefix bytes setting read directly from the connected radio
- Allow operators to change the prefix bytes setting (1, 2, or 3 bytes)
- Show impact analysis: which contacts/paths would be affected by a change
- Provide clear warnings about the implications of changing this setting
- Read from and write to the radio directly (not config.ini)

## User Stories

### US-001: Read prefix bytes from radio
**Description:** As an operator, I want to see the current prefix bytes setting from my radio so I know how paths are being encoded.

**Acceptance Criteria:**
- [ ] Add API endpoint `GET /api/radio/prefix-bytes` that reads the setting from the radio
- [ ] Returns JSON with `prefix_bytes` (1, 2, or 3) and `status` (connected/disconnected)
- [ ] Returns appropriate error if radio is not connected
- [ ] Typecheck/lint passes

### US-002: Create Advanced Settings card on radio page
**Description:** As an operator, I want to see advanced radio settings in a dedicated section so I can manage path configuration separately from basic radio parameters.

**Acceptance Criteria:**
- [ ] Add "Advanced Settings" card below the Radio Parameters card
- [ ] Card has consistent styling with existing cards on the page
- [ ] Card includes a "Read from Device" button similar to Radio Parameters
- [ ] Card shows loading state while fetching settings
- [ ] Typecheck/lint passes

### US-003: Display current prefix bytes setting
**Description:** As an operator, I want to see the current prefix bytes value with a clear explanation so I understand what it means.

**Acceptance Criteria:**
- [ ] Display current value (1, 2, or 3 bytes) with label "Path Prefix Bytes"
- [ ] Show equivalent hex characters (2, 4, or 6 chars)
- [ ] Include brief explanation: "Number of bytes used to identify nodes in routing paths"
- [ ] Show "Unknown" or "N/A" state when radio is disconnected
- [ ] Typecheck/lint passes

### US-004: Add prefix bytes selector
**Description:** As an operator, I want to select a different prefix bytes value so I can change how paths are encoded on my radio.

**Acceptance Criteria:**
- [ ] Dropdown or radio button group with options: 1 byte (2 hex), 2 bytes (4 hex), 3 bytes (6 hex)
- [ ] Current radio value is pre-selected
- [ ] Selector is disabled when radio is disconnected
- [ ] Typecheck/lint passes

### US-005: Show impact analysis before change
**Description:** As an operator, I want to see how many contacts and paths would be affected by changing prefix bytes so I can make an informed decision.

**Acceptance Criteria:**
- [ ] When a different value is selected, show impact summary
- [ ] Display count of contacts with stored paths that would need re-resolution
- [ ] Display count of observed paths that use a different byte width
- [ ] Show warning icon and text explaining the impact
- [ ] Typecheck/lint passes

### US-006: Create impact analysis API endpoint
**Description:** As a developer, I need an API to calculate the impact of changing prefix bytes so the UI can display it.

**Acceptance Criteria:**
- [ ] Add API endpoint `GET /api/radio/prefix-bytes/impact?target=N` (N = 1, 2, or 3)
- [ ] Returns count of contacts with `out_bytes_per_hop` different from target
- [ ] Returns count of observed_paths with `bytes_per_hop` different from target
- [ ] Returns list of affected repeater names (limited to first 10)
- [ ] Typecheck/lint passes

### US-007: Confirmation dialog with impact summary
**Description:** As an operator, I want to confirm before changing prefix bytes so I don't accidentally disrupt my mesh routing.

**Acceptance Criteria:**
- [ ] "Write to Device" button triggers confirmation modal
- [ ] Modal shows current value and new value
- [ ] Modal displays impact summary (contacts/paths affected)
- [ ] Modal includes warning: "Changing this setting affects how nodes are identified in routing paths. Existing paths may need to be re-learned."
- [ ] Modal has "Cancel" and "Confirm Change" buttons
- [ ] Typecheck/lint passes

### US-008: Write prefix bytes to radio
**Description:** As an operator, I want to save my prefix bytes change to the radio so the new setting takes effect.

**Acceptance Criteria:**
- [ ] Add API endpoint `POST /api/radio/prefix-bytes` with body `{"prefix_bytes": N}`
- [ ] Validates input is 1, 2, or 3
- [ ] Sends command to radio via MeshCore library
- [ ] Returns success/failure status
- [ ] Shows success toast notification on completion
- [ ] Shows error toast if write fails
- [ ] Refreshes displayed value after successful write
- [ ] Typecheck/lint passes

### US-009: Update bot's runtime prefix_bytes after radio change
**Description:** As a developer, I need the bot to use the new prefix_bytes value after it's changed on the radio so path parsing is consistent.

**Acceptance Criteria:**
- [ ] After successful write to radio, update `bot.prefix_bytes` and `bot.prefix_hex_chars`
- [ ] Log the change at INFO level
- [ ] New value is used immediately for path parsing without restart
- [ ] Typecheck/lint passes

### US-010: Show prefix bytes mismatch warning
**Description:** As an operator, I want to be warned if the radio's prefix bytes doesn't match what paths are using so I know there may be routing issues.

**Acceptance Criteria:**
- [ ] If observed_paths contain entries with different bytes_per_hop than current setting, show warning badge
- [ ] Warning text: "Some stored paths use a different prefix width"
- [ ] Clicking warning shows breakdown of path counts by bytes_per_hop
- [ ] Typecheck/lint passes

## Functional Requirements

- FR-1: Add `GET /api/radio/prefix-bytes` endpoint to read current prefix bytes from radio
- FR-2: Add `POST /api/radio/prefix-bytes` endpoint to write prefix bytes to radio
- FR-3: Add `GET /api/radio/prefix-bytes/impact` endpoint to calculate change impact
- FR-4: Create "Advanced Settings" card on radio page with prefix bytes control
- FR-5: Display current prefix bytes value with explanation (1/2/3 bytes = 2/4/6 hex chars)
- FR-6: Provide selector to choose new prefix bytes value (1, 2, or 3)
- FR-7: Show impact analysis when a different value is selected
- FR-8: Display confirmation dialog with impact summary before writing changes
- FR-9: Update bot runtime `prefix_bytes` after successful radio write
- FR-10: Show warning indicator when stored paths use different prefix widths

## Non-Goals

- No automatic migration of existing paths when prefix bytes changes
- No sync with config.ini (reads/writes directly to radio)
- No automatic prefix bytes detection or recommendation
- No prefix bytes history or audit log
- No per-contact prefix bytes override

## Technical Considerations

- The MeshCore library may need to be checked for prefix bytes read/write commands
- If the library doesn't support this, we may need to use raw commands or request library updates
- The bot currently reads `prefix_bytes` from config.ini at startup; after this change, it should read from radio on connect
- Impact analysis queries should be efficient (indexed queries on bytes_per_hop columns)
- Consider caching the impact analysis results briefly to avoid repeated DB queries

## Design Considerations

- Match existing Radio Parameters card styling
- Use similar patterns: "Read from Device" button, loading states, success/error toasts
- Confirmation modal should follow Bootstrap modal patterns used elsewhere
- Impact numbers should be clearly highlighted (use warning colors for non-zero counts)
- Consider showing a small diagram or visual explaining 1 vs 2 vs 3 byte prefixes

## Success Metrics

- Operators can view current prefix bytes setting without SSH access
- Operators can change prefix bytes with full understanding of impact
- No accidental prefix bytes changes (confirmation required)
- Setting change takes effect immediately without bot restart

## Open Questions

1. Does the MeshCore library currently support reading/writing the prefix bytes setting? If not, what command format is needed?
2. Should changing prefix bytes trigger a refresh of the contact list or mesh graph?
3. Should we invalidate/clear stored paths when prefix bytes changes, or just warn about them?
4. Is there a radio-level confirmation or does the setting take effect immediately?
