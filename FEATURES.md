# Feature Backlog

Features are ordered by priority. Dependencies are noted where they exist.

---

## 1. Reliable Agent Invocation via Streaming

*Motivation: `agent.invoke()` via the LangChain OpenAI-compatible shim for Gemini
reassembles streaming responses incorrectly, producing `AIMessage.content = "\n"`
when the model returns a streamed reply. This causes blank responses to be displayed
and logged with no indication of failure.*

The same three problems exist in both entry points:

**`cli.py`** — `agent.invoke()` used in `_run_single_session` for every turn.

**`streamlit_app.py`** — `_run_streaming_turn` streams tokens correctly for display,
but then calls `agent.invoke()` a second time to obtain the final `AgentState`.
This second invoke is the broken call: it re-runs the model, produces `"\n"`, and
overwrites the correctly-accumulated streamed reply. Additionally, `_extract_tool_calls`
scans the entire message history rather than the current turn only (AC5), and there
is no blank-reply guard before logging or display (AC3).

Fix both entry points:
- **CLI**: replace `agent.invoke()` with `agent.stream(stream_mode="values")`,
  extract final state from the last yielded chunk.
- **Streamlit**: remove the second `agent.invoke()` call; use the accumulated
  streamed text as the authoritative reply; reconstruct `AgentState` from the
  stream chunks directly (see also Feature 7 for full single-pass reconstruction).
- **Both**: add blank/whitespace reply guard; scope `_extract_tool_calls` to
  current-turn messages only.

---

### AC1 — Agent uses streaming to collect final state

**Given** the agent is invoked with a user message
**When** the graph runs (including any tool call cycles)
**Then** the response is collected via `agent.stream()`, consuming all chunks until
the stream is exhausted, with the final state extracted from the last chunk

---

### AC2 — Streamed reply content is complete and non-empty

**Given** the stream has been fully consumed
**When** the final `AIMessage.content` is extracted
**Then** it contains the model's full text response, not a partial artifact like `"\n"`

---

### AC3 — Empty/whitespace-only replies are detected before display and logging

**Given** the fully-consumed stream yields a final `AIMessage` with blank content
and no tool calls
**When** the reply is extracted
**Then** the agent retries or falls back to a user-facing error message — it never
prints or logs a blank reply

---

### AC4 — Failures are observable in the session log

**Given** a blank or malformed model response is detected
**When** the turn is recorded
**Then** the log captures the failure condition rather than `"\n"`

---

### AC5 — `_extract_tool_calls` is scoped to the current turn only

**Given** prior turns in the conversation involved tool calls
**When** extracting tool calls after turn N
**Then** only tool calls from turn N appear in the log — not all tool calls
accumulated in state

*Affects both `cli.py` (`_extract_tool_calls`) and `streamlit_app.py`
(`_extract_tool_calls` called on `final_state` which contains the full message
history).*

---

**Depends on:** nothing.

**Scenarios**

```
Given the user sends a message
When the agent responds without calling any tools
Then the reply is the model's complete text, not a partial streaming artifact

Given the user sends a message
When the agent calls a tool before responding
Then the final reply is the complete post-tool text response

Given the model returns a blank or whitespace-only response
When the turn completes
Then the user sees a fallback message and the log records the failure condition

Given two turns have each involved tool calls
When the second turn completes
Then the session log for turn 2 contains only turn 2's tool calls
```

---

## 2. Weather Tool

Fetch tonight's forecast so Withnail can factor conditions into venue recommendations
(outdoor vs indoor, rooftop vs basement).

Uses Open-Meteo API — free, no key required.
Accepts either a place name (`"Shoreditch, London"`) or a `"latitude,longitude"` string.
Resolves place names to coordinates internally via Open-Meteo geocoding —
the agent does not need to call `get_current_location` first.

**Tool description (as exposed to the LLM)**
> Get the weather forecast for tonight at 18:00 at a given location.
> Accepts either a place name (e.g. "Shoreditch, London") or a "latitude,longitude"
> string (e.g. "51.5233,-0.0754"). If given a place name, coordinates are resolved
> automatically via geocoding — you do not need to call get_current_location first.
> Returns temperature and a condition description suitable for venue reasoning.

**Depends on:** nothing.

**Scenarios**

```
Given the agent knows a place name but not coordinates
When get_weather is called with the place name
Then it resolves coordinates via geocoding and returns temperature and a condition description

Given the agent knows latitude and longitude
When get_weather is called with a "lat,lon" string
Then it skips geocoding and returns temperature and a condition description

Given the location string cannot be geocoded
When get_weather is called
Then it returns a clear error message

Given the Open-Meteo API is unreachable
When get_weather is called
Then it returns a clear error message and the agent proceeds without weather context

Given weather is wet or cold
When the agent recommends venues
Then it favours indoor venues and notes the weather as a reason

Given weather is clear and warm
When the agent recommends venues
Then it surfaces outdoor or rooftop options and notes the weather as a reason
```

---

## 3. Review Snippets in Place Details

*Feedback source: user asked for the "vibe" of a place — factual details alone were insufficient.*

Surface review text alongside the numeric rating in `get_place_details`
so Withnail can speak to atmosphere and wine selection, not just stars.

Google Places `reviews` field added to the existing field mask.
Up to 3 snippets returned, attributed (e.g. "a recent reviewer noted…").

**Depends on:** nothing.

**Scenarios**

```
Given a place has user reviews in the API response
When get_place_details is called
Then the result includes up to three review snippets

Given a place has no reviews in the API response
When get_place_details is called
Then the result is returned without a reviews section and no error is raised

Given reviews are present
When the agent recommends a venue
Then it references review content to describe atmosphere or wine selection
```

---

## 4. Distance and Travel Time Tool

*Feedback source: user asked for precise distance and walking time to a venue —
the agent can only report a search radius, not point-to-point distance.*

Calculate walking distance and estimated travel time between the user's current
location and a venue place ID.

Accepts user coordinates (from `get_current_location`) and a place ID.
Returns distance in metres and estimated walking time in minutes.

**Depends on:** `get_current_location` (existing tool). Feature 5 (CLI location
override) satisfies the coordinates requirement when GPS is unavailable.

**Scenarios**

```
Given the agent has the user's coordinates and a venue place ID
When get_travel_time is called
Then it returns the walking distance in metres and estimated time in minutes

Given the place ID is invalid or the venue cannot be resolved
When get_travel_time is called
Then it returns a clear error message

Given travel time is available
When the agent presents venue options
Then it includes walking time alongside address and rating
```

---

## 5. CLI Location Override

Allow the user to pass `--location "Shoreditch, London"` to bypass IP-based
geolocation, which is unreliable on VPNs and for remote workers.

When provided, the override is used in place of `get_current_location` output.
The agent uses it as the search anchor without calling the location tool.

**Depends on:** nothing. Also satisfies the coordinates input requirement for
Feature 4 when the user's precise GPS coordinates are not available.

**Scenarios**

```
Given the user starts the CLI with --location "Shoreditch, London"
When the agent searches for venues
Then it uses Shoreditch as the location without calling get_current_location

Given no --location flag is provided
When the agent needs a location
Then it calls get_current_location as normal

Given --location is provided with an unrecognisable string
When the agent attempts to search
Then it reports the issue to the user and falls back to get_current_location
```

---

## 6. Feedback Evals

*Motivation: the agent silently failed to call `leave_feedback` when it couldn't
answer a question about venue pricing — a capability gap went unrecorded.
Evals ensure the feedback instruction is followed consistently.*

A suite of offline evaluations that replay known capability-gap scenarios and
assert `leave_feedback` was called with a relevant message.
Evals run against a stubbed agent (no live API calls) using recorded prompts
drawn from real log entries and synthetic gap cases.

**Depends on:** existing `leave_feedback` tool and feedback log mechanism.

**Eval cases to cover**

| Trigger | Expected behaviour |
|---|---|
| User asks for venue pricing | `leave_feedback` called immediately |
| User asks for walking distance/time | `leave_feedback` called immediately |
| User asks for venue "vibe" with no reviews available | `leave_feedback` called immediately |
| Tool raises an unrecoverable error | `leave_feedback` called before responding |
| User asks an out-of-scope question | `leave_feedback` NOT called (declined, not a gap) |
| Agent successfully answers a question | `leave_feedback` NOT called |

**Scenarios**

```
Given a capability gap is encountered on the first turn
When the agent responds
Then leave_feedback is called in the same turn before the user reply

Given the agent cannot answer a question about a suggested venue
When the agent responds
Then leave_feedback is called with a description of what was asked and what was missing

Given the user asks an out-of-scope question
When the agent declines
Then leave_feedback is not called

Given the agent successfully completes a request
When the agent responds
Then leave_feedback is not called
```

---

## 7. Single-Pass Streaming State Reconstruction

*Motivation: the Streamlit UI currently calls `agent.stream()` to display tokens
then immediately calls `agent.invoke()` again to obtain the final `AgentState`
(updated `preferences`, `confirmed_place_id`, `booked`, tool call records).
This doubles the LLM cost and latency per turn.*

Replace the double-call pattern in `_run_streaming_turn` with state
reconstruction from the stream itself, eliminating the second `invoke`.

### Approach

LangGraph's `stream(stream_mode="messages")` yields `(chunk, metadata)` pairs.
The metadata dict contains node name and run info; the chunks include
`AIMessageChunk` (text tokens and tool call chunks) and `ToolMessage` objects
(tool outputs). Full state can be reconstructed by accumulating these:

1. **Collect all chunks** during the existing stream loop — already partially
   done for tool call detection and token display.
2. **Reconstruct the message list** in order:
   - `AIMessageChunk` objects can be concatenated via `+` into a single
     `AIMessage` (LangChain supports this natively).
   - `ToolMessage` objects arrive as full messages between LLM turns.
3. **Detect `booked` and updated preferences** by running a lightweight
   post-stream pass over the reconstructed messages using the same logic
   already in `AgentState` — no LLM call needed.
4. **Replace `agent.invoke(ss.agent_state)`** with the reconstructed state dict
   built from stream chunks.

### State fields to reconstruct

| Field | Source |
|---|---|
| `messages` | Accumulated from stream chunks in order |
| `preferences` | Carry forward from previous state; update from state update chunks if available via `stream_mode=["messages", "updates"]` |
| `confirmed_place_id` | Same carry-forward strategy |
| `booked` | Check last `AIMessage` content for booking sentinel or `booked=True` in any state update chunk |
| tool call records | Built from paired `AIMessageChunk.tool_call_chunks` + `ToolMessage` outputs |

### Fallback

If chunk accumulation fails to produce a coherent state (e.g. unexpected chunk
shape from a new model version), fall back to `agent.invoke()` and log a
warning. This ensures the UI never breaks silently.

**Depends on:** Feature 1 (reliable streaming — the second `invoke()` must first be removed before single-pass reconstruction can replace it).

**Scenarios**

```
Given the agent responds with a text reply and no tool calls
When the stream completes
Then the final agent_state is reconstructed from stream chunks without a second invoke

Given the agent calls one or more tools during a turn
When the stream completes
Then tool call records are built from stream chunks and match what invoke would have returned

Given the agent sets booked=True during the turn
When the stream completes
Then the reconstructed state has booked=True and the success card is shown

Given chunk accumulation produces an unexpected shape
When the stream completes
Then the code falls back to agent.invoke() and the turn completes correctly
```
