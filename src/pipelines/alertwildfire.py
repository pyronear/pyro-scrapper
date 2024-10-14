import os
import sys

libraries_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(libraries_path)


import json
import logging  # Import the logging module
import os
import shutil
from datetime import datetime

import luigi
import requests

from libraries.dl_images import download_and_process_camera, get_camera_local_time

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
OUTPUT_BASE_PATH = "./alertwildfire_data/"

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # You can change to DEBUG if you need more detailed logs
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


class FetchCamerasData(luigi.Task):
    """
    Task to fetch the cameras data from an API.
    The output is saved as a JSON file.
    """

    def output(self):
        return luigi.LocalTarget(os.path.join(OUTPUT_BASE_PATH, "cameras_data.json"))

    def run(self):
        logging.info("Fetching cameras data from API...")
        response = requests.get(CAMERAS_URL, headers=HEADERS)
        response.raise_for_status()  # Ensure we raise an error for bad responses
        cameras_data = response.json()

        # Write camera data to a JSON file
        with self.output().open("w") as f:
            json.dump(cameras_data, f)
        logging.info(f"Camera data saved to {self.output().path}")


class DownloadImagesForCamera(luigi.Task):
    """
    Task to download images for a specific camera.
    The output is a marker file indicating completion.
    """

    camera_feature = luigi.DictParameter()

    def __init__(self, *args, **kwargs):
        super(DownloadImagesForCamera, self).__init__(*args, **kwargs)
        self.state = self.camera_feature["properties"].get("state")
        self.source = self.camera_feature["properties"].get("id").lower()
        self.local_time = get_camera_local_time(self.state)
        self.output_path = os.path.join(
            OUTPUT_BASE_PATH, "temp", self.local_time.strftime("%Y_%m_%d-%H")
        )
        self.camera_path = os.path.join(self.output_path, self.source)

    @property
    def task_family(self):
        # Dynamically define task name based on camera ID
        camera_id = self.camera_feature["properties"].get("id").lower()
        return f"Dl-cam-{camera_id}"

    def output(self):
        marker_file = os.path.join(self.camera_path, "download_complete.txt")
        return luigi.LocalTarget(marker_file)

    def run(self):
        logging.info(
            f"Downloading images for camera {self.source} (state: {self.state})..."
        )

        # Download and process images for the camera
        download_and_process_camera(self.camera_feature["properties"], self.output_path)

        # Create the marker file to indicate completion
        if os.path.exists(self.camera_path) and os.listdir(self.camera_path):
            with self.output().open("w") as f:
                f.write("Download complete.\n")
            logging.info(
                f"Download complete for camera {self.source}. Marker created at {self.output().path}"
            )
        else:
            raise RuntimeError(
                f"Le dossier {self.camera_path} est vide ou inexistant après le téléchargement."
            )


class ProcessImagesForCamera(luigi.Task):
    """
    Task to process images for a specific camera by applying the algorithm.
    If successful, moves images to a 'processed' folder and creates a marker file.
    """

    camera_feature = luigi.DictParameter()

    @property
    def task_family(self):
        # Dynamically define task name based on camera ID
        camera_id = self.camera_feature["properties"].get("id").lower()
        return f"Process-cam-{camera_id}"

    def requires(self):
        return DownloadImagesForCamera(camera_feature=self.camera_feature)

    def output(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        processed_path = os.path.join(
            OUTPUT_BASE_PATH, "processed", local_time.strftime("%Y_%m_%d-%H"), source
        )
        marker_file = os.path.join(processed_path, "process_complete.txt")
        return luigi.LocalTarget(marker_file)

    def run(self):
        state = self.camera_feature["properties"].get("state")
        source = self.camera_feature["properties"].get("id").lower()
        local_time = get_camera_local_time(state)
        download_path = os.path.join(
            OUTPUT_BASE_PATH, "temp", local_time.strftime("%Y_%m_%d-%H"), source
        )
        processed_path = os.path.join(
            OUTPUT_BASE_PATH, "processed", local_time.strftime("%Y_%m_%d-%H"), source
        )

        logging.info(f"Processing images for camera {source}...")

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
                logging.info(f"Processed and moved image: {image_file}")
            else:
                logging.error(f"Error processing {image_file}")

        # Optionally, remove the original folder once processing is complete
        if os.path.exists(download_path) and not os.listdir(download_path):
            os.rmdir(download_path)

        # Create the marker file to indicate completion
        with self.output().open("w") as f:
            f.write("Process complete.\n")
        logging.info(
            f"Processing complete for camera {source}. Marker created at {self.output().path}"
        )

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

    @property
    def task_family(self):
        # Dynamically define task name based on camera ID
        return "Cam-Workflow-" + str(datetime.now().strftime("%Y_%m_%d-%H"))

    def requires(self):
        # First, fetch camera data
        yield FetchCamerasData()
        # Define a generator to yield all ProcessImagesForCamera tasks
        cameras_file_path = os.path.join(OUTPUT_BASE_PATH, "cameras_data.json")
        if os.path.exists(cameras_file_path):
            with open(cameras_file_path) as f:
                cameras = json.load(f)

            # Yield tasks for each camera
            for camera_feature in cameras["features"][:2]:
                logging.info(
                    f"Scheduling processing for camera {camera_feature['properties'].get('id')}"
                )
                yield ProcessImagesForCamera(camera_feature=camera_feature)

    def run(self):
        print("habile")


if __name__ == "__main__":
    luigi.run(["RunCameraWorkflow"])
