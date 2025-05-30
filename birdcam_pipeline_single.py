"""
birdcam_pipeline_single.py
This script processes birdcam videos to detect birds and save clips of the detected events.

Arguments:
    -i, --input_file: Path to the directory containing the videos.
    -o, --output_path: Path to the directory where the output will be saved.

Usage:
    python birdcam_pipeline_single.py -i <input_file> -o <output_path>
"""

import argparse
from pathlib import Path
from datetime import datetime
from find_birds import find_birds_and_save_clips, combine_clips_ffmpeg
from annotate_video import annotate_video
import ffmpeg

def process_single_video(video_file, output_path, output_rate=1, confidence_threshold=0.3):
    """
    Process a single video file.
    Args:
        video_file (Path): Path to the input video file.
        output_path (Path): Path to the directory where the output will be saved.
        output_rate (int): Sampling rate for frames (1 frame every n seconds).
        confidence_threshold (float): Confidence threshold for bird detection.
    """

    # Check the integrity of the input video file
    try:
        probe = ffmpeg.probe(str(video_file))
        if probe['format']['duration'] == '0':
            print(f"Input video file '{video_file}' is empty. Skipping...")
            return
    except ffmpeg.Error as e:
        print(f"Error probing input video file: {e}")
        return

    # Set up paths
    date = video_file.stem.split('_')[1]  # Extract date from the filename
    time = video_file.stem.split('_')[2]  # Extract time from the filename
    date_path = output_path / date
    clips_path = date_path / "clips"
    annotated_clips_path = date_path / "annotated_clips"
    clips_path.mkdir(parents=True, exist_ok=True)
    annotated_clips_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate clips.
    find_birds_and_save_clips(video_file, clips_path, output_rate=output_rate, confidence_threshold=confidence_threshold)

    # Step 2: Annotate each clip
    for clip_file in clips_path.glob(f"*{date}_{time}*.mp4"):
        # Annotate the clip
        annotate_video(clip_file, annotated_clips_path)

    return date_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam videos to detect birds and save clips.")
    parser.add_argument("-i", "--input_file", type=str, required=True, help="Path to the input video file.")
    parser.add_argument("-o", "--output_path", type=str, required=True, help="Path to the output directory.")
    
    args = parser.parse_args()
    
    input_file = Path(args.input_file)
    output_path = Path(args.output_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"The input file {input_file} does not exist.")
    
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    
    process_single_video(input_file, output_path)
