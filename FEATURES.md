# Feature Backlog

Features are ordered by priority. Dependencies are noted where they exist.

---

## 0. Structured Session Logging

*High priority — required foundation for feedback evals (feature 5) and any
future performance analysis.*

Capture a structured log for every session: the full conversation and all tool
calls with inputs and outputs (reasoning trace), written to `logs/` daily.

Feedback entries are written separately to `feedback/` so they can be tracked
and queried independently. Both files share a session ID and timestamp so they
can be correlated at analysis time.

**File layout**

```
logs/YYYY-MM-DD_<session_id>.json      — conversation + reasoning trace
feedback/YYYY-MM-DD_<session_id>.jsonl — one feedback entry per line
```

**Session log schema** (`logs/`)

```json
{
  "session_id": "uuid4",
  "date": "YYYY-MM-DD",
  "started_at": "ISO8601",
  "ended_at": "ISO8601",
  "outcome": "booked | declined | failed | abandoned",
  "turns": [
    {
      "turn": 1,
      "user": "what's the vibe like at Vagabond?",
      "reasoning": [
        {"tool": "get_place_details", "input": {...}, "output": "..."}
      ],
      "reply": "One imagines it to be rather convivial...",
      "sentinel": null
    }
  ]
}
```

**Feedback log schema** (`feedback/`)

```jsonl
{"session_id": "uuid4", "timestamp": "ISO8601", "turn": 1, "message": "User asked for vibe — no atmospheric data available."}
{"session_id": "uuid4", "timestamp": "ISO8601", "turn": 3, "message": "User asked for walking time — no distance tool available."}
```

**Depends on:** none — should be implemented before feature 5.

**Scenarios**

```
Given a session starts
When the user sends the first message
Then a new session log file is created in logs/ with today's date and a session ID

Given the agent calls a tool during a turn
When the turn completes
Then the tool name, input, and output are recorded in that turn's reasoning trace

Given the agent calls leave_feedback during a turn
When leave_feedback is called
Then a new line is appended to feedback/YYYY-MM-DD_<session_id>.jsonl
  with the session ID, timestamp, turn number, and message

Given a session ends (booked, declined, failed, or abandoned)
When the process exits or restarts
Then the session log is closed with an outcome and ended_at timestamp

Given multiple sessions run on the same day
When logs are written
Then each session produces separate files in logs/ and feedback/ with a shared unique session ID

Given a session log and feedback file share a session ID
When correlated by session ID and turn number
Then every feedback entry can be matched to the exact turn in the conversation log
```

---

## 1. Weather Tool

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

## 2. Review Snippets in Place Details

*Feedback source: user asked for the "vibe" of a place — factual details alone were insufficient.*

Surface review text alongside the numeric rating in `get_place_details`
so Withnail can speak to atmosphere and wine selection, not just stars.

Google Places `reviews` field added to the existing field mask.
Up to 3 snippets returned, attributed (e.g. "a recent reviewer noted…").

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

## 3. Distance and Travel Time Tool

*Feedback source: user asked for precise distance and walking time to a venue —
the agent can only report a search radius, not point-to-point distance.*

Calculate walking distance and estimated travel time between the user's current
location and a venue place ID.

Accepts user coordinates (from `get_current_location`) and a place ID.
Returns distance in metres and estimated walking time in minutes.

**Depends on:** `get_current_location` (existing tool)

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

## 4. CLI Location Override

Allow the user to pass `--location "Shoreditch, London"` to bypass IP-based
geolocation, which is unreliable on VPNs and for remote workers.

When provided, the override is used in place of `get_current_location` output.
The agent uses it as the search anchor without calling the location tool.

**Note:** also satisfies the location input requirement for feature 3
when the user's precise coordinates are not available.

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

## 5. Feedback Evals

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
