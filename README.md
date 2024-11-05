# pyro-scrapper

## Overview
Pyro-Scrapper is a specialized tool designed for scraping images from [Alert Wildfire](https://www.alertwildfire.org/), splitting these images by camera, and preparing them for future analysis using Pyro-Engine (not yet developed). The primary objective of this project is to augment the Pyronear dataset with images of wildfires, which can be either actual fires or false positives, both of which are valuable for analysis.

## Features
- **Image Scraping**: Downloads images from Alert Wildfire, leveraging the `dl_images.py` script. This involves fetching camera data, processing images, and handling various states and timezones. [View Script](https://github.com/MateoLostanlen/pyro-scrapper/blob/main/src/dl_images.py)

- **Image Splitting**: The `split_cams.py` script is used to split images based on the camera viewpoint

- **Data Processing by Pyro-engine**: We pass all images into [pyro-engine](https://github.com/pyronear/pyro-engine) as if they came from a Pyronear camera in order to make predictions and send alerts via our api.

## How It Works
1. **Scraping Images**: The script `dl_images.py` downloads images from Alert Wildfire, categorizing them based on the camera's state and source. It processes the images to ensure they meet the required standards (e.g., removing grayscale images).

2. **Splitting by Camera**: `split_cams.py` TO BE DEVELOPED

3. **Data Processing by Pyro-engine**: TO BE DEVELOPED

Certainly! Here's the revised Usage section with the added code snippets:

## Installation and Usage

### Locally
- Clone the repository.
- Ensure you have the required dependencies by installing them from `requirements.txt`.

Install requirements
```bash
pip install -r requirements.txt
```

To download images:
```bash
python src/dl_images.py
```

To split images by camera:
```bash
python/split_cams.py
```

These commands will initiate the image scraping and view point splitting.


### Using the docker image

First you will need to generate the credentials.json file according to the source you want to scrapp. 
For the alertwildfire , you can use the src/generate_wildfire_config.py script.

Then you have two choices : 
1) using the pyro-devops dev env, copying the credentials.json file in the data/ folder and launching the 'make-etl' command
2) filling your .env locally (API_URL) in order to use an external Pyro-API , filling the token part of the credentials.json and launching the command 'make run-etl' from this repo.

## Contributing

Please refer to [`CONTRIBUTING`](CONTRIBUTING.md) if you wish to contribute to this project.

## Credits

This project is developed and maintained by the repo owner and volunteers from [Pyronear](https://pyronear.org/).

## License

Distributed under the Apache 2 License. See [`LICENSE`](LICENSE) for more information.
