import requests
import os
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TOKEN = os.environ["PANDASCORE_TOKEN"]
PARIS = ZoneInfo("Europe/Paris")

KC_NAMES = {"Karmine Corp", "Karmine Corp Blue", "Karmine Corp GC", "Karmine Corp Blue Stars"}

PANDASCORE_TEAMS = [
    {"game": "lol",      "id": 134078, "label": "KC Academy (LEC)"},
    {"game": "valorant", "id": 130922, "label": "KC Valorant (VCT)"},
]

LIQUIPEDIA_PAGES = [
    {"wiki": "leagueoflegends", "page": "LFL/2026/Spring",                     "league": "LFL"},
    {"wiki": "leagueoflegends", "page": "Nexus_League/2026/Spring",            "league": "Div2 LoL"},
    {"wiki": "valorant",        "page": "VCT/2026/Game_Changers/EMEA/Stage_2", "league": "VCT GC"},
]


def make_vevent(uid, dtstart, summary, description):
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;TZID=Europe/Paris:{dtstart}",
        "DURATION:PT2H",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "END:VEVENT",
    ])


def fetch_pandascore_matches(game, team_id):
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


def pandascore_match_to_event(match):
    uid = f"kc-ps-{match['id']}@karmine-calendar"
    begin = match.get("begin_at")
    if not begin:
        return None
    dt = datetime.fromisoformat(begin.replace("Z", "+00:00")).astimezone(PARIS)
    dtstart = dt.strftime("%Y%m%dT%H%M%S")
    league_name = match.get("league", {}).get("name", "")
    opponents = match.get("opponents", [])
    opponent = next(
        (o["opponent"]["name"] for o in opponents if o["opponent"]["name"] not in KC_NAMES),
        "Adversaire inconnu"
    )
    summary = f"{league_name} | {opponent} vs Karmine Corp"
    description = f"{league_name}\\n{opponent} vs Karmine Corp"
    return make_vevent(uid, dtstart, summary, description)


def fetch_liquipedia(wiki, page):
    url = f"https://liquipedia.net/{wiki}/api.php"
    params = {
        "action": "parse",
        "page": page,
        "prop": "wikitext",
        "format": "json",
    }
    headers = {"User-Agent": "KCCalendar/1.0 (personal esport calendar project)"}
    time.sleep(2)
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    return r.json()


def parse_liquipedia_matches(data, league_label):
    events = []
    try:
        wikitext = data["parse"]["wikitext"]["*"]
        print(f"  [DEBUG] Extrait wikitext: {wikitext[:2000]}")
    except (KeyError, TypeError):
        print(f"  -> Impossible de lire le wikitext pour {league_label}")
        return events

    pattern = re.compile(
        r"\|\s*team1\s*=\s*([^\|\}\n]+).*?\|\s*team2\s*=\s*([^\|\}\n]+).*?\|\s*date\s*=\s*([^\|\}\n]+)",
        re.DOTALL
    )

    for m in pattern.finditer(wikitext):
        team1 = m.group(1).strip()
        team2 = m.group(2).strip()
        date_str = m.group(3).strip()

        is_kc = any(kc.lower() in team1.lower() or kc.lower() in team2.lower() for kc in KC_NAMES)
        if not is_kc:
            continue

        opponent = team2 if any(kc.lower() in team1.lower() for kc in KC_NAMES) else team1

        try:
            dt = datetime.strptime(date_str[:16], "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=PARIS)
            dtstart = dt.strftime("%Y%m%dT%H%M%S")
        except ValueError:
            continue

        uid = f"kc-lp-{league_label}-{team1}-{team2}-{date_str}@karmine-calendar".replace(" ", "-")
        summary = f"{league_label} | {opponent} vs Karmine Corp"
        description = f"{league_label}\\n{opponent} vs Karmine Corp"
        events.append(make_vevent(uid, dtstart, summary, description))

    return events


def main():
    events = []
    seen_ids = set()

    for team in PANDASCORE_TEAMS:
        print(f"PandaScore — {team['label']}...")
        matches = fetch_pandascore_matches(team["game"], team["id"])
        print(f"  -> {len(matches)} matchs trouvés")
        for match in matches:
            mid = match.get("id")
            if mid in seen_ids:
                continue
            event = pandascore_match_to_event(match)
            if event:
                events.append(event)
                seen_ids.add(mid)

    for lp in LIQUIPEDIA_PAGES:
        print(f"Liquipedia — {lp['league']}...")
        data = fetch_liquipedia(lp["wiki"], lp["page"])
        lp_events = parse_liquipedia_matches(data, lp["league"])
        print(f"  -> {len(lp_events)} matchs KC trouvés")
        events.extend(lp_events)

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
