#!/bin/bash

# Directory where this bash script exists
script_dir=$(dirname "$0")

# Directory to save recordings
output_dir="$script_dir/recordings"
max_usage=50

# Backup server details
backup_server="birdserver"
backup_dir="/bird_drive/recordings"

# Function to check disk usage
check_disk_usage() {
  local usage=$(df -h "$output_dir" | awk 'NR==2 {print $5}' | sed 's/%//')
  if [ "$usage" -ge $max_usage ]; then
    echo "Disk usage has exceeded $max_usage%. Overwriting the oldest file."
    delete_oldest_file
    return 1
  fi
  return 0
}

# Function to delete the oldest file
delete_oldest_file() {
  local oldest_file=$(ls -t "$output_dir" | tail -1)
  if [ -n "$oldest_file" ]; then
    rm "$output_dir/$oldest_file"
    echo "Deleted oldest file: $oldest_file"
  fi
}

# Function to create a timestamped file name
create_filename() {
  local timestamp=$(date +"%Y%m%d_%H%M%S")
  echo "$output_dir/birdcam_$timestamp.mp4"
}

create_still_filename() {
  local timestamp=$(date +"%Y%m%d_%H%M%S")
  echo "$output_dir/birdcam_$timestamp.jpg"
}

# Before starting the main loop, rsync the existing files to the backup server.
# This is sometimes necessary if we've lost internet connectivity.  This way
# it can still continue to record and we can recover the files later.
rsync -avz $output_dir/ $backup_server:$backup_dir/

# Main loop to make half-hourly recordings
while true; do

  # Check for the existence of the stop_streaming file
  if [ -f "$output_dir/stop_streaming" ]; then
    echo "Stop streaming file found. Exiting."
    rm $output_dir/stop_streaming
    exit 0
  fi

  if ! check_disk_usage; then
    continue
  fi
  output_file=$(create_filename)
  $script_dir/birdcam_stream.bash -o "$output_file" -t 1800 -a

  # rsync the file to the backup server
  rsync -avz "$output_file" $backup_server:$backup_dir/
done
