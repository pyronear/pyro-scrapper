import glob
import os
import shutil

import cv2
import numpy as np
from tqdm import tqdm
from typing import Dict

def resize_image(image, max_width):
    """
    Resize an image to a specified maximum width while maintaining the aspect ratio.

    Args:
        image (np.ndarray): The input image as a NumPy array.
        max_width (int): The maximum width for the resized image.

    Returns:
        np.ndarray: The resized image.
    """
    h, w = image.shape[:2]
    if w > max_width:
        scale = max_width / w
        image = cv2.resize(image, (int(w * scale), int(h * scale)))
    return image


def extract_features(image_path):
    """
    Extract keypoints and descriptors from an image using ORB.

    Args:
        image_path (str): Path to the image file.

    Returns:
        tuple: A tuple containing:
            - keypoints (list): A list of detected keypoints.
            - descriptors (np.ndarray): A NumPy array of descriptors corresponding to the keypoints.
    """
    # Load image
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    image = resize_image(image, max_width=500)

    # Use ORB or SIFT for feature detection
    orb = cv2.ORB_create()  # type: ignore[attr-defined]
    keypoints, descriptors = orb.detectAndCompute(image, None)
    return keypoints, descriptors


def match_features(descriptors1, descriptors2):
    """
    Match descriptors between two images using the BFMatcher.

    Args:
        descriptors1 (np.ndarray): Descriptors from the first image.
        descriptors2 (np.ndarray): Descriptors from the second image.

    Returns:
        list: A list of matched keypoints, sorted by distance (lower distance indicates better matches).
    """
    if descriptors1 is None or descriptors2 is None:
        return []
    # Use BFMatcher to find the best matches between descriptors
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(descriptors1, descriptors2)
    # Sort matches by distance (lower distance is better)
    matches = sorted(matches, key=lambda x: x.distance)
    return matches


def compute_homography(kp1, kp2, matches):
    """
    Compute the homography matrix between two sets of matched keypoints using RANSAC.

    Args:
        kp1 (list): Keypoints from the first image.
        kp2 (list): Keypoints from the second image.
        matches (list): Matched keypoints between the two images.

    Returns:
        tuple: A tuple containing:
            - H (np.ndarray): The homography matrix.
            - inliers (int): The number of inliers found during RANSAC.
    """
    # Extract the matched keypoints
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    # Compute the homography matrix using RANSAC
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    # Number of inliers (good matches)
    inliers = mask.sum()
    return H, inliers


def create_cluster(imgs, features, match_th=125, inliers_th=50):
    """
    Create clusters of images based on feature matching and homography inliers.

    Args:
        imgs (list): List of image file paths.
        features (list): List of tuples containing keypoints and descriptors for each image.
        match_th (int): Threshold for the minimum number of matches required to consider a match.
        inliers_th (int): Threshold for the minimum number of inliers to consider a valid match.

    Returns:
        dict: A dictionary where keys are cluster IDs and values are lists of image indices belonging to each cluster.
    """
    clusters: Dict[int, list] = {}
    for i in range(len(imgs)):
        match_found = -1
        for k, indexes in clusters.items():
            if match_found == -1:
                j = indexes[-1]

                kp1, desc1 = features[i]
                kp2, desc2 = features[j]
                matches = match_features(desc1, desc2)

                if len(matches) > match_th:
                    for j in indexes[-1:][::-1]:
                        if match_found == -1:
                            kp2, desc2 = features[j]
                            matches = match_features(desc1, desc2)
                            _, inliers = compute_homography(kp1, kp2, matches)
                            if inliers > inliers_th:
                                match_found = k
                                clusters[k].append(i)

        if match_found == -1:
            clusters[len(clusters)] = [i]

    return clusters


def move_to_groups(clusters, imgs, clean=True):
    """
    Move images into folders based on their clusters and optionally clean up the original folders.

    Args:
        clusters (dict): A dictionary where keys are cluster IDs and values are lists of image indices.
        imgs (list): List of image file paths.
        clean (bool): If True, removes the original folders after moving the images.

    Returns:
        None
    """
    group_id = 0
    for indexes in clusters.values():
        if len(indexes) > 4:
            for i in indexes:
                file = imgs[i]
                folder, name = os.path.split(file)
                new_file = os.path.join(
                    folder.replace("dl_frames", "dl_frames_splitted"),
                    str(group_id).zfill(3),
                    name,
                )
                os.makedirs(os.path.dirname(new_file), exist_ok=True)
                shutil.move(file, new_file)

            group_id += 1

        if clean:
            file = imgs[indexes[0]]
            folder = os.path.dirname(file)
            shutil.rmtree(folder)


# Main Script
if __name__ == "__main__":
    folders = glob.glob("AWF_scrap/dl_frames/**/*")
    folders.sort()

    for folder in tqdm(folders, desc="Splitting folders"):
        imgs = glob.glob(f"{folder}/*")
        imgs.sort()

        # Compute features
        features = [extract_features(img) for img in imgs]

        # Make clusters
        clusters = create_cluster(imgs, features, match_th=125, inliers_th=50)

        # Move images
        move_to_groups(clusters, imgs, clean=True)
