"""
find_birds.py
This script processes birdcam videos to detect birds and save clips of the detected events.
It uses the YOLOv5 model for object detection and MoviePy for video processing.
It extracts frames from the video, detects birds in those frames, and saves clips around the detected timestamps.
It also combines all the clips into a single video file.

Usage:
    python find_birds.py -i <input_video_directory> -o <output_directory>

"""

import argparse
import cv2
import torch
import pandas as pd
from moviepy.editor import VideoFileClip, concatenate_videoclips
from pathlib import Path

def extract_frames(video_path, output_rate=1):
    """
    Extract frames from a video at a specified rate as a generator.
    Args:
        video_path (str): Path to the input video file.
        output_rate (int): Rate at which to extract frames (1 means every frame, 2 means every second frame, etc.).
    Yields:
        frame (numpy.ndarray): Extracted frame.
        timestamp (float): Timestamp corresponding to the extracted frame.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = int(fps / output_rate)

    for frame_number in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)  # Jump ahead to the next frame_interval
        ret, frame = cap.read()
        if not ret:
            break
        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0  # Timestamp in seconds
        yield frame, timestamp

    # frame_count = 0
    # while True:
    #     ret, frame = cap.read()
    #     if not ret:
    #         break
    #     if frame_count % frame_interval == 0:
    #         timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0  # seconds
    #         yield frame, timestamp
    #     frame_count += 1

    cap.release()

def detect_birds(video_path, output_rate=1, model_name='yolov5s', confidence_threshold=0.3):
    """
    Detect birds in frames using a pre-trained YOLOv5 model.
    Args:
        video_path (Path): Path to the input video file.
        output_rate (int): Rate at which to extract frames.
        model_name (str): Name of the YOLOv5 model to use (e.g., 'yolov5s', 'yolov5m', etc.).
        confidence_threshold (float): Minimum confidence score for detections.
    Returns:
        bird_times (list): List of timestamps where birds were detected.
    """
    # Load the YOLOv5 model
    model = torch.hub.load('ultralytics/yolov5', model_name, pretrained=True)
    bird_times = []

    # Process frames one by one
    for frame, timestamp in extract_frames(video_path, output_rate=output_rate):
        results = model(frame)
        detections = results.pandas().xyxy[0]
        birds = detections[(detections['name'] == 'bird') & (detections['confidence'] > confidence_threshold)]
        if not birds.empty:
            print(f"Bird detected at {timestamp:.2f} seconds")
            bird_times.append(timestamp)

    return bird_times

def group_and_save_clips(video_path, output_path, timestamps, pre_buffer=10.0, post_buffer=10.0, min_gap=10.0):
    """
    Group timestamps and save video clips around detected birds.
    Args:
        video_path (Path): Path to the input video file.
        output_path (Path): Directory to save the output clips.
        timestamps (list): List of timestamps where birds were detected.
        pre_buffer (float): Time before the detected timestamp to include in the clip.
        post_buffer (float): Time after the detected timestamp to include in the clip.
        min_gap (float): Minimum gap between clips to consider them separate.
    """

    clip = VideoFileClip(str(video_path))
    timestamps = sorted(timestamps)

    merged_intervals = []
    if not timestamps:
        return

    # Initialize first interval
    start = max(0, timestamps[0] - pre_buffer)
    end = min(clip.duration, timestamps[0] + post_buffer)

    for t in timestamps[1:]:
        if t - end <= min_gap:  # close enough to merge
            end = min(clip.duration, t + post_buffer)
        else:
            merged_intervals.append((start, end))
            start = max(0, t - pre_buffer)
            end = min(clip.duration, t + post_buffer)
    merged_intervals.append((start, end))  # Don't forget the last interval

    # Save subclips
    for i, (s, e) in enumerate(merged_intervals):
        subclip = clip.subclip(s, e)

        # Format the start time as HH-MM-SS for the file name
        # h, m, s = int(s // 3600), int((s % 3600) // 60), int(s % 60)
        start_time_str = f"{int(s):04d}"

        # Include the start time in the output file name
        sub_clip_file = output_path / f"{video_path.stem}_clip_{start_time_str}.mp4"
        if sub_clip_file.exists():
            print(f"Clip {sub_clip_file} already exists. Skipping...")
            continue

        # Save the subclip
        subclip.write_videofile(str(sub_clip_file), codec="libx264", audio_codec="aac", audio=True, logger=None)
        print(f"Saved merged clip: {sub_clip_file}")

    clip.close()

def combine_clips(clips_dir, output_file="combined_bird_clips.mp4"):
    """
    Combine individual video clips into a single video file.
    Args:
        clips_dir (str or Path): Directory containing the individual video clips.
        output_file (str): Path to the output combined video file.
    """

    if not clips_dir.exists() or not clips_dir.is_dir():
        print(f"Error: Directory '{clips_dir}' does not exist or is not a directory.")
        return

    # Get all video files in the directory, sorted by name
    clip_files = sorted(clips_dir.glob("*.mp4"))
    if not clip_files:
        print(f"No video clips found in '{clips_dir}'.")
        return

    # Load all clips
    clips = [VideoFileClip(str(clip_file)) for clip_file in clip_files]

    # Concatenate the clips
    combined = concatenate_videoclips(clips, method="compose")

    # Write the combined video to the output file
    combined.write_videofile(str(output_file), codec="libx264", audio_codec="aac", audio=True)
    print(f"Combined video saved to: {output_file}")

    # Close all clips
    for clip in clips:
        clip.close()

def find_birds_and_save_clips(video_path, output_path=Path("clips"), output_rate=1, pre_buffer=10.0, post_buffer=10.0, min_gap=10.0):
    """
    Main function to find birds in a video and save clips.
    Args:
        video_path (Path): Path to the input video file.
        output_path (Path): Path to the output directory for clips.
        output_rate (int): Rate at which to extract frames.
        pre_buffer (float): Time before the detected timestamp to include in the clip.
        post_buffer (float): Time after the detected timestamp to include in the clip.
        min_gap (float): Minimum gap between clips to consider them separate.
    """

    # If the CSV file already exists, load it and skip bird detection.
    # But if the CSV file is empty, reprocess bird detection.
    csv_file = output_path / f"{video_path.stem}_timestamps.csv"
    reprocess = False
    if csv_file.exists():
        # Load existing timestamps from CSV, sorted
        bird_timestamps = pd.read_csv(str(csv_file))["Bird Detected At (s)"].tolist()
        bird_timestamps.sort()
        # if len(bird_timestamps) == 0:
        #     print(f"No bird timestamps found in '{csv_file}'. Reprocessing...")
        #     csv_file.unlink()  # Delete the empty CSV file
        #     reprocess = True
        # else:
            
        print(f"Timestamps file '{csv_file}' already exists. Skipping bird detection. Moving on to clip export.")
    else:
        reprocess = True
    if reprocess:
        print(f"Looking for birds in {video_path}...")
        bird_timestamps = detect_birds(video_path, output_rate=output_rate)

        # Save timestamps to CSV
        pd.Series(bird_timestamps, name="Bird Detected At (s)").to_csv(str(csv_file), index=False)

    # Export clips
    group_and_save_clips(video_path, output_path, bird_timestamps, pre_buffer, post_buffer, min_gap)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam videos for a specific day.")
    parser.add_argument(
        "-i", "--input_file",
        required=True,
        help="Path to the directory containing the videos."
    )
    parser.add_argument(
        "-o", "--output_file",
        required=True,
        help="Path to the directory where the output will be saved."
    )
    args = parser.parse_args()

    # Convert input and output paths to Path objects
    input_file = Path(args.input_file)
    output_file = Path(args.output_file)
    output_path = output_file.parent

    # Find those birds!
    find_birds_and_save_clips(input_file, output_path=output_path)

    # Combine bird clips into a single video
    combine_clips(output_path, output_file=output_file)
