import json
import os
from datetime import datetime, timedelta

import requests


def make_noaa_data_req(headers, startdate) -> tuple[list, str]:
    ## Data types requested:
    # TMAX: Maximum temperature
    # TMIN: Minimum temperature
    # WT16: Rain (may include freezing rain, drizzle, and freezing drizzle)
    # WSFG: Peak gust wind speed
    # WDFG: Direction of peak wind gust
    # TPCP: Total precipitation

    data = []
    retries = 10
    page_size = 1000
    retrieved = 0
    offset = 0
    data_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

    startdate_dt = datetime.fromisoformat(startdate)
    if startdate_dt.date() == datetime.now().date():
        startdate_dt = datetime.now().date() - timedelta(days=2)
        startdate = startdate_dt.isoformat() + "T00:00:00"
    enddate_dt = startdate_dt + timedelta(days=1)
    enddate = enddate_dt.isoformat() + "T00:00:00"

    # Retrieve 1 day of data at a time

    data_params = {
        "startdate": startdate,
        "enddate": enddate,
        "datatypeid": ["TMAX", "TMIN", "WT16", "WSFG", "WDFG", "TPCP"],
        "limit": 1,
        "datasetid": "GHCND",
        "units": "standard",  # 🇺🇸
    }

    data_metadata = requests.get(data_url, headers=headers, params=data_params)
    while data_metadata.status_code != 200 and retries > 0:
        retries -= 1
        data_metadata = requests.get(data_url, headers=headers, params=data_params)
    if data_metadata.status_code != 200:
        raise Exception(f"Error retrieving data metadata: {data_metadata.status_code}")

    data_metadata = json.loads(data_metadata.text)
    count = data_metadata["metadata"]["resultset"]["count"]

    print("Start retrieving data")
    while retrieved < count:
        data_params["limit"] = page_size
        data_params["offset"] = offset
        data_params["include_metadata"] = "false"

        data_response = requests.get(
            data_url,
            headers=headers,
            params=data_params,
        )

        if data_response.status_code != 200:
            print(f"Error retrieving data: {data_response.status_code}")
            continue

        data_page = json.loads(data_response.text)
        print(f"Retrieved {len(data_page['results'])} data")

        for page in data_page["results"]:
            data.append(page)

        retrieved += len(data_page["results"])
        offset = retrieved
        if retrieved == count:
            enddate = startdate
            enddate_dt = datetime.fromisoformat(enddate)
            startdate = enddate_dt - timedelta(days=3650)
            startdate = startdate.isoformat()

    print("Finished retrieving data")

    ### Use these to explore the data types available in the API
    # data_types_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/datatypes"
    # types_params = {"limit": 1000}
    # types_params_offset = {"limit": 1000, "offset": 1000}
    # data_types_response = requests.get(
    #     data_types_url, headers=headers, params=types_params
    # )
    # data_types_response_offset = requests.get(
    #     data_types_url, headers=headers, params=types_params_offset
    # )
    # data_types = json.loads(data_types_response.text)
    # data_types_offset = json.loads(data_types_response_offset.text)
    # data_types_pretty = json.dumps(data_types, indent=4)
    # data_types_pretty_offset = json.dumps(data_types_offset, indent=4)
    # print(data_types_pretty)
    # print(data_types_pretty_offset)

    return data, enddate


def lambda_handler(event, context):
    try:
        token = os.environ["NOAA_API_KEY"]
    except KeyError:
        err = "Error: NOAA_API_KEY not found in environment, can't fetch data."
        return {"error": err}
    headers = {"token": token}
    print(f"Lambda invoked with event: {event}")
    state = event["state"]
    data_startdate = (
        state["last_day_retrieved"]
        if "last_day_retrieved" in state
        else "2014-01-01T00:00:00"
    )
    last_date_retrievable = (datetime.now() - timedelta(days=1)).isoformat()

    noaa_data, enddate = make_noaa_data_req(headers, data_startdate)

    # Fix this to not include time, just look at the date
    if last_date_retrievable.split("T")[0] == enddate.split("T")[0]:
        hasMore = False
    else:
        hasMore = True

    ret = {
        "state": {"last_day_retrieved": enddate},
        "insert": {
            "noaa_data": noaa_data,
        },
        # schema only needs primary keys
        "schema": {
            "noaa_data": {"primary_key": ["date", "datatype", "station", "attributes"]},
        },
        "hasMore": hasMore,
    }
    return json.dumps(ret)


if __name__ == "__main__":
    # NOTE: Right now, this is only used for local testing, so use a limited state
    lambda_handler(
        {
            "state": {
                "last_day_retrieved": "2024-10-28T00:00:00",
            }
        },
        {},
    )
