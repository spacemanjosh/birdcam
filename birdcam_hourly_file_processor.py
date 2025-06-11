from pathlib import Path
import argparse
from datetime import datetime as dt, timedelta as td, date
from birdcam_continuous_pipeline import BirdcamProcessor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam hourly videos.")
    parser.add_argument(
        "-i", "--input_path",
        required=True,
        help="Path to the directory containing the videos."
    )
    parser.add_argument(
        "-a", "--archive_path",
        required=True,
        help="Path to the directory where the output will be saved."
    )
    args = parser.parse_args()

    staging_dir = staging_dir = Path(args.input_path)
    archive_dir = archive_dir = Path(args.archive_path)

    # Check for the last processed hourly file
    processed_dir = archive_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    last_processed_file = sorted(processed_dir.glob("202*/*.mp4"))
    last_processed_file = [f for f in last_processed_file if not f.name.startswith("._")][-1]

    # Get the last processed date and hour from a file that looks like 20250610_combined_bird_clips_05.mp4
    last_processed_date = dt.strptime(last_processed_file.stem.split("_")[0], "%Y%m%d").date()
    last_processed_hour = int(last_processed_file.stem.split("_")[-1])

    # If the last processed hour is 23, increment the date
    if last_processed_hour == 23:
        start_date = last_processed_date + td(days=1)
        start_hour = 0
    else:
        start_date = last_processed_date
        start_hour = last_processed_hour + 1
    start_time = dt(start_date.year, start_date.month, start_date.day, start_hour, 0, 0)

    # Process up to 3 hours ago
    now = dt.now()
    if now.hour >= 3:
        end_date = now.date()
        end_hour = now.hour - 3
    else:
        end_date = now.date() - td(days=1)
        end_hour = 23 + now.hour - 3
    end_time = dt(end_date.year, end_date.month, end_date.day, end_hour, 0, 0)

    # Ensure the start date and hour are before the end date and hour
    if end_time < start_time:
        print("No new hours to process.")
        exit(0)

    processor = BirdcamProcessor(staging_dir, archive_dir, daily_run=True)
    # Process each hour from start_time to end_time
    current_time = start_time
    while current_time <= end_time:
        day = current_time.date()
        hour = current_time.hour
        print(f"Processing {day} hour {hour} combined file...")
        
        # Process the hourly combined file
        # Uncomment the next line if you want to process without uploading
        # processor.process_hourly_combined_file(day, hour)
        
        # Process and upload the hourly combined file
        processor.process_and_upload_hourly_combined_file(day, hour)
        
        # Move to the next hour
        current_time += td(hours=1)
