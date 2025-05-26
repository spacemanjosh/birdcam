#!/bin/bash

# Directory where this bash script exists
script_dir=$(dirname "$0")

# Directory to save recordings
output_dir="$script_dir/recordings"
max_usage=50

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
  local oldest_file=$(find "$output_dir" -type f -printf '%T+ %p\n' | sort | head -n 1 | awk '{print $2}')
  if [ -n "$oldest_file" ]; then
    rm "$oldest_file"
    echo "Deleted oldest file: $oldest_file"
  fi
}

# Function to create a timestamped file name
create_filename() {
  local timestamp=$(date +"%Y%m%d_%H%M%S")
  echo "$output_dir/birdcam_$timestamp.mp4"
}

logfile="$script_dir/birdcam_stream_debug.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$logfile"
}

log "===== Starting script ====="

# Before we get started, rsync the recordings directory
# back to the main server.  This may be necessary if there were
# a network problem that prevented the rsync in the loop below.
log "Sleep for 10 seconds to allow system to stabilize."
sleep 10
log "Starting rsync..."
rsync -av "$output_dir"/*.mp4 homebase:/bird_dropbox/
log "Finished rsync."

# Main loop to make half-hourly recordings
log "Entering disk space check loop..."
while true; do
  if [ -f "$output_dir/stop_streaming" ]; then
    log "Stop file found. Exiting."
    rm "$output_dir/stop_streaming"
    exit 0
  fi

  if ! check_disk_usage; then
    log "Disk full. Deleted a file. Retrying."
    continue
  else
    log "Disk usage OK. Breaking loop."
    break
  fi
done

log "Sleep for 10 seconds before starting recording."
sleep 10

output_file=$(create_filename)
log "Starting recording: $output_file"
$script_dir/birdcam_stream.bash -o "$output_file" -t 600 -a
log "Finished recording: $output_file"
