# cowboybike-strava-sync

This script will fetch Cowboy Bike trips and upload them to Strava.
If the extended details provided by the newest Cowboy firmware are present, the activity will display locations as well as power data.

## Configuration

Configuration is mostly done through environment variables. 

| Variable                              | Description                                                                                                                                 | Default                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `COWBOY_USER_EMAIL`                   | Your cowboy account email                                                                                                                   | `None`                              |
| `COWBOY_USER_PASSWORD`                | Your cowboy account password                                                                                                                | `None`                              |
| `STRAVA_CLIENT_ID`                    | Your Strava API client ID                                                                                                                   | `None`                              |
| `STRAVA_CLIENT_SECRET`                | Your Strava API client secret                                                                                                               | `None`                              |
| `STRAVA_SECRET_FILE_LOCATION`         | The location of your strava token                                                                                                           | `~/.cowboybike-strava/strava-token` |
| `STRAVA_INITIAL_SECRET_FILE_LOCATION` | The location of your source strava token (this is used for Docker+Kubernetes deployments, since the file is not easily passed at first run) | `None`                              |
| `COWBOY_SECRET_FILE_LOCATION`         | The location of your cowboy token                                                                                                           | `~/.cowboybike-strava/cowboy-token` |
| `PERSISTENCE_LOCATION`                | The directory where cache will persist                                                                                                      | `~/.cowboybike-strava/`             |
| `COWBOY_TRIPS_DAYS`                   | The number of days to fetch                                                                                                                 | `7`                                 |
| `WATTS_FILTER`                        | The maximum watt power that will be considered valid                                                                                        | `1100`                              |
| `LOG_LEVEL`                           | The logging level                                                                                                                           | `INFO`                              |

Two files are required for authentication, they will be used to store your access and refresh tokens for Strava API and Cowboy.

For Cowboy, we can fully generate it with a login to the API. If the file does not exists, it will be created and then reused for subsequent requests.

For Strava, you need to create an Application following this guide : https://developers.strava.com/docs/authentication/
Don't forget to add the `activity:write` scope to your token request. When you finish the procedure, the last reply will be a json with this format

```
{
  "token_type": "Bearer",
  "expires_at": 1636631250,
  "expires_in": 21600,
  "refresh_token": "XXX",
  "access_token": "XXX",
  "athlete": {
    "id": 44554207,
    "username": "samueldumont",
    ...
  }
}
```

Save this file at the `STRAVA_SECRET_FILE_LOCATION`. This will be refreshed if necessary and updated.