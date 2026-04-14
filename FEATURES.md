# Feature Backlog

Features are ordered by priority. Dependencies are noted where they exist.

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
