import glob
import json
import logging
import multiprocessing
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytz
import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Load configurations from .env file
load_dotenv()
OUTPUT_BASE_PATH = os.getenv("OUTPUT_PATH", "AWF_scrap")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants
DURATION = "6h"  # options: 15m, 1h, 3h, 6h, 12h
CAMERAS_URL = "https://s3-us-west-2.amazonaws.com/alertwildfire-data-public/all_cameras-v2.json"
HEADERS = {
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.alertwildfire.org/",
    "Host": "s3-us-west-2.amazonaws.com",
}

STATE_TIMEZONES = {
    "AZ": "America/Phoenix",  # Arizona
    "CA": "America/Los_Angeles",  # California
    "CO": "America/Denver",  # Colorado
    "ID": "America/Boise",  # Idaho
    "MT": "America/Denver",  # Montana
    "NV": "America/Los_Angeles",  # Nevada
    "Nevada": "America/Los_Angeles",  # Alternate name for Nevada
    "OR": "America/Los_Angeles",  # Oregon
    "WA": "America/Los_Angeles",  # Washington
    # Add other states and their timezones here
}
MAX_TIME = 100


def duration_to_seconds(duration_str):
    logging.info(f"Converting duration '{duration_str}' to seconds.")
    """
    logging.info(f"Converting duration '{duration_str}' to seconds.")
    Convert a duration string to the equivalent number of seconds.
    Args:
        duration_str (str): A duration string in the format "Xh" (X hours) or "Xmn" (X minutes).
    Returns:
        int: The number of seconds equivalent to the duration string.
    Raises:
        ValueError: If the duration string format is invalid.
    """
    duration_str = duration_str.lower()
    if duration_str.endswith("h"):
        hours = int(duration_str[:-1])
        seconds = hours * 60 * 60
    elif duration_str.endswith("mn"):
        minutes = int(duration_str[:-2])
        seconds = minutes * 60
    else:
        raise ValueError("Invalid duration string format")

    logging.info(f"Duration '{duration_str}' converted to {seconds} seconds.")
    return seconds


def generate_chunks(response):
    """
    Splits the response content into chunks based on a specific delimiter. Each chunk represents a frame or segment.
    Args:
        response (requests.Response): The HTTP response containing the content to be split.
    Yields:
        bytes: A chunk of the response content.
    """
    logging.info("Generating image chunks from the HTTP response.")
    chunks = response.content.split(b"--frame\r\n")
    for chunk in chunks:
        if len(chunk) > 100:
            start = chunk.find(b"\xff\xd8")
            logging.debug(f"Chunk of size {len(chunk)} generated.")
            yield chunk[start:]


def get_camera_local_time(state):
    """
    Get the local time for a given state using the specified state's timezone.
    Args:
        state (str): The state for which to find the local time.
    Returns:
        datetime: The current local time for the given state.
    """
    logging.info(f"Getting local time for the state '{state}'.")
    timezone_str = STATE_TIMEZONES.get(state, "America/Phoenix")
    timezone = pytz.timezone(timezone_str)
    local_time = datetime.now(timezone)
    logging.info(f"Local time for the state '{state}' is {local_time}.")
    return local_time


def download_and_process_camera(cam_properties):
    """
    Download and process camera images based on the camera properties. Handles errors such as timeouts.
    Args:
        cam_properties (dict): A dictionary containing properties of a camera, including its state and ID.
    """
    try:
        state = cam_properties.get("state")
        source = cam_properties.get("id").lower()
        logging.info(f"Downloading camera images for '{source}' in state '{state}'.")

        url = f"https://ts1.alertwildfire.org/text/timelapse/?source={source}&preset={DURATION}"
        response = requests.get(url, headers=HEADERS, timeout=MAX_TIME)

        logging.info(f"Successfully downloaded images for camera '{source}' in '{state}'.")
        process_camera_images(response, state, source)
    except requests.exceptions.Timeout:
        logging.error(f"Timeout while processing camera '{source}'.")
    except Exception as e:
        logging.error(f"Error processing camera '{source}': {e}")


def download_and_process_images(cameras_features):
    """
    Download and process images for a list of cameras concurrently.
    Args:
        cameras_features (list): A list of camera features, each containing camera properties.
    """
    logging.info("Starting to download and process camera images concurrently.")
    with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor, tqdm(
        total=len(cameras_features)
    ) as pbar:
        futures = []
        for cameras_feature in cameras_features:
            futures.append(executor.submit(download_and_process_camera, cameras_feature["properties"]))
        for future in as_completed(futures):
            result = future.result()
            pbar.update(1)
            if result:
                logging.error(result)
    logging.info("Completed downloading and processing all camera images.")


def process_camera_images(response, state, source):
    """
    Process and save camera images from an HTTP response into a specified path,
    based on the camera's state and source information.
    Args:
        response (requests.Response): The HTTP response containing the camera images.
        state (str): The state of the camera.
        source (str): The camera source identifier.
    Logs:
        Error messages if any exception occurs during the processing.
    """
    local_time = get_camera_local_time(state)
    output_path = os.path.join(OUTPUT_BASE_PATH, "temp", local_time.strftime("%Y_%m_%d"))
    source_path = os.path.join(output_path, source)
    os.makedirs(source_path, exist_ok=True)
    logging.info(f"Processing camera images for '{source}' into '{source_path}'.")

    try:
        for i, chunk in enumerate(generate_chunks(response)):
            output_path = os.path.join(source_path, f"{str(i).zfill(8)}.jpg")
            with open(output_path, "wb") as f:
                f.write(chunk)
            logging.info(f"Saved chunk {i} for camera '{source}'.")

        # Sort and rename images
        sort_and_rename_images(source_path, local_time)
    except Exception as e:
        logging.error(f"Error processing images for '{source_path}': {e}")


def sort_and_rename_images(source_path, local_time):
    """
    Sort and rename images in a directory based on their timestamps relative to the local time.
    Args:
        source_path (str): The directory containing the images.
        local_time (datetime): The local time of the camera when the first image was captured.
    Logs:
        Error messages if any exception occurs during the sorting and renaming process.
    """
    logging.info(f"Sorting and renaming images in directory '{source_path}'.")
    try:
        imgs = glob.glob(os.path.join(source_path, "*"))
        imgs.sort()
        nb_imgs = len(imgs)

        if nb_imgs > 0:
            logging.info(f"Found {nb_imgs} images to rename.")
            dt = duration_to_seconds(DURATION) / nb_imgs
            local_time = local_time - timedelta(hours=duration_to_seconds(DURATION) / 3600)

            for i, file in enumerate(imgs):
                frame_time = local_time + timedelta(seconds=dt * i)
                frame_name = frame_time.strftime("%Y_%m_%dT%H_%M_%S") + ".jpg"
                new_file = os.path.join(source_path, frame_name)
                shutil.move(file, new_file)
                logging.debug(f"Renamed image {file} to {new_file}.")
    except Exception as e:
        logging.error(f"Error in sorting and renaming images in '{source_path}': {e}")


def remove_if_gray(file):
    """
    Remove an image file if it is determined to be grayscale.
    Args:
        file (str): The path to the image file.
    Logs:
        Error messages if any exception occurs. The file is removed in case of exceptions.
    """
    try:
        im = cv2.imread(file)
        h = im.shape[0]
        im_half = im[h // 2 :, :, :]
        d = np.max(im_half[:, :, 0] - im_half[:, :, 1])
        if d == 0:
            os.remove(file)
            logging.info(f"Removed grayscale image '{file}'.")
    except Exception as e:
        logging.error(f"Error processing file '{file}': {e}")
        os.remove(file)


def remove_grayscale_images():
    """
    Remove grayscale images from the temporary directory using threading.
    Logs:
        Error messages if any exception occurs during the removal process.
    """
    logging.info("Removing grayscale images.")
    try:
        temp_dir = os.path.join(OUTPUT_BASE_PATH, "temp")
        imgs = glob.glob(os.path.join(temp_dir, "**/*.jpg"), recursive=True)
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            list(tqdm(executor.map(remove_if_gray, imgs), total=len(imgs)))
    except Exception as e:
        logging.error(f"Error removing grayscale images: {e}")


def cleanup_empty_folders():
    """
    Remove empty folders within the temporary directory.
    Logs:
        Error messages if any exception occurs during the cleanup process.
    """
    logging.info("Cleaning up empty folders.")
    try:
        temp_dir = os.path.join(OUTPUT_BASE_PATH, "temp")
        scrap_folders = glob.glob(os.path.join(temp_dir, "**/*"))
        for scrap_folder in tqdm(scrap_folders, desc="Clean empty folders"):
            if not os.listdir(scrap_folder):
                shutil.rmtree(scrap_folder)
                logging.info(f"Removed empty folder '{scrap_folder}'.")
    except Exception as e:
        logging.error(f"Error cleaning up empty folders: {e}")


def merge_folders(src, dst):
    """
    Merge two folders, overwriting files in the destination folder if they already exist.
    Args:
        src (str): The path to the source folder.
        dst (str): The path to the destination folder.
    """
    logging.info(f"Merging folders from '{src}' to '{dst}'.")
    if not os.path.exists(dst):
        shutil.move(src, dst)
        logging.info(f"Moved '{src}' to '{dst}'.")
    else:
        for src_dir, dirs, files in os.walk(src):
            dst_dir = src_dir.replace(src, dst, 1)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)
            for file_ in files:
                src_file = os.path.join(src_dir, file_)
                dst_file = os.path.join(dst_dir, file_)
                if os.path.exists(dst_file):
                    os.remove(dst_file)
                shutil.move(src_file, dst_dir)
        os.rmdir(src)  # Optionally remove the source directory after merge
        logging.info(f"Merged and removed source directory '{src}'.")


def move_processed_directory():
    """
    Move processed directories from a temporary location to the final destination, merging folders as needed.
    """
    logging.info("Moving processed directories.")
    temp_dir = os.path.join(OUTPUT_BASE_PATH, "temp")
    scrap_folders = glob.glob(os.path.join(temp_dir, "**/*"))
    for folder in tqdm(scrap_folders, desc="Move processed directory"):
        merge_folders(folder, folder.replace("temp", "dl_frames"))
    logging.info("Completed moving processed directories.")


# Main Script
if __name__ == "__main__":
    logging.info("Starting the script.")

    cameras_data = {}
    my_file = Path(OUTPUT_BASE_PATH + "/cameras.json")
    if not my_file.is_file():
        os.makedirs(OUTPUT_BASE_PATH, exist_ok=True)
        logging.info(f"Fetching camera data from '{CAMERAS_URL}'.")
        response = requests.get(CAMERAS_URL, headers=HEADERS)
        cameras_data = response.json()

        out_file = open(OUTPUT_BASE_PATH + "/cameras.json", "w")
        json.dump(cameras_data, out_file)
        logging.info(f"Camera data saved to '{OUTPUT_BASE_PATH}/cameras.json'.")
    else:
        cameras_data = json.load(open(OUTPUT_BASE_PATH + "/cameras.json"))

    logging.info("Starting image download and processing.")
    download_and_process_images(cameras_data["features"])

    logging.info("Removing grayscale images.")
    remove_grayscale_images()

    logging.info("Cleaning up empty folders.")
    cleanup_empty_folders()

    logging.info("Moving processed directories to final destination.")
    move_processed_directory()

    logging.info("Script completed successfully.")
