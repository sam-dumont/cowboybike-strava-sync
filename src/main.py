import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from tcx import create_tcx
from dateutil import parser
from pathlib import Path
import dill as pickle
import shutil
import argparse

argparser = argparse.ArgumentParser()
argparser.add_argument("--activity", help="reupload specific activity")
args = argparser.parse_args()

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "NONE")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "NONE")
COWBOY_USER_EMAIL = os.getenv("COWBOY_USER_EMAIL", "NONE")
COWBOY_USER_PASSWORD = os.getenv("COWBOY_USER_PASSWORD", "NONE")
DELAY = int(os.getenv("DELAY", 30))

PERSISTENCE_LOCATION = os.getenv("PERSISTENCE_LOCATION", f"{os.path.expanduser('~')}/.cowboybike-strava")

PERSISTENCE_FILE = f"{PERSISTENCE_LOCATION}/activity-history"

STRAVA_SECRET_FILE_LOCATION = os.getenv("STRAVA_SECRET_FILE_LOCATION", f"{PERSISTENCE_LOCATION}/strava-token")
COWBOY_SECRET_FILE_LOCATION = os.getenv("COWBOY_SECRET_FILE_LOCATION", f"{PERSISTENCE_LOCATION}/cowboy-token")

STRAVA_INITIAL_SECRET_FILE_LOCATION = os.getenv("STRAVA_INITIAL_SECRET_FILE_LOCATION", None)

COWBOY_TRIPS_DAYS = int(os.getenv("COWBOY_TRIPS_DAYS", 7))


COWBOY_HEADERS = {
    "Content-Type": "application/json;charset=utf-8",
    "X-Cowboy-App-Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "Client-Type": "Android-App",
}

TCX_EXPORT_DIRECTORY = os.getenv("TCX_EXPORT_DIRECTORY", None)

UPLOAD_TO_STRAVA = os.getenv("UPLOAD_TO_STRAVA", True) in ["True", "1", True]

auth_cowboy = {}
auth_strava = {}


def login_cowboy(username, password):
    logging.debug("Logging to Cowboy API")
    headers = COWBOY_HEADERS.update({"Client": "Android-App"})
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
            "start_date_local": parser.parse(activity["started_at"]).isoformat(),
            "type": "EBikeRide",
            "elapsed_time": activity["moving_time"],
            "description": f"Average motor power: {trip['average_motor_power']}W\nAverage user power: {trip['average_user_power']}W",
            "distance": round(activity["distance"] * 1000, 3),
        },
    )
    if req.status_code == 409:
        logger.info("Activity already exists")


if __name__ == "__main__":

    Path(PERSISTENCE_LOCATION).mkdir(parents=True, exist_ok=True)

    if TCX_EXPORT_DIRECTORY is not None:
        Path(TCX_EXPORT_DIRECTORY).mkdir(parents=True, exist_ok=True)

    if (
        UPLOAD_TO_STRAVA
        and STRAVA_INITIAL_SECRET_FILE_LOCATION is not None
        and not Path(STRAVA_SECRET_FILE_LOCATION).is_file()
    ):
        shutil.copyfile(STRAVA_INITIAL_SECRET_FILE_LOCATION, STRAVA_SECRET_FILE_LOCATION)

    try:
        activity_history = pickle.load(open(PERSISTENCE_FILE, "rb"))
    except:
        activity_history = []

    try:
        with open(COWBOY_SECRET_FILE_LOCATION, "r") as infile:
            auth = json.loads(infile.read())
            if auth["Expiry"] < int(time.time()):
                raise Exception("Token expired")
            logging.debug(f"Using the existing cowboy token. User {auth['Uid']}")
            auth_cowboy = auth
    except:
        logger.debug("Would login")
        auth_cowboy = login_cowboy(COWBOY_USER_EMAIL, COWBOY_USER_PASSWORD)

    if UPLOAD_TO_STRAVA:
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

    COWBOY_HEADERS.update(
        {
            "Client": auth_cowboy["Client"],
            "Uid": auth_cowboy["Uid"],
            "Access-Token": auth_cowboy["Access-Token"],
        }
    )

    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_date = end_date - timedelta(days=COWBOY_TRIPS_DAYS)

    last_page = False
    page = 1
    trips = []

    trips_url = (
        f"https://app-api.cowboy.bike/trips/{args.activity}" if args.activity else "https://app-api.cowboy.bike/trips"
    )

    while not last_page:
        try:
            trips_history = requests.get(
                trips_url,
                json={
                    "page": page,
                    "from": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                    "to": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                headers=COWBOY_HEADERS,
            )

            trips_history.raise_for_status()
            trips_history = trips_history.json()

            last_page = args.activity or trips_history["last_page"]
            page += 1

            if args.activity:
                trips.extend([trips_history])
            else:
                for day in trips_history["daily_summaries"]:
                    trips.extend(trips_history["daily_summaries"][day]["trips"])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                auth_cowboy = login_cowboy(COWBOY_USER_EMAIL, COWBOY_USER_PASSWORD)
                COWBOY_HEADERS.update(
                    {
                        "Client": auth_cowboy["Client"],
                        "Uid": auth_cowboy["Uid"],
                        "Access-Token": auth_cowboy["Access-Token"],
                    }
                )

    for trip in trips:
        if (
            trip["uid"] not in activity_history or (args.activity and int(args.activity) == int(trip["id"]))
        ) and datetime.now(tz=timezone.utc) > parser.parse(trip["ended_at"]).astimezone(timezone.utc) + timedelta(
            minutes=DELAY
        ):
            logger.info(f"Processing trip {trip['id']}")
            if trip["has_dashboard_data"]:
                try:
                    trip_charts = requests.get(
                        f"https://app-api.cowboy.bike/trips/{trip['id']}/charts",
                        headers=COWBOY_HEADERS,
                    ).json()

                    if len(trip_charts["durations"]) <= 0.95 * trip["unlocked_time"]:
                        raise ValueError("Not the full trip data")
                    tcx = create_tcx(trip, trip_charts)
                    tcx.write(
                        f"/tmp/output_{trip['id']}.tcx",
                        pretty_print=True,
                        xml_declaration=True,
                        encoding="utf-8",
                    )
                    if TCX_EXPORT_DIRECTORY is not None:
                        try:
                            shutil.copyfile(
                                f"/tmp/output_{trip['id']}.tcx",
                                f"{TCX_EXPORT_DIRECTORY}/{trip['id']}.tcx",
                            )
                        except Exception as e:
                            logger.error(e)
                except:
                    if datetime.now(tz=timezone.utc) > parser.parse(trip["started_at"]).astimezone(
                        timezone.utc
                    ) + timedelta(days=1):
                        create_simple_activity(trip)
                    break

                if UPLOAD_TO_STRAVA:
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
                        "description": f"Average motor power: {trip['average_motor_power']}W\nAverage user power: {trip['average_user_power']}W",
                    }

                    req = requests.post(
                        "https://www.strava.com/api/v3/uploads",
                        headers={"Authorization": f"Bearer {auth_strava['access_token']}"},
                        data=payload,
                        files=files,
                    )

                os.remove(f"/tmp/output_{trip['id']}.tcx")
            elif UPLOAD_TO_STRAVA and datetime.now(tz=timezone.utc) > parser.parse(trip["started_at"]).astimezone(
                timezone.utc
            ) + timedelta(days=1):
                create_simple_activity(trip)

            if trip["uid"] not in activity_history:
                activity_history.append(trip["uid"])
        else:
            logger.info(f"Activity {trip['uid']} already processed, nothing to do")

    pickle.dump(sorted(activity_history), open(PERSISTENCE_FILE, "wb"))
