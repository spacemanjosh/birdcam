import sqlite3
from datetime import datetime as dt
from pathlib import Path
import argparse


def connect_to_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def close_db(conn):
    conn.close()

def get_processing_stats(self):
    conn, cursor = connect_to_db()

    # Get the number of files processed
    cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'processed'")
    processed_count = cursor.fetchone()[0]

    # Get the number of files staged
    cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'staged'")
    staged_count = cursor.fetchone()[0]

    # Get the number of files failed
    cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'failed'")
    failed_count = cursor.fetchone()[0]

    # Get the number of files in the database
    cursor.execute("SELECT COUNT(*) FROM files")
    total_count = cursor.fetchone()[0]

    self.cursor.execute("SELECT * FROM daily_runs")
    daily_runs = self.cursor.fetchall()

    close_db(conn)

    print(f"Total files in database: {total_count} as of {dt.now()}")
    print(f"Files staged: {staged_count}")
    print(f"Files processed: {processed_count}")
    print(f"Files failed: {failed_count}")
    print(f"Daily runs: {daily_runs}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print processing statistics from the database.")
    parser.add_argument("-d", "--db_path", type=str, required=True, help="Path to the database file.")
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    
    if not db_path.exists():
        raise FileNotFoundError(f"The database file {db_path} does not exist.")
    
    get_processing_stats(db_path)
    