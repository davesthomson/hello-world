#!/usr/bin/env python3
"""
ESPN College Football Play-by-Play Scraper

Scrapes play-by-play data from ESPN's internal JSON API, which solves the
problem of data not being present in the raw HTML (ESPN renders it via JS).

Usage:
    python espn_pbp_scraper.py <game_id_or_url>
    python espn_pbp_scraper.py 401752709
    python espn_pbp_scraper.py https://www.espn.com/college-football/playbyplay/_/gameId/401752709

Output:
    - Prints play-by-play to console
    - Saves CSV to espn_pbp_<gameId>.csv
"""

import sys
import re
import json
import csv
import time
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ESPN's internal JSON API - returns structured data directly, bypassing
# the JavaScript-rendered HTML page entirely.
SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/summary?event={game_id}"
)

# Fallback: the XHR endpoint that ESPN's own frontend uses.
XHR_URL = (
    "https://www.espn.com/college-football/playbyplay"
    "?gameId={game_id}&_xhr=1"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds, doubles each retry


def extract_game_id(input_str):
    """Extract numeric game ID from a URL or raw ID string."""
    # Try to find gameId in a URL
    match = re.search(r"gameId[/=](\d+)", input_str)
    if match:
        return match.group(1)
    # If it's just digits, use as-is
    if input_str.strip().isdigit():
        return input_str.strip()
    raise ValueError(
        f"Could not extract game ID from: {input_str}\n"
        f"Expected a numeric ID or ESPN URL containing gameId."
    )


def fetch_json(url):
    """Fetch JSON from a URL with retries and exponential backoff."""
    headers = {"User-Agent": USER_AGENT}
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} in {wait}s... ({e})")
                time.sleep(wait)

    raise ConnectionError(f"Failed after {MAX_RETRIES} attempts: {last_error}")


def fetch_game_data(game_id):
    """
    Fetch play-by-play data from ESPN's JSON API.

    Tries the summary endpoint first, falls back to the XHR endpoint.
    Returns the parsed JSON dict.
    """
    # Primary: summary API
    url = SUMMARY_URL.format(game_id=game_id)
    print(f"Fetching from summary API: {url}")
    try:
        data = fetch_json(url)
        if "drives" in data:
            return data
        print("  Summary API returned no drives data.")
    except Exception as e:
        print(f"  Summary API failed: {e}")

    # Fallback: XHR endpoint
    url = XHR_URL.format(game_id=game_id)
    print(f"Fetching from XHR endpoint: {url}")
    try:
        data = fetch_json(url)
        # XHR response nests content differently
        if isinstance(data, dict):
            # Navigate into content if wrapped
            content = data.get("content", data)
            if isinstance(content, dict) and "drives" in content:
                return content
            if "drives" in data:
                return data
        print("  XHR endpoint returned no drives data.")
    except Exception as e:
        print(f"  XHR endpoint failed: {e}")

    raise RuntimeError(
        f"Could not fetch play-by-play data for game {game_id} from any source."
    )


def ordinal(n):
    """Convert integer to ordinal string: 1 -> '1st', 2 -> '2nd', etc."""
    if n is None:
        return ""
    n = int(n)
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th")
    return f"{n}{suffix}"


def format_quarter(period_number):
    """Convert period number to quarter label: 1-4 -> '1','2','3','4', 5+ -> 'OT', 'OT2', etc."""
    if period_number is None:
        return ""
    p = int(period_number)
    if p <= 4:
        return str(p)
    if p == 5:
        return "OT"
    return f"OT{p - 4}"


def build_team_lookup(data):
    """
    Build a dict mapping team IDs to team abbreviations/names from the
    header.competitions.competitors data.
    """
    lookup = {}
    try:
        competitions = data.get("header", {}).get("competitions", [])
        for comp in competitions:
            for competitor in comp.get("competitors", []):
                team = competitor.get("team", {})
                team_id = str(team.get("id", ""))
                lookup[team_id] = {
                    "abbreviation": team.get("abbreviation", ""),
                    "displayName": team.get("displayName", ""),
                    "shortDisplayName": team.get("shortDisplayName", ""),
                    "location": team.get("location", ""),
                }
    except (KeyError, TypeError, IndexError):
        pass
    return lookup


def get_team_name(team_obj, team_lookup):
    """Extract team display name from a team object, with fallback to lookup."""
    if not team_obj:
        return ""
    # Direct fields on the team object
    for field in ("displayName", "shortDisplayName", "abbreviation", "location"):
        val = team_obj.get(field)
        if val:
            return val
    # Fallback: look up by ID
    team_id = str(team_obj.get("id", ""))
    if team_id in team_lookup:
        info = team_lookup[team_id]
        return info.get("displayName") or info.get("abbreviation") or ""
    return ""


def get_team_abbrev(team_obj, team_lookup):
    """Extract team abbreviation from a team object, with fallback to lookup."""
    if not team_obj:
        return ""
    abbr = team_obj.get("abbreviation")
    if abbr:
        return abbr
    team_id = str(team_obj.get("id", ""))
    if team_id in team_lookup:
        return team_lookup[team_id].get("abbreviation", "")
    return ""


def format_down_distance(play, team_lookup):
    """
    Format down & distance from play start data.
    Example output: '1st & 10 at FLA 19'
    """
    start = play.get("start", {})
    if not start:
        return ""

    down = start.get("down")
    distance = start.get("distance")
    yard_line = start.get("yardLine")

    parts = []
    if down is not None and distance is not None:
        parts.append(f"{ordinal(down)} & {distance}")

    if yard_line is not None:
        # Try to get the team abbreviation for the yard line side
        yl_team = start.get("team", {})
        team_abbr = get_team_abbrev(yl_team, team_lookup)
        if team_abbr:
            parts.append(f"at {team_abbr} {yard_line}")
        else:
            parts.append(f"at {yard_line}")

    return " ".join(parts)


def parse_plays(data):
    """
    Parse all plays from the ESPN API response.

    Returns a list of dicts, each with:
        - possession: team name with possession
        - quarter: quarter label (1, 2, 3, 4, OT, OT2, ...)
        - time: game clock (e.g. '15:00')
        - play: play description text
        - down_dist: down & distance (e.g. '1st & 10 at FLA 19')
    """
    team_lookup = build_team_lookup(data)
    drives_data = data.get("drives", {})
    all_drives = []

    # Collect drives from both 'previous' (completed) and 'current' (in-progress)
    previous = drives_data.get("previous", [])
    if isinstance(previous, list):
        all_drives.extend(previous)

    current = drives_data.get("current")
    if isinstance(current, dict):
        all_drives.append(current)

    plays_out = []
    for drive in all_drives:
        # Drive-level team (possession)
        drive_team = drive.get("team", {})
        possession = get_team_name(drive_team, team_lookup)

        plays = drive.get("plays", [])
        if not isinstance(plays, list):
            continue

        for play in plays:
            # Period / quarter
            period = play.get("period", {})
            if isinstance(period, dict):
                quarter_num = period.get("number")
            else:
                quarter_num = period
            quarter = format_quarter(quarter_num)

            # Clock / time
            clock = play.get("clock", {})
            if isinstance(clock, dict):
                time_display = clock.get("displayValue", "")
            else:
                time_display = str(clock) if clock else ""

            # Play description
            play_text = play.get("text", "")

            # Down & distance
            down_dist = format_down_distance(play, team_lookup)

            # If down_dist is empty, try shortDownDistanceText or
            # the play's type for special plays (kickoff, etc.)
            if not down_dist:
                sdd = play.get("shortDownDistanceText")
                if sdd:
                    down_dist = sdd

            plays_out.append({
                "possession": possession,
                "quarter": quarter,
                "time": time_display,
                "play": play_text,
                "down_dist": down_dist,
            })

    return plays_out


def print_plays(plays, game_id):
    """Print plays to console in a readable format."""
    print(f"\n{'='*80}")
    print(f"  ESPN Play-by-Play: Game {game_id}")
    print(f"  Total plays: {len(plays)}")
    print(f"{'='*80}\n")

    current_quarter = None
    for i, p in enumerate(plays, 1):
        # Print quarter header when it changes
        if p["quarter"] != current_quarter:
            current_quarter = p["quarter"]
            q_label = f"Quarter {current_quarter}" if current_quarter.isdigit() else current_quarter
            print(f"\n--- {q_label} ---\n")

        print(f"  [{p['time']:>5s}] {p['possession']}")
        if p["down_dist"]:
            print(f"          {p['down_dist']}")
        print(f"          {p['play']}")
        print()


def save_csv(plays, game_id):
    """Save plays to a CSV file."""
    filename = f"espn_pbp_{game_id}.csv"
    fieldnames = ["possession", "quarter", "time", "play", "down_dist"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(plays)
    print(f"Saved {len(plays)} plays to {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Scrape ESPN college football play-by-play data",
        epilog=(
            "Examples:\n"
            "  python espn_pbp_scraper.py 401752709\n"
            "  python espn_pbp_scraper.py https://www.espn.com/college-football/playbyplay/_/gameId/401752709\n"
            "  python espn_pbp_scraper.py 401752709 --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "game",
        help="ESPN game ID or full play-by-play URL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted text",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip saving CSV file",
    )
    args = parser.parse_args()

    # Extract game ID
    try:
        game_id = extract_game_id(args.game)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Game ID: {game_id}")

    # Fetch data
    try:
        data = fetch_game_data(game_id)
    except (ConnectionError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse plays
    plays = parse_plays(data)

    if not plays:
        print("No plays found in the response.", file=sys.stderr)
        print("The game may not have started yet, or the data format may have changed.")
        sys.exit(1)

    # Output
    if args.json:
        print(json.dumps(plays, indent=2, ensure_ascii=False))
    else:
        print_plays(plays, game_id)

    # Save CSV
    if not args.no_csv:
        save_csv(plays, game_id)


if __name__ == "__main__":
    main()
