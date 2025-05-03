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

def annotate_video(input_file, output_dir=Path("./annotated_videos")):
    """
    Annotate a video with date and time overlays.
    Args:
        input_file (Path): Path to the input video file.
        output_dir (Path): Directory where the annotated video will be saved.
    """
    
    # TODO: get rid of os.path stuff and use pathlib

    # Check if the input file exists
    if not input_file.exists():
        print(f"Error: File '{input_file}' does not exist.")
        return

    # Check if the input file is a video file
    if not input_file.name.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
        print(f"Error: File '{input_file}' is not a valid video file.")
        return

    # Paths and file names
    output_dir = Path(output_dir)
    file_name = input_file.stem
    file_extension = input_file.suffix[1:]

    # Parse out date (YYYYMMDD) and time (HHMMSS)
    prefix, datepart, timepart = file_name.split('_')

    # Build SMPTE timecode
    tc = f"{timepart[:2]}\\:{timepart[2:4]}\\:{timepart[4:]}\\:00"

    # Format the date
    date_fmt = f"{datepart[:4]}-{datepart[4:6]}-{datepart[6:]}"

    # Output file
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the directory if it doesn't exist
    output_file = output_dir / f"{file_name}_dated_tc.{file_extension}"
    # Check if the output file already exists
    if output_file.exists():
        print(f"Warning: Output file '{output_file}' already exists. Returning without overwriting.")
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
        sys.exit(1)
    frame_rate = eval(video_stream['r_frame_rate'])  # Convert "30/1" to 30.0

    # Build the FFmpeg filter
    font_file = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = 32
    font_color = "white"

    # Build SMPTE timecode
    start_time_seconds = int(timepart[:2]) * 3600 + int(timepart[2:4]) * 60 + int(timepart[4:])  # Convert HHMMSS to seconds

    dynamic_timecode = (
        f"text='%{{eif\\:mod((t+{start_time_seconds})/3600\\,24)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})/60\\,60)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})\\,60)\\:d\\:2}}'"
    )
    filter_complex = (
        f"fps=fps={frame_rate},"
        f"drawtext=fontfile={font_file}:"
        f"text='{date_fmt}':fontcolor={font_color}:fontsize={font_size}:x=100:y=h-180:box=0,"
        f"drawtext=fontfile={font_file}:"
        f"{dynamic_timecode}:fontcolor={font_color}:fontsize={font_size}:x=100:y=h-140:box=0,"
        f"drawtext=fontfile={font_file}:"
        f"text='LA County USA':fontcolor={font_color}:fontsize={font_size}:x=100:y=h-100:box=0"
    )

    # Run FFmpeg with fps filter in the input
    try:
        (
            ffmpeg
            .input(input_file)  # Normalize frame rate here
            .output(str(output_file), vf=filter_complex, vcodec='libx264', crf=18, preset='medium')
            .run()
        )
        print(f"Wrote '{output_file}' with date '{date_fmt}' and timecode starting at '{timepart[:2]}:{timepart[2:4]}:{timepart[4:]}'")
    except:
        print(f"Error: Failed to write {output_file}")
        output_file.unlink(missing_ok=True)  # Remove the output file if it exists

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Annotate a video with date and time overlays.")
    parser.add_argument("-i", "--input", required=True, type=str, help="Path to the input video file.")
    parser.add_argument("-o", "--output", required=True, type=str, help="Path to the output directory.")
    args = parser.parse_args()

    annotate_video(args.input, args.output)