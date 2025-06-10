"""
Annotate a video with date and time overlays.

Arguments:
    -i, --input: Path to the input video file.
    -o, --output: Path to the output directory.

Usage:
    python annotate_video.py -i <input_video_file> -o <output_directory>

"""

import argparse
import ffmpeg
import os
from pathlib import Path
import sys

def annotate_video(input_file, output_dir=Path("./annotated_videos"),
                    start_time_seconds=0,
                    skip_bird_detection=False):
    """
    Annotate a video clip with date and time overlays.
    Args:
        input_file (Path): Path to the input video file.
        output_dir (Path): Directory where the annotated video will be saved.
        start_time_seconds (int): Starting time of the clip in seconds.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_file.stem}_annotated.mp4"

    # Check if the output file already exists
    if output_file.exists():
        print(f"Output file '{output_file}' already exists. Skipping...")
        return
    
    # Get the frame rate of the input video
    try:
        probe = ffmpeg.probe(input_file)
    except ffmpeg.Error as e:
        print(f"Bad input movie file: '{input_file}'.")
        return
    
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if not video_stream:
        print("Error: No video stream found in the input file.")
        return
    frame_rate = eval(video_stream['r_frame_rate'])  # Convert "30/1" to 30.0

    # Build the FFmpeg filter
    font_file = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = 32
    font_color = "white"

    # Paths and file names
    output_dir = Path(output_dir)
    file_name = input_file.stem
    file_extension = input_file.suffix[1:]

    # Parse out date (YYYYMMDD) and time (HHMMSS)
    datepart = file_name.split('_')[1]  # YYYYMMDD
    timepart = file_name.split('_')[2]  # HHMMSS
    if not skip_bird_detection:
        clip_start_time = file_name.split('_')[4]  # seconds
    else:
        clip_start_time = 0

    # Add the start time to the time part
    start_time_seconds = int(clip_start_time) + int(timepart[:2]) * 3600 + int(timepart[2:4]) * 60 + int(timepart[4:])

    date_fmt = f"{datepart[:4]}-{datepart[4:6]}-{datepart[6:]}"

    # Build dynamic timecode based on the clip's starting time
    dynamic_timecode = (
        f"text='%{{eif\\:mod((t+{start_time_seconds})/3600\\,24)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})/60\\,60)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})\\,60)\\:d\\:2}}'"
    )
    filter_complex = (
        f"fps=fps={frame_rate},"
        f"drawtext=fontfile={font_file}:"
        f"text='@HackedBirdhouse':fontcolor={font_color}:fontsize={font_size}:x=100:y=100:box=0,"
        f"drawtext=fontfile={font_file}:"
        f"text='{date_fmt}':fontcolor={font_color}:fontsize={font_size}:x=100:y=h-180:box=0,"
        f"drawtext=fontfile={font_file}:"
        f"{dynamic_timecode}:fontcolor={font_color}:fontsize={font_size}:x=100:y=h-140:box=0,"
        f"drawtext=fontfile={font_file}:"
        f"text='LA County USA':fontcolor={font_color}:fontsize={font_size}:x=100:y=h-100:box=0"
    )

    # Run FFmpeg with the filter
    try:
        (
            ffmpeg
            .input(input_file)
            .output(str(output_file), 
                    vf=filter_complex, 
                    vcodec='libx264', 
                    crf=18, 
                    preset='ultrafast')
            .run()
        )
        print(f"Wrote '{output_file}' with starting timecode at {start_time_seconds} seconds.")
    except ffmpeg.Error as e:
        print(f"Error: Failed to write {output_file}")
        output_file.unlink(missing_ok=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Annotate a video with date and time overlays.")
    parser.add_argument("-i", "--input", required=True, type=str, help="Path to the input video file.")
    parser.add_argument("-o", "--output", required=True, type=str, help="Path to the output directory.")
    parser.add_argument("-s", "--start-time", type=int, default=0, help="Starting time of the clip in seconds.")
    args = parser.parse_args()

    annotate_video(Path(args.input), Path(args.output), args.start_time)
