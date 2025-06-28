import argparse
import shutil
import sqlite3
from pathlib import Path
import time
import subprocess
from datetime import datetime as dt, timedelta as td
from birdcam_pipeline_single import process_single_video
from birdcam_pipeline import process_videos_from_day, combine_clips_ffmpeg
from upload_to_youtube import upload_video_wrapper, convert_to_utc
import logging

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler('birdcam.log')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Stream handler (outputs to stdout, which systemd captures)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(stream_formatter)

# Add both handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

class BirdcamProcessor:
    """
    BirdcamProcessor is a class that monitors a directory for new video files,
    catalogs them in a SQLite database, and processes them.
    """

    def __init__(self, staging_dir=None, archive_dir=None, daily_run=False):
        # Directory where the videos are staged
        staging_dir = Path(staging_dir)
        self.staging_dir = staging_dir / "staging"
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Directory where the processed videos will be saved
        self.processed_dir = staging_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Directory where the processed videos will be archived
        self.archive_dir = Path(archive_dir)

        # SQLite database file
        if daily_run:
            self.db_path = staging_dir / "birdcam_daily_catalog.db"
        else:
            self.db_path = staging_dir / "birdcam_catalog.db"

        self.initialize_database()
        self.connect_to_db()

    def __del__(self):
        self.close_db()

    def connect_to_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close_db(self):
        self.conn.close()

    # Initialize SQLite database
    def initialize_database(self):
        self.connect_to_db()
        # Create the files table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_name TEXT PRIMARY KEY,
                status TEXT
            )
        """)
        # Create the daily_runs table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_runs (
                run_date TEXT PRIMARY KEY
            )
        """)
        # Create a table to track youtube uploads
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS youtube_uploads (
                video_name TEXT PRIMARY KEY,
                upload_date TEXT
            )
        """)
        # Create a table to track hourly youtube uploads
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_youtube_uploads (
                date TEXT,
                hour INTEGER
            )
        """)
        # Create a simple table to track the publish delay time
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS publish_delay (
                id INTEGER PRIMARY KEY,
                delay_time INTEGER
            )
        """)
        self.conn.commit()
        self.close_db()

    # Catalog a new file in the database
    def catalog_file(self, file, status="new"):
        file_name = file.name
        self.connect_to_db()
        self.cursor.execute("INSERT OR IGNORE INTO files (file_name, status) VALUES (?, ?)", (file_name, status))
        self.conn.commit()
        self.close_db()

    def check_file_status(self, file):
        file_name = file.name
        self.connect_to_db()
        self.cursor.execute("SELECT status FROM files WHERE file_name = ?", (file_name,))
        result = self.cursor.fetchone()
        self.close_db()
        return result[0] if result else None

    # Update the status of a file in the database
    def update_file_status(self, file, status):
        file_name = file.name
        self.connect_to_db()
        self.cursor.execute("UPDATE files SET status = ? WHERE file_name = ?", (status, file_name))
        self.conn.commit()
        self.close_db()

    # Get staged files from DB
    def get_staged_files(self):
        self.connect_to_db()
        self.cursor.execute("SELECT file_name FROM files WHERE status = 'staged'")
        staged_files = sorted([self.staging_dir / row[0] for row in self.cursor.fetchall()])
        self.close_db()
        return staged_files

    def catalog_new_files(self):
        # Check for new files in the staging directory
        for file in sorted(self.staging_dir.glob("*.mp4")):
            if not self.check_file_status(file):
                # New file detected
                try:
                    self.catalog_file(file)
                    self.update_file_status(file, "staged")
                except Exception as e:
                    logger.error(f"Error cataloging file {file}: {e}")
                    self.update_file_status(file, "failed")
                    continue

    def sync_files(self, source, destination):
        """
        Sync files using rsync.
        Args:
            source (Path): Source directory or file.
            destination (Path): Destination directory.
        """
        try:
            result = subprocess.run(
                ["rsync", "-av", str(source), str(destination)],
                check=True,
                text=True,
                capture_output=True
            )
            logger.info(f"Rsync completed successfully: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during rsync: {e.stderr}")

    def sync_processed_files(self, day):
        """
        Sync processed files to the archive directory.
        """
        try:
            processed_files = self.processed_dir / day.strftime("%Y%m%d")
            archive_path = self.archive_dir / "processed"
            archive_path.mkdir(parents=True, exist_ok=True)
            self.sync_files(processed_files, archive_path)
            logger.info(f"Moved processed files for {day} to archive!")
            return True
        except Exception as e:
            logger.error(f"Error moving processed files to archive for {day}: {e}")
            return False

    def process_new_files(self, skip_bird_detection=False):
        # Check for staged files
        staged_files = self.get_staged_files()
        for file in staged_files:
            # Process the file
            logger.info(f"Processing {file}...")
            try:
                output_dir = process_single_video(file, 
                                    self.processed_dir, 
                                    output_rate=2, 
                                    confidence_threshold=0.3,
                                    skip_bird_detection=skip_bird_detection)
                if output_dir is None:
                    logger.info(f"Video file {file} is zero langth. Skipping...")
                    self.update_file_status(file, "failed")
                else:
                    # After processing, update the status
                    logger.info(f"Processed {file} successfully.")
                    self.update_file_status(file, "processed")
            except Exception as e:
                logger.error(f"Error processing file {file}: {e}")
                self.update_file_status(file, "failed")

    def process_hourly_combined_file(self, day, hour):
        """
        Process the hourly combined file for the given day and hour.
        Args:
            day (datetime.date): The date for which to process the hourly combined file.
            hour (int): The hour of the day (0-23) for which to process the file.
        """
        logger.info(f"Processing hourly combined video for {day} at hour {hour}...")
        try:
            # Pull files from the archive to the processed directory
            date_dir = self.archive_dir / "processed" / day.strftime("%Y%m%d")

            # Combine all clips into a single video
            combined_file = date_dir / f"{day.strftime('%Y%m%d')}_combined_bird_clips_{hour:02d}.mp4"
            if not combined_file.exists():
                combine_clips_ffmpeg(
                    date_dir / "annotated_clips",
                    [combined_file],
                    hour=hour)
            else:
                logger.info(f"Combined file {combined_file} already exists. Skipping processing.")

            logger.info(f"Processing for {day} at hour {hour} completed!")
            return combined_file
        except Exception as e:
            logger.error(f"Error processing hourly combined file for {day} at hour {hour}: {e}")
            return None

    def process_daily_combined_file(self, day):

        # Process daily video.
        logger.info(f"Processing daily combined video for {day}...")
        try:
            # Pull files from the archive to the processed directory
            date_dir_archive = self.archive_dir / "processed" / day.strftime("%Y%m%d") / "annotated_clips"
            date_dir = self.processed_dir / day.strftime("%Y%m%d")
            self.sync_files(date_dir_archive, date_dir)

            # Combine all clips into a single video
            combined_files = [
                date_dir / f"{day.strftime('%Y%m%d')}_combined_bird_clips_AM.mp4",
                date_dir / f"{day.strftime('%Y%m%d')}_combined_bird_clips_PM.mp4"
            ]
            combine_clips_ffmpeg(
                date_dir / "annotated_clips",
                combined_files)
            
            # Record the daily run in the database
            # Check if both combined files exist
            if any(combined_file.exists() for combined_file in combined_files):
                self.record_daily_run(str(day))
                logger.info(f"Processing for {day} completed!")
                return combined_files
            else:
                logger.error(f"Error processing daily combined file for {day}")
                return None
        except Exception as e:
            date_dir = self.processed_dir / day.strftime("%Y%m%d")
            combined_files = [
                date_dir / f"{day.strftime('%Y%m%d')}_combined_bird_clips_AM.mp4",
                date_dir / f"{day.strftime('%Y%m%d')}_combined_bird_clips_PM.mp4"
            ]
            for combined_file in combined_files:
                if combined_file.exists():
                    combined_file.unlink()
            logger.error(f"Error processing daily combined file for {day}: {e}")
            return None        

    def get_processing_stats(self):
        self.connect_to_db()

        # Get the number of files processed
        self.cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'processed'")
        processed_count = self.cursor.fetchone()[0]

        # Get the number of files staged
        self.cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'staged'")
        staged_count = self.cursor.fetchone()[0]

        # Get the number of files failed
        self.cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'failed'")
        failed_count = self.cursor.fetchone()[0]

        # Get the number of files in the database
        self.cursor.execute("SELECT COUNT(*) FROM files")
        total_count = self.cursor.fetchone()[0]

        self.close_db()

        logger.info(f"Total files in database: {total_count} as of {dt.now()}")
        logger.info(f"Files staged: {staged_count}")
        logger.info(f"Files processed: {processed_count}")
        logger.info(f"Files failed: {failed_count}")

    def has_daily_run(self, run_date):
        """
        Check if a daily combined file has already been processed for the given date.
        Args:
            run_date (str): The date to check (format: YYYY-MM-DD).
        Returns:
            bool: True if the date exists in the `daily_runs` table, False otherwise.
        """
        self.connect_to_db()
        self.cursor.execute("SELECT 1 FROM daily_runs WHERE run_date = ?", (run_date,))
        result = self.cursor.fetchone()
        self.close_db()
        return result is not None
    
    def has_hourly_youtube_upload_run(self, date, hour):
        """
        Check if an hourly YouTube upload has already been processed for the given video name, date, and hour.
        Args:
            date (str): The date of the upload (format: YYYY-MM-DD).
            hour (int): The hour of the upload (0-23).
        Returns:
            bool: True if the upload exists in the `hourly_youtube_uploads` table, False otherwise.
        """
        self.connect_to_db()
        self.cursor.execute("SELECT 1 FROM hourly_youtube_uploads WHERE date = ? AND hour = ?",
                            (date, hour))
        result = self.cursor.fetchone()
        self.close_db()
        return result is not None

    def record_daily_run(self, run_date):
        """
        Record a daily combined file processing run for the given date.
        Args:
            run_date (str): The date to record (format: YYYY-MM-DD).
        """
        self.connect_to_db()
        self.cursor.execute("INSERT OR IGNORE INTO daily_runs (run_date) VALUES (?)", (run_date,))
        self.conn.commit()
        self.close_db()

    def upload_to_youtube_channel(self, video_file, title=": Nesting Western Bluebirds", publish_at=None):
        """
        Upload a video file to YouTube.
        Args:
            video_file (Path): Path to the video file to upload.
        """

        try:
            if publish_at:
                # This will only be private until the publish_at time
                logger.info(f"Video will be published at {publish_at} UTC.")
                publish_at = convert_to_utc(publish_at, "America/Los_Angeles")
                privacy_status = "private"
            else:
                logger.info("Video set to public.")
                publish_at = None
                privacy_status = "public"

            upload_video_wrapper(
                str(video_file), 
                title=title,
                publish_at=publish_at,
                privacy_status=privacy_status
            )

            logger.info(f"Uploaded video {video_file} to YouTube!")

            # Record the upload in the database
            self.connect_to_db()
            self.cursor.execute("INSERT OR IGNORE INTO youtube_uploads (video_name, upload_date) VALUES (?, ?)",
                                (video_file.name, dt.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.conn.commit()
            self.close_db()
            return True
        except Exception as e:
            logger.error(f"Error uploading video {video_file} to YouTube: {e}")
            return False
        
    def convert_hour_number_to_12_hour_format(self, hour):
        """
        Convert a 24-hour format hour to a 12-hour format with AM/PM.
        Args:
            hour (int): Hour in 24-hour format (0-23).
        Returns:
            str: Hour in 12-hour format with AM/PM.
        """
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"
    
    def process_and_upload_hourly_combined_file(self, day, hour):
        """
        Process and upload the hourly combined file for the given day and hour.
        Args:
            day (datetime.date): The date for which to process the hourly combined file.
            hour (int): The hour of the day (0-23) for which to process the file.
        """
        # Check if the process has already run for yesterday
        if self.has_hourly_youtube_upload_run(day, hour):
            logger.info(f"Hourly combined file processing has already run for {day}.")
        else:
            logger.info(f"Processing hourly combined file for {day} at hour {hour}...")
            combined_file = self.process_hourly_combined_file(day, hour)
            if combined_file.exists():
                # If we have a new hourly combined file, upload it to Youtube.
                am_pm_hour = self.convert_hour_number_to_12_hour_format(hour)
                title = f" {am_pm_hour}: Nesting Western Bluebirds"

                # Between the hours of 6am and 6pm, set publish_at to 6pm
                # But only during weekdays (Monday to Friday)
                current_hour = dt.now().hour
                current_weekday = dt.now().weekday()  # 0=Monday, 6=Sunday
                if current_weekday < 5 and 6 <= current_hour < 18:
                    # If we publish multiple videos at 6pm, we want to stagger them
                    # by 1 minute each, so they aren't displayed out of order.
                    publish_at = dt.combine(dt.now(), dt.strptime("18:00:00", "%H:%M:%S").time())
                    
                    # Get the publish delay time from the database
                    self.connect_to_db()
                    self.cursor.execute("SELECT delay_time FROM publish_delay WHERE id = 1")
                    if self.cursor.fetchone() is None:
                        # If the delay_time is not set, initialize it to 0
                        self.cursor.execute("INSERT INTO publish_delay (id, delay_time) VALUES (1, 0) ON CONFLICT(id) DO UPDATE SET delay_time = 0")
                        self.conn.commit()
                        delay_time = 0
                    else:
                        delay_time = self.cursor.fetchone()[0]
                    self.close_db()
                    
                    publish_at += td(seconds=delay_time)

                    # Update the delay time in the database for the next video
                    self.connect_to_db()
                    self.cursor.execute("UPDATE publish_delay SET delay_time = ? WHERE id = 1", (delay_time + 1,))
                    self.conn.commit()
                    self.close_db()

                    publish_at = str(publish_at)
                else:
                    publish_at = None
                    # Set the delay time to 0 in the database
                    self.connect_to_db()
                    self.cursor.execute("UPDATE publish_delay SET delay_time = 0 WHERE id = 1")
                    self.conn.commit()
                    self.close_db()

                # Upload the combined video to YouTube
                check = self.upload_to_youtube_channel(
                    combined_file, 
                    title=title,
                    publish_at=publish_at)
                
                if check:
                    # Record the hourly run in the database
                    self.connect_to_db()
                    self.cursor.execute("INSERT OR IGNORE INTO hourly_youtube_uploads (date, hour) VALUES (?, ?)",
                                        (day.strftime("%Y-%m-%d"), hour))
                    self.conn.commit()
                    self.close_db()
                    logger.info(f"Successfully uploaded hourly combined file for {day} at hour {hour} to YouTube.")
                else:
                    logger.error(f"Failed to upload hourly combined file for {day} at hour {hour}")
                    

    def process_and_upload_daily_combined_file(self, day, process_hour=3, publish_hour=5):
        # Check if we are at least 6 hours into the next day.  If so, process 
        # the daily combined file.
        now = dt.now()
        if now.hour >= process_hour:
            # Check if the process has already run for yesterday
            if self.has_daily_run(str(day)):
                logger.info(f"Daily combined file processing has already run for {day}.")
            else:
                logger.info(f"Processing daily combined file for {day}...")
                combined_files = self.process_daily_combined_file(day)
                for combined_file in combined_files:
                    if combined_file.exists():
                        # If we have a new daily combined file, upload it to Youtube.   
                        now = dt.now()
                        if now.hour >= publish_hour:
                            publish_at = None
                        else:
                            publish_at = str(dt.combine(dt.now(), dt.strptime(f"{publish_hour}:00:00", "%H:%M:%S").time()))

                        if combined_file.name.endswith("_AM.mp4"):
                            title = f"AM: Nesting Western Bluebirds"
                        elif combined_file.name.endswith("_PM.mp4"):
                            title = f"PM: Nesting Western Bluebirds"
                        else:
                            title = ": Nesting Western Bluebirds"

                        # Upload the combined video to YouTube
                        # TODO: Catch when this fails and log it
                        check = self.upload_to_youtube_channel(
                            combined_file, 
                            title=title,
                            publish_at=publish_at)
                        if check:
                            logger.info(f"Successfully uploaded daily combined file for {day} to YouTube.")
                        
                            # Remove annotated clips after processing the daily combined file
                            logger.info(f"Removing annotated clips for {day}...")
                            annotated_clips_dir = combined_file.parent / "annotated_clips"
                            if annotated_clips_dir.exists():
                                try:
                                    shutil.rmtree(annotated_clips_dir)
                                    logger.info(f"Deleted annotated clips for {day}.")
                                except Exception as e:
                                    logger.error(f"Error deleting annotated clips for {day}: {e}")
                        else:
                            logger.error(f"Failed to upload daily combined file for {day} to YouTube.")

                    else:
                        logger.info("No new daily combined file to process.")

    def delete_old_processed_files(self, day):
        # Delete the processed files for the specified day to save disk space.
        logger.info(f"Deleting processed files for {day} if they exist...")
        day_dir = self.processed_dir / day.strftime("%Y%m%d")
        if day_dir.exists():
            try:
                shutil.rmtree(day_dir)
                logger.info(f"Deleted processed files for {day}.")
            except Exception as e:
                logger.error(f"Error deleting processed files for {day}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam videos as they come in from the Pi Zero")
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
    parser.add_argument(
        "-d", "--process_daily_file",
        required=False,
        default=False,
        action='store_true',
        help="Process the daily combined file."
    )
    parser.add_argument(
        "-s", "--skip_bird_detection",
        required=False,
        default=False,
        action='store_true',
        help="Skip bird detection and only annotate existing clips."
    )
    args = parser.parse_args()

    staging_dir = Path(args.input_path)
    archive_dir = Path(args.archive_path)
    process_daily_file = args.process_daily_file
    skip_bird_detection = args.skip_bird_detection

    processor = BirdcamProcessor(staging_dir, archive_dir)

    # Monitor the staging directory for new files
    # TODO: Perhaps use a service/timer to check for new files instead of a while loop
    while True:
        processor.catalog_new_files()
        processor.process_new_files(skip_bird_detection=skip_bird_detection)

        now = dt.now()
        today = now.date()
        yesterday = today - td(days=1)
        two_days_ago = today - td(days=2)

        # Sync processed files to the archive directory
        check = processor.sync_processed_files(today)

        if process_daily_file:
            processor.process_and_upload_daily_combined_file(yesterday)

        # Sync processed files to the archive directory
        processor.sync_processed_files(yesterday)

        processor.delete_old_processed_files(two_days_ago)

        time.sleep(60 * 5)  # Check every 5 minutes
