import json
import os
import shutil
from datetime import datetime

import luigi
import requests

from dl_images import download_and_process_camera, get_camera_local_time

# Constants
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
OUTPUT_BASE_PATH = "./"


class FetchCamerasData(luigi.Task):
    """
    Task to fetch the cameras data from an API.
    The output is saved as a JSON file.
    """

    def output(self):
        return luigi.LocalTarget(os.path.join(OUTPUT_BASE_PATH, "cameras_data.json"))

    def run(self):
        response = requests.get(CAMERAS_URL, headers=HEADERS)
        response.raise_for_status()  # Ensure we raise an error for bad responses
        cameras_data = response.json()

        # Write camera data to a JSON file
        with self.output().open("w") as f:
            json.dump(cameras_data, f)


class DownloadImagesForCamera(luigi.Task):
    """
    Task to download images for a specific camera.
    The output is a marker file indicating completion.
    """

    camera_feature = luigi.DictParameter()

    def output(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        output_path = os.path.join(
            OUTPUT_BASE_PATH, "temp", local_time.strftime("%Y_%m_%d")
        )
        camera_path = os.path.join(output_path, source)
        marker_file = os.path.join(camera_path, "download_complete.txt")
        return luigi.LocalTarget(marker_file)

    def run(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        output_path = os.path.join(
            OUTPUT_BASE_PATH, "temp", local_time.strftime("%Y_%m_%d")
        )
        camera_path = os.path.join(output_path, source)

        # Download and process images for the camera
        download_and_process_camera(self.camera_feature["properties"])

        # Create the marker file to indicate completion
        os.makedirs(camera_path, exist_ok=True)
        with self.output().open("w") as f:
            f.write("Download complete.\n")


class ProcessImagesForCamera(luigi.Task):
    """
    Task to process images for a specific camera by applying the algorithm.
    If successful, moves images to a 'processed' folder and creates a marker file.
    """

    camera_feature = luigi.DictParameter()

    def requires(self):
        return DownloadImagesForCamera(camera_feature=self.camera_feature)

    def output(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        processed_path = os.path.join(
            OUTPUT_BASE_PATH, "processed", local_time.strftime("%Y_%m_%d"), source
        )
        marker_file = os.path.join(processed_path, "process_complete.txt")
        return luigi.LocalTarget(marker_file)

    def run(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        download_path = os.path.join(
            OUTPUT_BASE_PATH, "temp", local_time.strftime("%Y_%m_%d"), source
        )
        processed_path = os.path.join(
            OUTPUT_BASE_PATH, "processed", local_time.strftime("%Y_%m_%d"), source
        )

        # Ensure the processed directory exists
        os.makedirs(processed_path, exist_ok=True)

        # Check if download_path exists
        if not os.path.exists(download_path):
            raise FileNotFoundError(f"Download path does not exist: {download_path}")

        # Process each image in the download_path
        for image_file in os.listdir(download_path):
            image_path = os.path.join(download_path, image_file)

            # Ensure it's a file
            if not os.path.isfile(image_path):
                continue

            # Simulate applying an algorithm to the image (e.g., fire detection)
            if self.apply_algorithm(image_path):
                # Move processed images to the 'processed' directory
                shutil.move(image_path, os.path.join(processed_path, image_file))
            else:
                # In case of failure, you can skip or log the error.
                print(f"Error processing {image_file}")

        # Optionally, remove the original folder once processing is complete
        if os.path.exists(download_path) and not os.listdir(download_path):
            os.rmdir(download_path)

        # Create the marker file to indicate completion
        with self.output().open("w") as f:
            f.write("Process complete.\n")

    def apply_algorithm(self, image_path):
        """
        Simulate applying a detection algorithm on the image.
        Returns True if successful, False otherwise.
        Replace this with your actual algorithm.
        """
        # Placeholder for actual processing logic
        return True


class RunCameraWorkflow(luigi.WrapperTask):
    """
    Wrapper task to run the entire workflow for all cameras.
    """

    def requires(self):
        # First, fetch camera data
        return FetchCamerasData()

    def run(self):
        # Define a generator to yield all ProcessImagesForCamera tasks
        with self.input().open("r") as f:
            cameras = json.load(f)

        # Yield tasks for each camera
        for camera_feature in cameras["features"][:10]:
            yield ProcessImagesForCamera(camera_feature=camera_feature)


if __name__ == "__main__":
    luigi.run(["RunCameraWorkflow"])
