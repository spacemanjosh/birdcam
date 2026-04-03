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
                    center_horizontal=False,
                    skip_bird_detection=False,
                    is_slow_motion=False,
                    crop_square_centered=False, 
                    crop_left_half=False):
    """
    Annotate a video clip with date and time overlays.
    Args:
        input_file (Path): Path to the input video file.
        output_dir (Path): Directory where the annotated video will be saved.
        start_time_seconds (int): Starting time of the clip in seconds.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    file_base_name = input_file.stem
    if is_slow_motion:
        file_base_name += "_slow_motion"
    if center_horizontal:
        file_base_name += "_centered"
    if crop_square_centered:
        file_base_name += "_square"
    if crop_left_half:
        file_base_name += "_left_half"
    output_file = output_dir / f"{file_base_name}_annotated.mp4"

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
    frame_width = int(video_stream['width'])
    frame_height = int(video_stream['height'])

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
    if is_slow_motion:
        # If the video is in slow motion, we need to adjust the timecode to reflect the actual time in the original footage.
        # Assuming the slow motion video is at 1/4 speed, we would multiply the time by 4 to get the correct timecode.
        dynamic_timecode = (
            f"text='%{{eif\\:mod((t/4+{start_time_seconds})/3600\\,24)\\:d\\:2}}\\:%{{eif\\:mod((t/4+{start_time_seconds})/60\\,60)\\:d\\:2}}\\:%{{eif\\:mod((t/4+{start_time_seconds})\\,60)\\:d\\:2}}'"
        )
    else:
        dynamic_timecode = (
            f"text='%{{eif\\:mod((t+{start_time_seconds})/3600\\,24)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})/60\\,60)\\:d\\:2}}\\:%{{eif\\:mod((t+{start_time_seconds})\\,60)\\:d\\:2}}'"
        )
    if center_horizontal:
        dynamic_timecode = dynamic_timecode.replace("x=100", "x=(w-text_w)/2")
        crop_filter = ""
        if crop_square_centered:
            crop_size = min(frame_width, frame_height)
            crop_x = int((frame_width - crop_size) / 2)
            crop_y = int((frame_height - crop_size) / 2)
            crop_filter = f"crop={crop_size}:{crop_size}:{crop_x}:{crop_y},"
        if crop_left_half:
            crop_filter = f"crop={frame_width//2}:{frame_height}:0:0,"
        filter_complex = (
            f"{crop_filter}"
            f"fps=fps={frame_rate},"
            f"drawtext=fontfile={font_file}:"
            f"text='@HackedBirdhouse':fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=100:box=0,"
            f"drawtext=fontfile={font_file}:"
            f"text='{date_fmt}':fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=h-180:box=0,"
            f"drawtext=fontfile={font_file}:"
            f"{dynamic_timecode}:fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=h-140:box=0,"
            f"drawtext=fontfile={font_file}:"
            f"text='LA County USA':fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=h-100:box=0"
        )
    else:
        crop_filter = ""
        if crop_square_centered:
            crop_size = min(frame_width, frame_height)
            crop_x = int((frame_width - crop_size) / 2)
            crop_y = int((frame_height - crop_size) / 2)
            crop_filter = f"crop={crop_size}:{crop_size}:{crop_x}:{crop_y},"
        filter_complex = (
            f"{crop_filter}"
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
    parser.add_argument("--center-horizontal", action='store_true', help="Center the text horizontally instead of left-aligned.")
    parser.add_argument("--crop-square-centered", action='store_true', help="Center-crop video to square aspect ratio before overlays.")
    parser.add_argument("--is-slow-motion", action='store_true', help="Indicates that the input video is in slow motion, which may require different handling for timecode.")
    parser.add_argument("--crop-left-half", action='store_true', help="Crop the video to the left half before overlays.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if input_path.is_dir():
        # Get all video files in the directory
        video_files = sorted(input_path.glob("*.mp4"))
        for video_file in video_files:
            # Get the start time for this video
            start_time = video_file.stem.split('_')[4]  # seconds
            annotate_video(
                video_file,
                Path(args.output),
                int(start_time),
                center_horizontal=args.center_horizontal,
                is_slow_motion=args.is_slow_motion,
                crop_square_centered=args.crop_square_centered,
                crop_left_half=args.crop_left_half
            )
    else:        
        annotate_video(
            input_path,
            Path(args.output),
            args.start_time,
            center_horizontal=args.center_horizontal,
            is_slow_motion=args.is_slow_motion,
            crop_square_centered=args.crop_square_centered,
            crop_left_half=args.crop_left_half
        )
