import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import math
import time
import os
from dotenv import load_dotenv
from scipy.optimize import minimize
load_dotenv()

API_KEY = os.environ["API_KEY"]
COOKIES = os.environ["COOKIES"].split(",")

URL_ODDS = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds?regions=eu&bookmakers=sport888&apiKey={API_KEY}"
URL_BETS = "https://wmtippspiel.srf.ch/bet"
URL_ROUND = "https://wmtippspiel.srf.ch/round"

TIMEZONE_OFFSET = timedelta(hours=2)
MIN_LEAD_SECONDS = 600  # don't bet within 10 minutes of kickoff
TOTAL_ROUNDS = 9
PREFIX_ROUNDS = 4
RHO = -0.13  # Dixon-Coles low-score correction
MAX_GOALS = 8


COUNTRIES = {
    "Mexico": "Mexiko",
    "South Africa": "Südafrika",
    "South Korea": "Südkorea",
    "Czech Republic": "Tschechien",
    "Canada": "Kanada",
    "Bosnia & Herzegovina": "Bosnien-Herzeg.",
    "USA": "USA",
    "Paraguay": "Paraguay",
    "Qatar": "Katar",
    "Switzerland": "Schweiz",
    "Brazil": "Brasilien",
    "Morocco": "Marokko",
    "Haiti": "Haiti",
    "Scotland": "Schottland",
    "Australia": "Australien",
    "Turkey": "Türkei",
    "Germany": "Deutschland",
    "Curaçao": "Curacao",
    "Netherlands": "Niederlande",
    "Japan": "Japan",
    "Ivory Coast": "Elfenbeinküste",
    "Ecuador": "Ecuador",
    "Sweden": "Schweden",
    "Tunisia": "Tunesien",
    "Spain": "Spanien",
    "Cape Verde": "Kap Verde",
    "Belgium": "Belgien",
    "Egypt": "Ägypten",
    "Saudi Arabia": "Saudi-Arabien",
    "Uruguay": "Uruguay",
    "Iran": "Iran",
    "New Zealand": "Neuseeland",
    "France": "Frankreich",
    "Senegal": "Senegal",
    "Iraq": "Irak",
    "Norway": "Norwegen",
    "Argentina": "Argentinien",
    "Algeria": "Algerien",
    "Austria": "Österreich",
    "Jordan": "Jordanien",
    "Portugal": "Portugal",
    "DR Congo": "DR Kongo",
    "England": "England",
    "Croatia": "Kroatien",
    "Ghana": "Ghana",
    "Panama": "Panama",
    "Uzbekistan": "Usbekistan",
    "Colombia": "Kolumbien",
}


def en_to_de(english_name):
    german_name = COUNTRIES.get(english_name)
    if german_name is None:
        print(f"Failed to translate country name: {english_name}")
    return german_name


def poisson_pmf(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def compute_1x2_probs(lambda_h, lambda_a):
    p_home = p_draw = p_away = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = poisson_pmf(i, lambda_h) * poisson_pmf(j, lambda_a)
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p
    return p_home, p_draw, p_away


def fit_lambdas(p_home, p_draw, p_away):
    def objective(params):
        lh, la = params
        if lh <= 0 or la <= 0:
            return 1e6
        ph, pd, pa = compute_1x2_probs(lh, la)
        return (ph - p_home) ** 2 + (pd - p_draw) ** 2 + (pa - p_away) ** 2

    result = minimize(objective, x0=[1.5, 1.0], method="Nelder-Mead",
                      options={"xatol": 1e-6, "fatol": 1e-10})
    return result.x


def dc_tau(i, j, lambda_h, lambda_a):
    if i == 0 and j == 0:
        return 1 - lambda_h * lambda_a * RHO
    elif i == 1 and j == 0:
        return 1 + lambda_a * RHO
    elif i == 0 and j == 1:
        return 1 + lambda_h * RHO
    elif i == 1 and j == 1:
        return 1 - RHO
    return 1.0


def calculate_score(odds_home, odds_away, odds_draw):
    raw = [1 / odds_home, 1 / odds_draw, 1 / odds_away]
    total = sum(raw)
    p_home, p_draw, p_away = raw[0] / total, raw[1] / total, raw[2] / total

    lambda_h, lambda_a = fit_lambdas(p_home, p_draw, p_away)

    best_prob = -1
    best_score = (1, 1)
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = poisson_pmf(i, lambda_h) * poisson_pmf(j, lambda_a) * dc_tau(i, j, lambda_h, lambda_a)
            if p > best_prob:
                best_prob = p
                best_score = (i, j)

    return best_score


def fetch_odds():
    response = requests.get(URL_ODDS)

    if response.status_code != 200:
        print(f"Failed to retrieve the odds. Status code: {response.status_code}")
        return None

    print("Successfully got odds")
    matches = {}

    for match in response.json():
        home_team = match["home_team"]
        away_team = match["away_team"]
        event_date = match["commence_time"]

        odds_home, odds_away, odds_draw = 0, 0, 0
        for outcome in match["bookmakers"][0]["markets"][0]["outcomes"]:
            if outcome["name"] == home_team:
                odds_home = outcome["price"]
            elif outcome["name"] == away_team:
                odds_away = outcome["price"]
            else:
                odds_draw = outcome["price"]

        goals_home, goals_away = calculate_score(odds_home, odds_away, odds_draw)

        home_team = en_to_de(home_team)
        away_team = en_to_de(away_team)
        matches[f"{home_team} - {away_team} - {event_date[:10]}"] = [goals_home, goals_away]

    return matches


def place_bets(matches, current_datetime):
    next_match = None
    seen_deadlines = set()

    for round_num in range(1, TOTAL_ROUNDS + 1):
        for i, cookie in enumerate(COOKIES):
            headers = {
                "Content-Type": "application/json",
                "Cookie": f"betty_web_production={cookie}",
            }
            response = requests.get(f"{URL_ROUND}/{PREFIX_ROUNDS}{round_num}", headers=headers)

            new_cookie = response.cookies.get("betty_web_production")
            if new_cookie:
                COOKIES[i] = new_cookie

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
                deadline = datetime.fromisoformat(bet_prop["bet"]["deadline"].rstrip("Z"))
                home_team = bet_prop["bet"]["teams"][0]["name"]
                away_team = bet_prop["bet"]["teams"][1]["name"]
                match_key = f"{home_team} - {away_team} - {event_date[:10]}"

                if deadline not in seen_deadlines:
                    seen_deadlines.add(deadline)
                    if (
                        next_match is None
                        and deadline > current_datetime
                        and (deadline - current_datetime).total_seconds() > MIN_LEAD_SECONDS
                    ):
                        next_match = deadline

                if match_key not in matches or deadline <= current_datetime:
                    continue

                score = matches[match_key]
                data = json.dumps({"bet": score, "bet_id": bet_id, "authenticity_token": authenticity_token})
                response = requests.post(URL_BETS, data=data, headers=headers)

                if response.status_code == 201:
                    print(f"Successfully placed bet: {home_team}: {score[0]} - {away_team}: {score[1]}")
                else:
                    print(f"Error placing bet: {home_team}: {score[0]} - {away_team}: {score[1]}")

    return next_match


def main():
    while True:
        current_datetime = datetime.utcnow().replace(microsecond=0)
        print(f"Start execution on {current_datetime}")

        matches = fetch_odds()
        next_match = place_bets(matches or {}, current_datetime)

        if next_match is None:
            print("No more matches, the script has stopped")
            break

        sleep_seconds = (next_match - current_datetime).total_seconds() - MIN_LEAD_SECONDS
        print(f"Next execution on {next_match + TIMEZONE_OFFSET - timedelta(minutes=10)}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
