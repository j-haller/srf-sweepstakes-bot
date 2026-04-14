# SRF Sweepstakes Bot

Automatically submits tips for the [SRF EM Tippspiel](https://emtippspiel.srf.ch) sweepstakes based on betting odds. No money involved.

Originally built for the **UEFA European Championship 2024**.

## How it works

At 10 minutes before each match, the script fetches the current betting odds from [the-odds-api.com](https://the-odds-api.com) and uses them to calculate a predicted score, which it then submits to the SRF sweepstakes platform on your behalf. It sleeps between runs and stops automatically once all matches have been played.

## Setup

### Prerequisites

- Python 3.12+ or Docker

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```
cp .env.example .env
```

| Variable  | Description                                                                 |
|-----------|-----------------------------------------------------------------------------|
| `API_KEY` | API key from [the-odds-api.com](https://the-odds-api.com/#get-access)       |
| `COOKIES` | Session cookie(s) from [emtippspiel.srf.ch](https://emtippspiel.srf.ch) after logging in, comma-separated for multiple accounts |

### Running with Docker (recommended)

```bash
docker compose up --build
```

### Running directly

```bash
pip install -r requirements.txt
python srf-sweepstakes-bot.py
```

## Updating for a new tournament

The following values in `srf-sweepstakes-bot.py` need to be updated before each tournament:

- **`URL_ODDS`** — replace the sport key (`soccer_uefa_european_championship`) with the one for the new tournament. Available sport keys are listed in the [the-odds-api.com docs](https://the-odds-api.com/liveapi/guides/v4/#get-sports).
- **`COUNTRIES`** — update the name-to-German-translation dictionary to match the participating teams.
- **`AVG_GOALS`** — update with the average goals per game from the previous edition of the tournament.
- **`TOTAL_ROUNDS`** — update if the number of rounds differs.
