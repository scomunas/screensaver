import os
import re
import logging
from datetime import datetime
from PIL import Image
import exifread
from config import PHOTO_EXTENSIONS

logger = logging.getLogger("nas_manager")

def get_clean_string(tag_val):
    if tag_val is None:
        return None
    val_str = str(tag_val).strip()
    val_str = val_str.replace('\x00', '').strip()
    return val_str if val_str and val_str.lower() != 'none' else None

def parse_ratio(ratio):
    """
    Safely converts an exifread Ratio/Digitial number to a float.
    """
    if ratio is None:
        return None
    try:
        if hasattr(ratio, 'values') and len(ratio.values) > 0:
            val = ratio.values[0]
            if hasattr(val, 'num') and hasattr(val, 'den'):
                if val.den == 0:
                    return None
                return float(val.num) / float(val.den)
        val_str = str(ratio)
        if '/' in val_str:
            num, den = val_str.split('/')
            return float(num) / float(den)
        return float(val_str)
    except Exception:
        return None

def parse_iso(iso_val):
    if iso_val is None:
        return None
    try:
        if hasattr(iso_val, 'values') and len(iso_val.values) > 0:
            return int(iso_val.values[0])
        return int(str(iso_val).split(',')[0].strip())
    except Exception:
        return None

def get_exif_date(tags):
    for key in ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTimeDigitized']:
        date_tag = tags.get(key)
        if date_tag:
            try:
                date_str = get_clean_string(date_tag)
                if date_str:
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
            except Exception:
                continue
    return None

def get_date_from_filename(filename):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})',
        r'IMG_(\d{4})(\d{2})(\d{2})_(\d{6})'
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                p = match.groups()
                return datetime(int(p[0]), int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5]))
            except Exception:
                continue
    return None

def extract_photo_metadata(file_path: str) -> dict:
    """
    Extracts dimensions and EXIF metadata from a photo.
    Returns a dictionary of cleaned metadata values.
    """
    metadata = {
        "width": None,
        "height": None,
        "date_taken": None,
        "camera_make": None,
        "camera_model": None,
        "lens_model": None,
        "exposure_time": None,
        "f_number": None,
        "iso": None,
        "focal_length": None
    }
    
    # 1. Read width and height using Pillow (fast header read)
    try:
        with Image.open(file_path) as img:
            metadata["width"], metadata["height"] = img.size
    except Exception as e:
        logger.warning(f"Pillow failed to read dimensions for {file_path}: {e}")
    
    # 2. Extract EXIF details using exifread
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            metadata["date_taken"] = get_exif_date(tags)
            metadata["camera_make"] = get_clean_string(tags.get('Image Make'))
            metadata["camera_model"] = get_clean_string(tags.get('Image Model'))
            metadata["lens_model"] = get_clean_string(tags.get('EXIF LensModel')) or get_clean_string(tags.get('EXIF LensSpecification'))
            
            exposure = tags.get('EXIF ExposureTime')
            if exposure:
                metadata["exposure_time"] = get_clean_string(exposure)
                
            metadata["f_number"] = parse_ratio(tags.get('EXIF FNumber'))
            metadata["iso"] = parse_iso(tags.get('EXIF ISOSpeedRatings'))
            metadata["focal_length"] = parse_ratio(tags.get('EXIF FocalLength'))
            
    except Exception as e:
        logger.warning(f"exifread failed for {file_path}: {e}")
    
    # 3. Fallbacks
    filename = os.path.basename(file_path)
    
    if not metadata["date_taken"]:
        metadata["date_taken"] = get_date_from_filename(filename)
        
    if not metadata["date_taken"]:
        try:
            st = os.stat(file_path)
            try:
                metadata["date_taken"] = datetime.fromtimestamp(st.st_birthtime)
            except AttributeError:
                metadata["date_taken"] = datetime.fromtimestamp(st.st_mtime)
        except Exception:
            metadata["date_taken"] = datetime.now()

    return metadata
