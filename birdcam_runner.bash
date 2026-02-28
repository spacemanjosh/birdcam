#!/bin/bash

# Directory where this bash script exists
script_dir=$(dirname "$0")

# Directory to save recordings
output_dir="$script_dir/recordings"
hold_dir="$script_dir/sent"
max_usage=50

# Function to check disk usage
check_disk_usage() {
  local usage=$(df -h "$hold_dir" | awk 'NR==2 {print $5}' | sed 's/%//')
  if [ "$usage" -ge $max_usage ]; then
    echo "Disk usage has exceeded $max_usage%. Overwriting the oldest file."
    delete_oldest_file
    return 1
  fi
  return 0
}

# Function to delete the oldest file
delete_oldest_file() {
  local oldest_file=$(find "$hold_dir" -type f -printf '%T+ %p\n' | sort | head -n 1 | awk '{print $2}')
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

in_time_window() {
    now=$(date +%H:%M)

    # Simple string comparison works because format is HH:MM
    if [[ "$now" > "$START_TIME" && "$now" < "$STOP_TIME" ]]; then
        return 0
    else
        return 1
    fi
}

logfile="$script_dir/birdcam_stream_debug.log"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$logfile"
}

log "===== Starting script ====="

# Check CPU temp and cool down if needed.
# THRESHOLD=80.0
# while true; do
#     temp=$(vcgencmd measure_temp | grep -oP '[0-9]+\.[0-9]+')
#     log "Current temp: $temp°C"

#     # Use awk to compare floating point numbers
#     if awk "BEGIN {exit !($temp > $THRESHOLD)}"; then
#         log "🔥 CPU temperature too high ($temp°C). Sleeping for 10s..."
#         sleep 10
#     else
#         log "✅ Temperature OK. Continuing..."
#         break
#     fi
# done

# Before we get started, rsync the recordings directory
# back to the main server.  This may be necessary if there were
# a network problem that prevented the rsync in the loop below.
log "Sleep for 10 seconds to allow system to stabilize."
sleep 10
log "Starting rsync..."
$script_dir/birdcam_rsync.bash \
    birdnode1 \
    /bird_dropbox/ \
    "$output_dir" \
    "$hold_dir" \
    > >(while IFS= read -r line; do log "[rsync][stdout] $line"; done) \
    2> >(while IFS= read -r line; do log "[rsync][stderr] $line"; done)
rsync_status=$?

if [ $rsync_status -ne 0 ]; then
  log "Rsync failed with exit code: $rsync_status"
else
  log "Finished rsync successfully."
fi

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

START_TIME="05:00"
STOP_TIME="20:00"
SLEEP_NIGHT=300   # sleep 5 min when outside window

if in_time_window; then
    log "In time window. Starting recording..."
else
    log "Outside time window. Sleeping for $SLEEP_NIGHT seconds..."
    sleep $SLEEP_NIGHT
    exit 0
fi

log "Sleep for 10 seconds before starting recording."
sleep 10

output_file=$(create_filename)

log "Taking a still image."
rpicam-still -n --autofocus-window 0.41,0.30,0.22,0.39 --output "${output_file%.mp4}.jpg"
if [ $? -ne 0 ]; then
    log "Failed to capture still image."
else
    log "Still image captured: ${output_file%.mp4}.jpg"
fi

output_file=$(create_filename)
log "Starting recording: $output_file"
$script_dir/birdcam_stream.bash -o "$output_file" -t 600 -a
if [ $? -ne 0 ]; then
    log "Recording failed for: $output_file"
    exit 1
fi
log "Finished recording: $output_file"
