from find_birds import combine_clips_ffmpeg
from pathlib import Path
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine annotated clips into a single video.")
    parser.add_argument(
        "-i", "--input_path",
        required=True,
        help="Path to the directory containing the annotated clips."
    )
    parser.add_argument(
        "-o", "--output_path",
        required=True,
        help="Path to the directory where the combined video will be saved."
    )
    parser.add_argument(
        "--hourly",
        required=False,
        default=False,
        action='store_true',
        help="Whether to make hourly combined videos instead of daily."
    )
    args = parser.parse_args()

    # Convert input and output paths to Path objects
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Combining annotated clips from {input_path} and saving to {output_path}...")

    if args.hourly:
        # Combine clips into hourly videos
        for hour in range(24):
            all_clips = sorted(input_path.glob(f"*.mp4"))
            hourly_clips = [f for f in all_clips if int(f.name.split('_')[2][0:2]) == hour]
            if not hourly_clips:
                print(f"No clips found for hour {hour:02d}. Skipping.")
                continue
            date_str = hourly_clips[0].name.split('_')[1]
            hourly_output_path = output_path / f"hummingbirdcam_{date_str}_{hour:02d}_hour.mp4"
            combine_clips_ffmpeg(input_path, [hourly_output_path], hour=hour)
    else:
        # Combine all clips into a single video
        combine_clips_ffmpeg(input_path, [output_path])
