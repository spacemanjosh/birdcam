"""
birdcam_pipeline.py
This script processes birdcam videos to detect birds and save clips of the detected events.

Arguments:
    -d, --date: Date in the format YYYYMMDD (e.g., 20250429).
    -i, --input_path: Path to the directory containing the videos.
    -o, --output_path: Path to the directory where the output will be saved.

Usage:
    python birdcam_pipeline.py -d <date> -i <input_path> -o <output_path>
"""

import argparse
from pathlib import Path
from datetime import datetime
from find_birds import find_birds_and_save_clips, combine_clips
from annotate_video import annotate_video
from birdcam_pipeline_single import process_single_video
import ffmpeg
import time

def process_videos_from_day(date, video_path, output_path, output_rate=1, confidence_threshold=0.3):
    """
    Process all videos from a specific day.
    Args:
        date (str): Date in the format YYYYMMDD.
        video_path (Path): Path to the directory containing the videos.
        output_path (Path): Path to the directory where the output will be saved.
        output_rate (int): Sampling rate for frames (1 frame every n seconds).
        confidence_threshold (float): Confidence threshold for bird detection.
    """

    # Set up paths
    date_path = output_path / date
    date_path.mkdir(parents=True, exist_ok=True)
    clips_path = date_path / "annotated_clips"
    clips_path.mkdir(parents=True, exist_ok=True)
    combined_file_path = date_path / f"{date}_combined_bird_clips.mp4"

    # Check if the combined file already exists.  If it is and it's valid, skip processing.
    if combined_file_path.exists():
        # Check the integrity of the combined mp4 file
        try:
            probe = ffmpeg.probe(str(combined_file_path))
            if probe['format']['duration'] == '0':
                print(f"Combined video file '{combined_file_path}' is empty. Reprocessing...")
                combined_file_path.unlink()
            else:
                # If the file is not empty, skip processing
                print(f"Combined video file '{combined_file_path}' is valid. Skipping processing.")
                return
        except ffmpeg.Error as e:
            print(f"Error probing combined video file: {e}")
            print(f"Reprocessing combined video file '{combined_file_path}'.")
            combined_file_path.unlink()

    # Get all video files in the directory
    video_files = sorted(video_path.glob(f"*{date}_*.mp4"))
    if not video_files:
        print(f"No video files found in '{video_path}'.")
        return
    
    # Loop over all the video files and process them
    for video_file in video_files:
        process_single_video(video_file, output_path, output_rate=output_rate, confidence_threshold=confidence_threshold)

    # Combine all clips into a single video
    combine_clips(clips_path, combined_file_path)

    return combined_file_path

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process birdcam videos for a specific day.")
    parser.add_argument(
        "-d", "--date",
        required=True,
        help="Date in the format YYYYMMDD (e.g., 20250429)."
    )
    parser.add_argument(
        "-i", "--input_path",
        required=True,
        help="Path to the directory containing the videos."
    )
    parser.add_argument(
        "-o", "--output_path",
        required=True,
        help="Path to the directory where the output will be saved."
    )

    args = parser.parse_args()

    # Convert input and output paths to Path objects
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)

    print(f"Processing videos from {args.date} in {input_path} and saving to {output_path}...")
    t1 = time.time()
    process_videos_from_day(
        date=args.date,
        video_path=input_path,
        output_path=output_path,
        output_rate=2,
        confidence_threshold=0.3
    )
    t2 = time.time()
    print(f"Processing completed in {t2 - t1:.2f} seconds.")
