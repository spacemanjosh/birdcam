import sys
if sys.platform.startswith('linux'):
    import torch
    torch.backends.mkldnn.enabled = False

from pathlib import Path
import argparse
from datetime import datetime as dt, timedelta as td, date
from birdcam_pipeline import process_videos_from_day
from upload_to_youtube import upload_video_wrapper, convert_to_utc
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam exterior footage.")
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
    parser.add_argument(
        "-d", "--date",
        required=True,
        help="Date in the format YYYYMMDD (e.g., 20250429)."
    )
    args = parser.parse_args()

    date_to_process = dt.strptime(args.date, "%Y%m%d").date()

    input_path = Path(args.input_path)
    output_path = Path(args.output_path)

    print(f"Processing videos from {args.date} in {input_path} and saving to {output_path}...")
    t1 = time.time()
    combined_file = process_videos_from_day(
        date=args.date,
        video_path=input_path,
        output_path=output_path,
        output_rate=2,
        min_hour=4,
        max_hour=21
    )
    if combined_file:
        print(f"Combined video saved to: {combined_file}")


        description = """
A nesting pair of Western Bluebirds!  Exterior clips from throughout the day.

Video taken on a Raspberry Pi Zero 2W with Camera Module v3 (NoIR Wide version).  Details here: https://github.com/spacemanjosh/birdcam
Bird species identified by audio using the Cornell Lab of Ornithology's Merlin Bird ID app.  Details here: https://merlin.allaboutbirds.org/

Note: I'm using the NoIR version of the camera, which means there is no infra-red filter present.  This means that the camera is also picking up IR light in addition to visible light.  So the color balance looks a bit off.
"""
        current_hour = dt.now().hour
        current_weekday = dt.now().weekday()  # 0=Monday, 6=Sunday
        if current_weekday < 5 and 5 <= current_hour < 18:
            publish_at = str(dt.combine(dt.now(), dt.strptime("18:00:00", "%H:%M:%S").time()))
            publish_at = convert_to_utc(publish_at, "America/Los_Angeles")
            privacy_status = "private"
        else:
            publish_at = None
            privacy_status = "public"

        upload_video_wrapper(
            combined_file,
            title=": Nesting Western Bluebirds Exterior Clips",
            description=description,
            privacy_status=privacy_status,
            publish_at=publish_at,
            playlist_name="Hacked Birdhouse Exterior Shots"
        )

    else:
        print("No videos processed.")
    t2 = time.time()
    print(f"Processing completed in {t2 - t1:.2f} seconds.")
