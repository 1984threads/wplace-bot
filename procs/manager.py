import multiprocessing as mp
import time
import cloudscraper
import traceback
from helpers import logsetup
from PIL import Image
from io import BytesIO

# Chunk of the Tsar bomba testing site, Mityushikha Bay.
CHUNK_X = 1334
CHUNK_Y = 391

INIT_X = 0
INIT_Y = 0

PATH_TO_IMAGE = "assets/wplace.png"

COLORS_RGBA = [
    {"color": [0, 0, 0, 0], "alias": "Transparent"},
    {"color": [0, 0, 0, 255], "alias": "Black"},
    {"color": [60, 60, 60, 255], "alias": "Dark Gray"},
    {"color": [120, 120, 120, 255], "alias": "Gray"},
    {"color": [210, 210, 210, 255], "alias": "Light Gray"},
    {"color": [255, 255, 255, 255], "alias": "White"},
    {"color": [96, 0, 24, 255], "alias": "Deep Red"},
    {"color": [237, 28, 36, 255], "alias": "Red"},
    {"color": [255, 127, 39, 255], "alias": "Orange"},
    {"color": [246, 170, 9, 255], "alias": "Gold"},
    {"color": [249, 221, 59, 255], "alias": "Yellow"},
    {"color": [255, 250, 188, 255], "alias": "Light Yellow"},
    {"color": [14, 185, 104, 255], "alias": "Dark Green"},
    {"color": [19, 230, 123, 255], "alias": "Green"},
    {"color": [135, 255, 94, 255], "alias": "Light Green"},
    {"color": [12, 129, 110, 255], "alias": "Dark Teal"},
    {"color": [16, 174, 166, 255], "alias": "Teal"},
    {"color": [19, 225, 190, 255], "alias": "Light Teal"},
    {"color": [40, 80, 158, 255], "alias": "Dark Blue"},
    {"color": [64, 147, 228, 255], "alias": "Blue"},
    {"color": [96, 247, 242, 255], "alias": "Cyan"},
    {"color": [107, 80, 246, 255], "alias": "Indigo"},
    {"color": [153, 177, 251, 255], "alias": "Light Indigo"},
    {"color": [120, 12, 153, 255], "alias": "Dark Purple"},
    {"color": [170, 56, 185, 255], "alias": "Purple"},
    {"color": [224, 159, 249, 255], "alias": "Light Purple"},
    {"color": [203, 0, 122, 255], "alias": "Dark Pink"},
    {"color": [236, 31, 128, 255], "alias": "Pink"},
    {"color": [243, 141, 169, 255], "alias": "Light Pink"},
    {"color": [104, 70, 52, 255], "alias": "Dark Brown"},
    {"color": [149, 104, 42, 255], "alias": "Brown"},
    {"color": [248, 178, 119, 255], "alias": "Beige"}
]

def find_closest_color(rgba_tuple: tuple) -> tuple:
    """
    Given a tuple of RGBA values, returns the closest color from the
    predefined COLORS_RGBA list, in the form of a tuple consisting of
    the index and its name.

    Args:
        rgba_tuple (tuple): A tuple of (R, G, B, A) values, where each value
                            is between 0 and 255.

    Returns:
        tuple: A tuple containing the index of the closest color and its alias,
               e.g., (index, "Alias Name").
    """
    if not (isinstance(rgba_tuple, tuple) and len(rgba_tuple) == 4 and
            all(0 <= val <= 255 for val in rgba_tuple)):
        raise ValueError("Input must be an RGBA tuple with values between 0 and 255.")

    min_distance_squared = float('inf')
    closest_color_info = None

    for index, color_info in enumerate(COLORS_RGBA):
        r1, g1, b1, a1 = rgba_tuple
        r2, g2, b2, a2 = color_info["color"]

        # Calculate Euclidean distance squared for performance (no need for sqrt)
        distance_squared = (r2 - r1)**2 + \
                           (g2 - g1)**2 + \
                           (b2 - b1)**2 + \
                           (a2 - a1)**2

        if distance_squared < min_distance_squared:
            min_distance_squared = distance_squared
            closest_color_info = (index, color_info["alias"])

    return closest_color_info

class ManagerClass(mp.Process):
    def __init__(self,
            log_pipe: mp.Queue,
            task_pipe: mp.Queue,
            luz_lock,
            ):
        super().__init__()
        self.log_pipe = log_pipe
        self.task_pipe = task_pipe
        self.luz_lock = luz_lock

    def run(self):
        logger = logsetup(self.log_pipe, f"Manager")
        scraper = cloudscraper.create_scraper()
        logger.info(f"Manager successfully initated")

        chunk_url = f"https://backend.wplace.live/files/s0/tiles/{CHUNK_X}/{CHUNK_Y}.png"

        img = Image.open(PATH_TO_IMAGE).convert("RGBA")
        img_pixels = img.load()
        img_width, img_height = img.size

        while True:
            try:
                self.luz_lock.value = False
                
                logger.info(f"Clearing task pipe...")
                while not self.task_pipe.empty():
                    try:
                        self.task_pipe.get(block=False)
                    except Exception:
                        logger.info(f"Task pipe should now be clear")
                        continue

                logger.info(f"Obtaining and cropping chunk map...")
                response = scraper.get(chunk_url)
                response.raise_for_status()
                chunk_map = Image.open(BytesIO(response.content)).convert("RGBA")
                crop_box = (
                    INIT_X, 
                    INIT_Y,
                    INIT_X + img_width,
                    INIT_Y + img_height
                )
                chunk_area = chunk_map.crop(crop_box)
                chunk_pixels = chunk_area.load()
                logger.info(f"Success")

                logger.info(f"Comparing pixels...")
                for y in range(img_height):
                    for x in range(img_width):
                        current_pixels = chunk_pixels[x, y]
                        target_pixels = img_pixels[x, y]
                        if current_pixels != target_pixels:
                            color_id, color_name = find_closest_color(target_pixels)
                            self.task_pipe.put({
                                "coord": [INIT_X + x, INIT_Y + y],
                                "color_id": color_id,
                                "color_name": color_name
                            })
                
                self.luz_lock.value = True                
            except Exception as e:
                logger.info(f"Detected error: {''.join(str(item) for item in traceback.format_exception(type(e), e, e.__traceback__))}")
            finally:
                if self.luz_lock.value is not True:
                    self.luz_lock.value = True
                logger.info(f"Sleeping for 60 seconds...")
                time.sleep(60)