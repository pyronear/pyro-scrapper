# process_images.py

import os
from PIL import Image
from pyroengine.engine import Engine
import logging
import argparse
import glob
from dotenv import load_dotenv

load_dotenv()

# Configurer le logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_BASE_PATH = os.getenv("OUTPUT_PATH", "AWF_scrap")


def parse_args():
    parser = argparse.ArgumentParser(description="Traiter des images pour détecter des signes de feux de forêt.")
    parser.add_argument(
        "--api_url",
        type=str,
        default=None,
        help="URL de l'API pyronear. Laisser vide pour ne pas utiliser l'API."
    )
    return parser.parse_args()

def main():
    args = parse_args()

    images_folder = OUTPUT_BASE_PATH + "/dl_frames"
    api_url = args.api_url

    # Vérifiez que le dossier des images existe
    if not os.path.isdir(images_folder):
        logger.error(f"Le dossier des images '{images_folder}' n'existe pas.")
        exit(1)

    image_paths = glob.glob(os.path.join(images_folder, "*/*/*.jpg"))
    if not image_paths:
        logger.warning(f"Aucune image trouvée dans le dossier '{images_folder}'.")
        exit(0)

    logger.info(f"Nombre d'images à traiter : {len(image_paths)}")
    
    engines = {} 
    
    # Iterate over each image path
    for image_path in image_paths:
        try:
            _, _, day, camera_id, filename = image_path.split(os.sep)

            date = filename[:-4]

            logger.info(f"Day: {day}, Camera ID: {camera_id}, Date: {date}, Path: {image_path}")
            
            if camera_id not in engines:
                engine = Engine(
                    api_host=api_url,
                    static_cam_id=camera_id,
                )
                engines.append(engine)
            
            frame = Image.open(image_path).convert("RGB")
            # Initialiser l'Engine

            confidence = engines[camera_id].predict(frame=frame, cam_id=camera_id, pose_id=None)
            logger.info(f"Image: {image_path} - Confiance: {confidence:.2%}")
            
            engines[camera_id].process_alerts()

        except Exception as e:
            logger.exception(f"Erreur lors du traitement de l'image {image_path}: {e}")
        finally:
            logger.info(f"Removing: {image_path} - Confiance: {confidence:.2%}")
            os.remove(image_path)

if __name__ == "__main__":
    main()
