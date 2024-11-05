# process_images.py

import glob
import json
import logging
import os

from dotenv import load_dotenv
from PIL import Image
from pyroengine.engine import Engine

load_dotenv()

# Configurer le logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_BASE_PATH = os.getenv("OUTPUT_PATH", "AWF_scrap")
API_URL = os.getenv("API_URL")


def main():
    images_folder = OUTPUT_BASE_PATH + "/dl_frames"

    # Vérifiez que le dossier des images existe
    if not os.path.isdir(images_folder):
        logger.error(f"Le dossier des images '{images_folder}' n'existe pas.")
        exit(1)

    image_paths = glob.glob(os.path.join(images_folder, "*/*/*.jpg"))
    if not image_paths:
        logger.warning(f"Aucune image trouvée dans le dossier '{images_folder}'.")
        exit(0)

    logger.info(f"Nombre d'images à traiter : {len(image_paths)}")

    with open("data/credentials-wildfire.json", "rb") as json_file:
        cameras_credentials = json.load(json_file)

    splitted_cam_creds = {}
    for _ip, cam_data in cameras_credentials.items():
        if _ip != "organization":
            splitted_cam_creds[_ip] = cam_data["token"]

    engine = Engine(
        api_host=API_URL,
        cam_creds=splitted_cam_creds,
        external_sources=True,
    )

    # Iterate over each image path
    for image_path in image_paths:
        try:
            _, _, day, camera_id, filename = image_path.split(os.sep)

            date = filename[:-4]

            logger.info(
                f"Day: {day}, Camera ID: {camera_id}, Date: {date}, Path: {image_path}"
            )

            frame = Image.open(image_path).convert("RGB")
            # Initialiser l'Engine

            confidence = engine.predict(frame=frame, cam_id=camera_id, pose_id=None)
            logger.info(f"Image: {image_path} - Confiance: {confidence:.2%}")

            engine._process_alerts()

        except Exception as e:
            logger.exception(f"Erreur lors du traitement de l'image {image_path}: {e}")
        finally:
            logger.info(f"Removing: {image_path}")
            os.remove(image_path)


if __name__ == "__main__":
    main()
