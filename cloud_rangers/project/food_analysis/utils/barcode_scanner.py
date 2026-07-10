import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image

def decode_barcode(image):
    """
    Decodes a barcode from a PIL Image or numpy array.
    Returns the barcode data as a string, or None if not found.
    """
    try:
        if isinstance(image, Image.Image):
            image = np.array(image.convert('RGB'))
            # Convert RGB to BGR for OpenCV
            image = image[:, :, ::-1].copy() 

        # Preprocessing: Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect barcodes
        decoded_objects = decode(gray)

        if decoded_objects:
            # Return the first one found
            return decoded_objects[0].data.decode("utf-8")
        
        # Try with thresholding if simple grayscale fails
        _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
        decoded_objects_thresh = decode(thresh)
        
        if decoded_objects_thresh:
            return decoded_objects_thresh[0].data.decode("utf-8")

        return None

    except Exception as e:
        print(f"Error decoding barcode: {e}")
        return None
