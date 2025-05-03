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
import ffmpeg

def process_videos_from_day(date, video_path, output_path):
    """
    Process all videos from a specific day.
    Args:
        date (str): Date in the format YYYYMMDD.
        video_path (Path): Path to the directory containing the videos.
        output_path (Path): Path to the directory where the output will be saved.
    """

    # Set up paths
    date_path = output_path / date
    date_path.mkdir(parents=True, exist_ok=True)
    annotate_video_path = date_path / "annotated_videos"
    annotate_video_path.mkdir(parents=True, exist_ok=True)
    clips_path = date_path / "clips"
    clips_path.mkdir(parents=True, exist_ok=True)
    combined_file_path = date_path / f"{date}_combined_bird_clips.mp4"

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

    # Process each video file
    for video_file in video_files:
        print(f"Annotating {video_file}...")
        annotate_video(video_file, annotate_video_path)

    annotated_videos = sorted(annotate_video_path.glob(f"*{date}_*.mp4"))
    if not annotated_videos:
        print(f"No annotated video files found in '{annotate_video_path}'.")
        return
    
    # Check to see if any clips for this date already exist
    existing_clips = sorted(clips_path.glob(f"*{date}_*.mp4"))
    if existing_clips:
        print(f"Clips already exist for date {date}. Moving on to combine clips.")
    else:
        print(f"Searching for birds for date {date}...")
        # Process each annotated video file
        for annotated_video in annotated_videos:
            print(f"Finding birds in {annotated_video}...")
            find_birds_and_save_clips(annotated_video, clips_path)

    combine_clips(clips_path, combined_file_path)

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

    process_videos_from_day(
        date=args.date,
        video_path=input_path,
        output_path=output_path
    )
