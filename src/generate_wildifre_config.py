import csv
import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OUTPUT_BASE_PATH = os.getenv("OUTPUT_PATH", "AWF_scrap")

CAMERAS_URL = (
    "https://s3-us-west-2.amazonaws.com/alertwildfire-data-public/all_cameras-v2.json"
)

HEADERS = {
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.alertwildfire.org/",
    "Host": "s3-us-west-2.amazonaws.com",
}

# Main Script
if __name__ == "__main__":
    print("Starting the script.")

    cameras_data = {}
    my_file = Path(OUTPUT_BASE_PATH + "/cameras.json")
    if not my_file.is_file():
        os.makedirs(OUTPUT_BASE_PATH, exist_ok=True)
        print(f"Fetching camera data from '{CAMERAS_URL}'.")
        response = requests.get(CAMERAS_URL, headers=HEADERS)
        cameras_data = response.json()

        out_file = open(OUTPUT_BASE_PATH + "/cameras.json", "w")
        json.dump(cameras_data, out_file)
        print(f"Camera data saved to '{OUTPUT_BASE_PATH}/cameras.json'.")
    else:
        cameras_data = json.load(open(OUTPUT_BASE_PATH + "/cameras.json"))

    # Set the organization_id (you can change this)
    organization_id = os.getenv("ORGANIZATION_ID")
    if organization_id is None:
        raise RuntimeError("ORGANIZATION_ID is not defined")

    # CSV output file path
    csv_output_file = "cameras.csv"

    # JSON output file path
    json_output_file = "credentials.json"

    # CSV column headers
    csv_headers = [
        "organization_id",
        "name",
        "angle_of_view",
        "elevation",
        "lat",
        "lon",
        "is_trustable",
        "last_active_at",
        "created_at",
    ]

    # Prepare to write CSV data
    csv_data = []

    # Prepare to write JSON data
    json_data = {}

    # Loop through each feature (camera) in the input data
    for index, feature in enumerate(cameras_data["features"], start=1):
        properties = feature["properties"]
        geometry = feature["geometry"]

        # Extract relevant data for the CSV
        name = properties.get("name", f"cam-{index}")
        print("Processing the camera : " + name)
        angle_of_view = properties.get("fov", "0.0")
        elevation = geometry["coordinates"][2]
        lat, lon = geometry["coordinates"][1], geometry["coordinates"][0]
        is_trustable = True  # Assuming all cameras are trustable for this example
        last_active_at = properties.get("last_movement_at", datetime.now().isoformat())
        created_at = properties.get("activated_at", datetime.now().isoformat())

        # Add a row to CSV data
        csv_data.append(
            [
                organization_id,
                name,
                angle_of_view,
                elevation,
                lat,
                lon,
                is_trustable,
                last_active_at,
                created_at,
            ]
        )

        # Prepare data for JSON
        camera_id = properties.get("id", f"reolink_dev{index}")
        azimuth = properties.get("az_current", "0.0")

        json_data[camera_id.lower()] = {
            "brand": "reolink",
            "name": name,
            "type": "static",  # Always static
            "token": "",
            "azimuth": azimuth,
        }

    # Write the CSV data to file
    with open(csv_output_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(csv_headers)  # Write the CSV headers
        writer.writerows(csv_data)  # Write the CSV rows

    # Write the JSON data to file
    with open(json_output_file, mode="w") as file:
        json.dump(json_data, file, indent=4)

    print(f"CSV file saved to: {csv_output_file}")
    print(f"JSON file saved to: {json_output_file}")
