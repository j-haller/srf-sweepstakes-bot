import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import math
import time
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["API_KEY"]
COOKIES = os.environ["COOKIES"].split(",")

URL_ODDS = f"https://api.the-odds-api.com/v4/sports/soccer_uefa_european_championship/odds?regions=eu&bookmakers=sport888&apiKey={API_KEY}"
URL_BETS = "https://emtippspiel.srf.ch/bet"
URL_ROUND = "https://emtippspiel.srf.ch/round"

TIMEZONE_OFFSET = timedelta(hours=2)
MIN_LEAD_SECONDS = 600  # don't bet within 10 minutes of kickoff
TOTAL_ROUNDS = 7
AVG_GOALS = 2.46
THRESHOLD = 0.75
THRESHOLD_ONE = 0.5

COUNTRIES = {
    "Germany": "Deutschland", "Scotland": "Schottland", "Hungary": "Ungarn",
    "Switzerland": "Schweiz", "Spain": "Spanien", "Croatia": "Kroatien",
    "Italy": "Italien", "Albania": "Albanien", "Poland": "Polen",
    "Netherlands": "Niederlande", "Slovenia": "Slowenien", "Denmark": "Dänemark",
    "Serbia": "Serbien", "England": "England", "Romania": "Rumänien",
    "Ukraine": "Ukraine", "Belgium": "Belgien", "Slovakia": "Slowakei",
    "Austria": "Österreich", "France": "Frankreich", "Turkey": "Türkei",
    "Georgia": "Georgien", "Portugal": "Portugal", "Czech Republic": "Tschechien",
}


def round_goals(goals):
    if goals < 1:
        return math.floor(goals) if goals < THRESHOLD_ONE else math.ceil(goals)
    return math.floor(goals) if goals < math.floor(goals + THRESHOLD) else math.ceil(goals)


def calculate_score(odds_home, odds_away, odds_draw):
    is_home_favorite = odds_home < odds_away

    if is_home_favorite:
        goals_home = odds_away * AVG_GOALS / odds_draw
        goals_away = odds_home / AVG_GOALS
    else:
        goals_home = odds_away / AVG_GOALS
        goals_away = odds_home * AVG_GOALS / odds_draw

    goals_home = round_goals(goals_home)
    goals_away = round_goals(goals_away)

    if is_home_favorite:
        goals_home -= 2 if goals_home - goals_away >= 3 else 1
    else:
        goals_away -= 2 if goals_away - goals_home >= 3 else 1

    return goals_home, goals_away


def fetch_odds(current_datetime):
    response = requests.get(URL_ODDS)

    if response.status_code != 200:
        print(f"Failed to retrieve the odds. Status code: {response.status_code}")
        return None, None

    print("Successfully got odds")
    matches = {}
    next_match = None

    for match in response.json():
        home_team = match["home_team"]
        away_team = match["away_team"]
        event_date = match["commence_time"]
        event_datetime = datetime.fromisoformat(event_date.rstrip("Z")) + TIMEZONE_OFFSET

        if (
            next_match is None
            and event_datetime > current_datetime
            and (event_datetime - current_datetime).total_seconds() > MIN_LEAD_SECONDS
        ):
            next_match = event_datetime

        odds_home, odds_away, odds_draw = 0, 0, 0
        for outcome in match["bookmakers"][0]["markets"][0]["outcomes"]:
            if outcome["name"] == home_team:
                odds_home = outcome["price"]
            elif outcome["name"] == away_team:
                odds_away = outcome["price"]
            else:
                odds_draw = outcome["price"]

        goals_home, goals_away = calculate_score(odds_home, odds_away, odds_draw)

        home_team = COUNTRIES[home_team]
        away_team = COUNTRIES[away_team]
        matches[f"{home_team} - {away_team} - {event_date}"] = [goals_home, goals_away]

    return matches, next_match


def place_bets(matches, current_datetime):
    for round_num in range(1, TOTAL_ROUNDS + 1):
        for cookie in COOKIES:
            headers = {
                "Content-Type": "application/json",
                "Cookie": f"betty_web_production={cookie}",
            }
            response = requests.get(f"{URL_ROUND}/{round_num}", headers=headers)

            if response.status_code != 200:
                print(f"Failed to retrieve the website. Status code: {response.status_code}")
                print(response.text)
                continue

            divs = BeautifulSoup(response.text, "lxml").find_all("div", attrs={"data-react-class": "ScoreBet"})

            if not divs:
                print("Error getting divs: Did you forget your cookie?")
                continue

            for div in divs:
                bet_prop = json.loads(div["data-react-props"])
                bet_id = bet_prop["bet"]["bet_id"]
                authenticity_token = bet_prop["authenticity_token"]
                event_date = bet_prop["bet"]["event_date"]
                deadline = datetime.fromisoformat(bet_prop["bet"]["deadline"].rstrip("Z")) + TIMEZONE_OFFSET
                home_team = bet_prop["bet"]["teams"][0]["name"]
                away_team = bet_prop["bet"]["teams"][1]["name"]
                match_key = f"{home_team} - {away_team} - {event_date}"

                if match_key not in matches or deadline <= current_datetime:
                    continue

                score = matches[match_key]
                data = json.dumps({"bet": score, "bet_id": bet_id, "authenticity_token": authenticity_token})
                response = requests.post(URL_BETS, data=data, headers=headers)

                if response.status_code == 201:
                    print(f"Successfully placed bet: {home_team}: {score[0]} - {away_team}: {score[1]}")
                else:
                    print(f"Error placing bet: {home_team}: {score[0]} - {away_team}: {score[1]}")


def main():
    while True:
        current_datetime = datetime.now().replace(microsecond=0)
        print(f"Start execution on {current_datetime}")

        matches, next_match = fetch_odds(current_datetime)

        if matches is not None:
            place_bets(matches, current_datetime)

        if next_match is None:
            print("No more matches, the script has stopped")
            break

        sleep_seconds = (next_match - current_datetime).total_seconds() - MIN_LEAD_SECONDS
        print(f"Next execution on {next_match - timedelta(minutes=10)}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
