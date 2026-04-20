import requests
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TOKEN = os.environ["PANDASCORE_TOKEN"]
PARIS = ZoneInfo("Europe/Paris")

TEAMS = [
    {"game": "lol",      "id": 134078, "label": "KC Academy (LEC)"},
    {"game": "lol",      "id": 128268, "label": "KC Blue (LFL)"},
    {"game": "lol",      "id": 136080, "label": "KC Blue Stars (Div2)"},
    {"game": "valorant", "id": 130922, "label": "KC Valorant (VCT)"},
    {"game": "valorant", "id": 132777, "label": "KC GC (Game Changers)"},
]

KC_NAMES = {"Karmine Corp", "Karmine Corp Blue", "Karmine Corp GC", "Karmine Corp Blue Stars"}

def fetch_matches(game, team_id):
    url = f"https://api.pandascore.co/{game}/matches/upcoming"
    params = {
        "token": TOKEN,
        "filter[opponent_id]": team_id,
        "per_page": 50,
        "sort": "begin_at",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

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

    opponent = next(
        (o["opponent"]["name"] for o in opponents if o["opponent"]["name"] not in KC_NAMES),
        "Adversaire inconnu"
    )

    summary     = f"{league_name} | {opponent} vs Karmine Corp"
    description = f"{league_name} {serie_name}\\n{opponent} vs Karmine Corp"

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
        print(f"Récupération des matchs pour {team['label']}...")
        matches = fetch_matches(team["game"], team["id"])
        print(f"  → {len(matches)} matchs trouvés")

        for match in matches:
            mid = match.get("id")
            if mid in seen_ids:
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

    print(f"\n{len(events)} matchs écrits dans docs/calendar.ics")

if __name__ == "__main__":
    main()
