import shutil
import cv2
import torch
from pathlib import Path
from find_birds import draw_bounding_box, detect_false_positives

def detect_birds(image_file, output_dir="Path('.')", confidence_threshold=0.3):
    """
    Detect birds in a still image.
    
    Args:
        image_file (Path): Path to the input image file.
        confidence_threshold (float): Confidence threshold for bird detection.
        
    Returns:
        bool: True if birds are detected, False otherwise.
    """
    # Load the YOLOv5 model
    model = torch.hub.load("ultralytics/yolov5", "yolov5s", pretrained=True)
    
    # Load the image
    image = cv2.imread(str(image_file))
    if image is None:
        print(f"Error loading image file: {image_file}")
        return False
    
    # Perform inference
    results = model(image)
    detections = results.pandas().xyxy[0]

    # Hilariously, the model is sometimes identifying birds as "cat" or other things.
    # FIXME:  This is a temporary fix, but it works for now. Need to train a custom model.
    birds = detections[
        # (
            (detections["name"] == "bird") &
            # (detections["name"] == "cat")  |
            # (detections["name"] == "dog")  |
            # (detections["name"] == "person")
        # ) & 
        (detections["confidence"] > confidence_threshold)
        ]
    
    if birds.empty:
        print(f"No birds detected in {image_file}.")
        image_file.unlink(missing_ok=True)
        dmg_file = image_file.with_suffix(".dng")
        dmg_file.unlink(missing_ok=True)
        return False
    
    print(f"Detected {len(birds)} birds in {image_file}.")

    real_detections = 0
    for index, row in birds.iterrows():
        box = row[["xmin", "ymin", "xmax", "ymax"]].values

        # Check for false positives
        if detect_false_positives(box):
            continue
        else:
            real_detections += 1
        
        draw_bounding_box(image, box, label=row.get("name"), confidence=row["confidence"])
    
    if real_detections == 0:
        print(f"No valid bird detections in {image_file}.")
        image_file.unlink(missing_ok=True)
        dmg_file = image_file.with_suffix(".dng")
        dmg_file.unlink(missing_ok=True)
        return False
    
    else:

        # Save the annotated image
        output_file = Path(output_dir) / image_file.name.replace(".jpg", "_annotated.jpg")
        print(output_file)
        cv2.imwrite(str(output_file), image)

        # Move the original image to the output directory on separate drive
        shutil.move(image_file, Path(output_dir) / image_file.name)
        shutil.move(image_file.with_suffix(".dng"), 
                    Path(output_dir) / image_file.name.replace(".jpg", ".dng"))

        return True  # Simulating detection for demonstration purposes

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect birds in still images.")
    parser.add_argument("--input_dir", type=Path, default=Path("."), help="Directory containing input images.")
    parser.add_argument("--output_dir", type=Path, default=Path("."), help="Directory to save annotated images.")
    parser.add_argument("--confidence_threshold", type=float, default=0.3, help="Confidence threshold for bird detection.")

    args = parser.parse_args()

    already_processed = set()

    while True:
        image_files = sorted(args.input_dir.glob("*.jpg"))
        if not image_files:
            print("No images found. Waiting for new images...")
            break
        
        for image_file in image_files:
            if image_file.name in already_processed:
                continue
            print(f"Processing {image_file}...")
            detect_birds(image_file, args.output_dir, 
                         args.confidence_threshold)
            already_processed.add(image_file.name)
