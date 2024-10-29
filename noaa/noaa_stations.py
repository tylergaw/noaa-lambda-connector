import json
import os

import requests


def make_noaa_station_req(headers, startdate):
    # There are 152481 stations returned from the API, will need to page this
    stations = []
    page_size = 1000
    retrieved = 0
    offset = 0
    stations_url = "https://www.ncei.noaa.gov/cdo-web/api/v2/stations"

    stations_params = {"limit": 1}
    if startdate != "":
        stations_params["startdate"] = startdate

    stations_metadata = requests.get(
        stations_url, headers=headers, params=stations_params
    )
    stations_metadata = json.loads(stations_metadata.text)
    count = stations_metadata["metadata"]["resultset"]["count"]

    print("Start retrieving stations data")
    while retrieved < count:
        stations_params["limit"] = page_size
        stations_params["offset"] = offset

        stations_response = requests.get(
            stations_url,
            headers=headers,
            params=stations_params,
        )

        if stations_response.status_code != 200:
            print(f"Error retrieving stations data: {stations_response.status_code}")
            continue

        stations_page = json.loads(stations_response.text)
        print(f"Retrieved {len(stations_page['results'])} stations")

        for station in stations_page["results"]:
            stations.append(station)

        retrieved += len(stations_page["results"])
        offset = retrieved

    print("Finished retrieving stations data")
    return stations


def lambda_handler(event, context):
    try:
        token = os.environ["NOAA_API_KEY"]
    except KeyError:
        err = "Error: NOAA_API_KEY not found in environment, can't fetch data."
        return {"error": err}
    headers = {"token": token}
    print(f"Lambda invoked with event: {event}")
    state = event["state"]

    stations_startdate = state["last_sync_run"] if "last_sync_run" in state else ""

    stations_data = make_noaa_station_req(headers, stations_startdate)

    ret = {
        "state": {},
        "insert": {
            "stations": stations_data,
        },
        # schema only needs primary keys
        "schema": {
            "stations": {"primary_key": ["id"]},
        },
        "hasMore": False,
    }
    return json.dumps(ret)


if __name__ == "__main__":
    # NOTE: Right now, this is only used for local testing, so use a limited state
    lambda_handler(
        {"state": {}},
        {},
    )
