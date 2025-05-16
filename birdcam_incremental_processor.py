import shutil
import sqlite3
from pathlib import Path
import time
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
        self.db_path = archive_dir / "birdcam_catalog.db"

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
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_name TEXT PRIMARY KEY,
                status TEXT
            )
        """)
        self.conn.commit()

    # Catalog a new file in the database
    def catalog_file(self, file, status="new"):
        file_name = file.name
        self.cursor.execute("INSERT OR IGNORE INTO files (file_name, status) VALUES (?, ?)", (file_name, status))
        self.conn.commit()

    def check_file_status(self, file):
        file_name = file.name
        self.cursor.execute("SELECT status FROM files WHERE file_name = ?", (file_name,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # Update the status of a file in the database
    def update_file_status(self, file, status):
        file_name = file.name
        self.cursor.execute("UPDATE files SET status = ? WHERE file_name = ?", (status, file_name))
        self.conn.commit()

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

    def process_daily_combined_file(self, date):
        print(f"Processing videos from {date} in {self.staging_dir} and saving to {self.staging_dir / "processed"}...")
        process_videos_from_day(
            date=date,
            video_path=self.staging_dir,
            output_path=self.staging_dir / "processed",
            output_rate=2,
            confidence_threshold=0.3
        )
        print(f"Processing for {date} completed!")

