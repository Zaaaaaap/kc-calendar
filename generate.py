import requests
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TOKEN = os.environ["PANDASCORE_TOKEN"]
PARIS = ZoneInfo("Europe/Paris")

# Les équipes KC à suivre, par jeu
TEAMS = [
    {"game": "lol",      "slug": "karmine-corp"},
    {"game": "valorant", "slug": "karmine-corp"},
    {"game": "valorant", "slug": "karmine-corp-female"},
]

# Les ligues autorisées (slugs exacts de PandaScore)
ALLOWED_LEAGUES = {"lec", "lfl", "lfl-division-2", "vct-emea", "vct-game-changers-emea"}

def fetch_matches(game, team_slug):
    url = f"https://api.pandascore.co/{game}/matches/upcoming"
    params = {
        "token": TOKEN,
        "filter[opponent_id]": get_team_id(game, team_slug),
        "per_page": 50,
        "sort": "begin_at",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def get_team_id(game, team_slug):
    url = f"https://api.pandascore.co/{game}/teams"
    params = {"token": TOKEN, "search[slug]": team_slug}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return data[0]["id"]

def match_to_ics(match):
    uid = f"kc-{match['id']}@karmine-calendar"
    begin = match.get("begin_at")
    if not begin:
        return None

    dt = datetime.fromisoformat(begin.replace("Z", "+00:00")).astimezone(PARIS)
    dtstart = dt.strftime("%Y%m%dT%H%M%S")

    league_name = match.get("league", {}).get("name", "")
    serie_name  = match.get("serie", {}).get("full_name", "")
    opponents   = match.get("opponents", [])
    teams       = " vs ".join(o["opponent"]["name"] for o in opponents)
    summary     = f"KC | {teams} — {league_name}"
    description = f"{league_name} {serie_name}\\n{teams}"

    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;TZID=Europe/Paris:{dtstart}",
        f"DURATION:PT2H",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "END:VEVENT",
    ])

def main():
    events = []
    seen_ids = set()

    for team in TEAMS:
        team_id = get_team_id(team["game"], team["slug"])
        if not team_id:
            print(f"Équipe introuvable : {team['slug']}")
            continue

        url = f"https://api.pandascore.co/{team['game']}/matches/upcoming"
        params = {
            "token": TOKEN,
            "filter[opponent_id]": team_id,
            "per_page": 50,
            "sort": "begin_at",
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        matches = r.json()

        for match in matches:
            mid = match.get("id")
            if mid in seen_ids:
                continue

            league_slug = match.get("league", {}).get("slug", "")
            if not any(league_slug.startswith(allowed) for allowed in ALLOWED_LEAGUES):
                continue

            event = match_to_ics(match)
            if event:
                events.append(event)
                seen_ids.add(mid)

    ics = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KC Calendar//FR",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Karmine Corp",
        "X-WR-TIMEZONE:Europe/Paris",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        *events,
        "END:VCALENDAR",
    ])

    os.makedirs("docs", exist_ok=True)
    with open("docs/calendar.ics", "w", encoding="utf-8") as f:
        f.write(ics)

    print(f"{len(events)} matchs écrits dans docs/calendar.ics")

if __name__ == "__main__":
    main()
