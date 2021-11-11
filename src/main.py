import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta
from tcx import create_tcx
from dateutil import parser
from pathlib import Path
import dill as pickle
import shutil

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "NONE")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "NONE")
COWBOY_USER_EMAIL = os.getenv("COWBOY_USER_EMAIL", "NONE")
COWBOY_USER_PASSWORD = os.getenv("COWBOY_USER_PASSWORD", "NONE")

PERSISTENCE_LOCATION = os.getenv(
    "PERSISTENCE_LOCATION", f"{os.path.expanduser('~')}/.cowboybike-strava"
)

PERSISTENCE_FILE = f"{PERSISTENCE_LOCATION}/activity-history"

STRAVA_SECRET_FILE_LOCATION = os.getenv(
    "STRAVA_SECRET_FILE_LOCATION", f"{PERSISTENCE_LOCATION}/strava-token"
)
COWBOY_SECRET_FILE_LOCATION = os.getenv(
    "COWBOY_SECRET_FILE_LOCATION", f"{PERSISTENCE_LOCATION}/cowboy-token"
)

STRAVA_INITIAL_SECRET_FILE_LOCATION = os.getenv(
    "STRAVA_INITIAL_SECRET_FILE_LOCATION", None
)

COWBOY_TRIPS_DAYS = int(os.getenv("COWBOY_TRIPS_DAYS", 7))


BASE_HEADERS = {
    "Content-Type": "application/json;charset=utf-8",
    "X-Cowboy-App-Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "Client-Type": "Android-App",
}

auth_cowboy = {}
auth_strava = {}


def login_cowboy(username, password):
    logging.debug("Logging to Cowboy API")
    headers = BASE_HEADERS.update({"Client": "Android-App"})
    resp = requests.post(
        url="https://app-api.cowboy.bike/auth/sign_in",
        json={"email": username, "password": password},
        headers=headers,
    )
    logging.debug(f"Response {resp.status_code}")
    auth = {
        "Uid": resp.headers["Uid"],
        "Access-Token": resp.headers["Access-Token"],
        "Client": resp.headers["Client"],
        "Expiry": int(resp.headers["Expiry"]),
    }
    with open(COWBOY_SECRET_FILE_LOCATION, "w+") as outfile:
        json.dump(auth, outfile)
    return auth


def login_strava(refresh_token, client_id, client_secret):
    logging.debug("Login to Strava API")
    resp = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    auth = resp.json()
    logging.debug(f"Response {resp.status_code}")
    with open(STRAVA_SECRET_FILE_LOCATION, "w+") as outfile:
        json.dump(auth, outfile)
    return auth


def create_simple_activity(activity):
    logger.info("I would create a simple activity")
    req = requests.post(
        "https://www.strava.com/api/v3/activities",
        headers={"Authorization": f"Bearer {auth_strava['access_token']}"},
        json={
            "name": activity["title"],
            "start_date_local": parser.parse(
                activity["started_at"]
            ).isoformat(),
            "type": "EBikeRide",
            "elapsed_time": activity["moving_time"],
            "distance": round(activity["distance"] * 1000, 3),
        },
    )
    if req.status_code == 409:
        logger.info("Activity already exists")


if __name__ == "__main__":

    Path(PERSISTENCE_LOCATION).mkdir(parents=True, exist_ok=True)

    if (
        STRAVA_INITIAL_SECRET_FILE_LOCATION is not None
        and not Path(STRAVA_SECRET_FILE_LOCATION).is_file()
    ):
        shutil.copyfile(
            STRAVA_INITIAL_SECRET_FILE_LOCATION, STRAVA_SECRET_FILE_LOCATION
        )

    try:
        activity_history = pickle.load(open(PERSISTENCE_FILE, "rb"))
    except:
        activity_history = []

    try:
        with open(COWBOY_SECRET_FILE_LOCATION, "r") as infile:
            auth = json.loads(infile.read())
            if auth["Expiry"] < int(time.time()):
                raise Exception("Token expired")
            logging.debug(
                f"Using the existing cowboy token. User {auth['Uid']}"
            )
            auth_cowboy = auth
    except:
        logger.debug("Would login")
        auth_cowboy = login_cowboy(COWBOY_USER_EMAIL, COWBOY_USER_PASSWORD)

    try:
        with open(STRAVA_SECRET_FILE_LOCATION, "r") as infile:
            auth = json.loads(infile.read())
            if auth["expires_at"] < int(time.time()):
                auth = login_strava(
                    auth["refresh_token"],
                    STRAVA_CLIENT_ID,
                    STRAVA_CLIENT_SECRET,
                )
            else:
                logging.debug(f"Using the existing strava token.")
            auth_strava = auth
    except:
        logger.error("File does not exists, please create it first")
        exit(1)

    BASE_HEADERS.update(
        {
            "Client": auth_cowboy["Client"],
            "Uid": auth_cowboy["Uid"],
            "Access-Token": auth_cowboy["Access-Token"],
        }
    )

    end_date = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    start_date = end_date - timedelta(days=COWBOY_TRIPS_DAYS)

    last_page = False
    page = 1
    trips = []

    while not last_page:
        trips_history = requests.get(
            "https://app-api.cowboy.bike/trips",
            json={
                "page": page,
                "from": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "to": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            headers=BASE_HEADERS,
        ).json()

        last_page = trips_history["last_page"]
        page += 1

        for day in trips_history["daily_summaries"]:
            trips.extend(trips_history["daily_summaries"][day]["trips"])

    for trip in trips:
        if trip["uid"] not in activity_history:
            logger.info(f"Processing trip {trip['id']}")
            if trip["has_dashboard_data"]:
                try:
                    trip_charts = requests.get(
                        f"https://app-api.cowboy.bike/trips/{trip['id']}/charts",
                        headers=BASE_HEADERS,
                    ).json()
                    tcx = create_tcx(trip, trip_charts)
                    tcx.write(
                        f"/tmp/output_{trip['id']}.tcx",
                        pretty_print=True,
                        xml_declaration=True,
                        encoding="utf-8",
                    )
                except:
                    create_simple_activity(trip)
                    break

                files = {
                    "file": (
                        f"{trip['uid']}.tcx",
                        open(f"/tmp/output_{trip['id']}.tcx", "rb"),
                        "application-type",
                    )
                }
                payload = {
                    "activity_type": "ebikeride",
                    "name": trip["title"],
                    "data_type": "tcx",
                }

                req = requests.post(
                    "https://www.strava.com/api/v3/uploads",
                    headers={
                        "Authorization": f"Bearer {auth_strava['access_token']}"
                    },
                    data=payload,
                    files=files,
                )
            else:
                create_simple_activity(trip)

            if trip["uid"] not in activity_history:
                activity_history.append(trip["uid"])
        else:
            logger.info(
                f"Activity {trip['uid']} already processed, nothing to do"
            )

    pickle.dump(sorted(activity_history), open(PERSISTENCE_FILE, "wb"))
