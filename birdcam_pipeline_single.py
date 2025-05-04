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
from find_birds import find_birds_and_save_clips, combine_clips
from annotate_video import annotate_video
import ffmpeg

def process_single_video(video_file, output_path):
    """
    Process a single video file.
    Args:
        video_file (Path): Path to the input video file.
        output_path (Path): Path to the directory where the output will be saved.
    """

    # Set up paths
    date = video_file.stem.split('_')[1]  # Extract date from the filename
    date_path = output_path / date
    annotate_video_path = date_path / "annotated_videos"
    annotate_video_path.mkdir(parents=True, exist_ok=True)
    clips_path = date_path / "clips"
    clips_path.mkdir(parents=True, exist_ok=True)

    # Annotate the video
    annotate_video(video_file, annotate_video_path)
    annotate_video_file = annotate_video_path / f"{video_file.stem}_dated_tc.mp4"

    # Find birds and save clips
    find_birds_and_save_clips(annotate_video_file, clips_path)

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
    