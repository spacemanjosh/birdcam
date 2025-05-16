import argparse
import shutil
import sqlite3
from pathlib import Path
import time
from datetime import datetime as dt, timedelta as td
from birdcam_pipeline_single import process_single_video
from birdcam_pipeline import process_videos_from_day

class BirdcamProcessor:
    """
    BirdcamProcessor is a class that monitors a directory for new video files,
    catalogs them in a SQLite database, and processes them.
    """

    def __init__(self, dropbox_dir=None, staging_dir=None, archive_dir=None):
        self.dropbox_dir = Path(dropbox_dir)
        self.staging_dir = Path(staging_dir)
        self.archive_dir = Path(archive_dir)
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
        # Create the `files` table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_name TEXT PRIMARY KEY,
                status TEXT
            )
        """)
        # Create the `daily_runs` table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_runs (
                run_date TEXT PRIMARY KEY
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

    def copy_to_staging(self, file):
        # Move the file to the staging directory
        staging_path = self.staging_dir / file.name

        try:
            shutil.copy2(file, staging_path)
        except Exception as e:
            print(f"Error moving file {file} to staging: {e}")
            self.update_file_status(file, "failed")
            return
        
        print(f"Moved {file} to {staging_path}")
        self.update_file_status(file, "staged")

    def catalog_new_files(self):
        # Check for new files in the dropbox directory
        for file in self.dropbox_dir.glob("*.mp4"):
            if not self.check_file_status(file):
                # New file detected
                self.catalog_file(file)
                self.copy_to_staging(file)

    def process_files(self):
        # Check for staged files
        for file in self.staging_dir.glob("*.mp4"):
            if self.check_file_status(file) == "staged":
                # Process the file
                print(f"Processing {file}...")
                try:
                    process_single_video(file, 
                                        self.staging_dir / "processed", 
                                        output_rate=2, 
                                        confidence_threshold=0.3)
                except Exception as e:
                    print(f"Error processing file {file}: {e}")
                    self.update_file_status(file, "failed")
                    continue

                # After processing, update the status
                self.update_file_status(file, "processed")

    def process_daily_combined_file(self):
        # Get the current time and date
        now = dt.now()
        today = now.date()
        yesterday = today - td(days=1)

        # Check if we are at least 3 hours into the next day
        if now.hour < 3:
            return

        # Check if the process has already run for yesterday
        if self.has_daily_run(str(yesterday)):
            print(f"Daily combined file processing has already run for {yesterday}.")
            return

        # Process videos from yesterday
        print(f"Processing videos from {yesterday} in {self.staging_dir} and saving to {self.staging_dir / 'processed'}...")
        try:
            process_videos_from_day(
                date=yesterday.strftime("%Y%m%d"),
                video_path=self.staging_dir,
                output_path=self.staging_dir / "processed",
                output_rate=2,
                confidence_threshold=0.3
            )
        except Exception as e:
            print(f"Error processing daily combined file for {yesterday}: {e}")
            return
        print(f"Processing for {yesterday} completed!")

        # Move the processed file to the archive directory
        try:
            processed_files = self.staging_dir / "processed" / yesterday.strftime("%Y%m%d")
            archive_path = self.archive_dir / "processed" / yesterday.strftime("%Y%m%d")
            archive_path.mkdir(parents=True, exist_ok=True)
            shutil.copytree(processed_files, archive_path, dirs_exist_ok=True)
        except Exception as e:
            print(f"Error moving processed files to archive for {yesterday}: {e}")
            return
        print(f"Moved processed files for {yesterday} to archive!")

        # Record the daily run in the database
        self.record_daily_run(str(yesterday))

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

        print(f"Total files in database: {total_count} as of {dt.now()}")
        print(f"Files staged: {staged_count}")
        print(f"Files processed: {processed_count}")
        print(f"Files failed: {failed_count}")

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process birdcam videos as they come in from the Pi Zero")
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
        "-a", "--archive_path",
        required=True,
        help="Path to the directory where the output will be saved."
    )
    args = parser.parse_args()

    dropbox_dir = args.input_path
    staging_dir = args.ouptut_path
    archive_dir = args.archive_path

    processor = BirdcamProcessor(dropbox_dir, staging_dir, archive_dir)

    # Monitor the dropbox directory for new files
    while True:
        processor.catalog_new_files()
        processor.process_files()
        processor.get_processing_stats()
        processor.process_daily_combined_file()
        time.sleep(60 * 5)  # Check every 5 minutes
