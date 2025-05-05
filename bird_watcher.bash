#!/bin/bash

# Directory to watch (where Pi Zero 2W syncs files)
WATCH_DIR="/bird_drive/recordings"

# Output directory for processed files
OUTPUT_DIR="/bird_drive/processed"

# Log file for debugging
LOG_FILE="/bird_drive/processing.log"

# Activate the Python virtual environment
conda activate birdcam

# Get into the directory where this script is located
cd ~/git/birdcam

# Start monitoring the directory
echo "Monitoring directory: $WATCH_DIR" >> "$LOG_FILE"
inotifywait -m -e close_write --format '%w%f' "$WATCH_DIR" | while read NEW_FILE
do
    # Log the new file
    echo "$(date): Detected new file: $NEW_FILE" >> "$LOG_FILE"

    # Check if the new file is a video file
    if [[ "$NEW_FILE" == *.mp4 || "$NEW_FILE" == *.mov ]]; then
        echo "$(date): Processing file: $NEW_FILE" >> "$LOG_FILE"

        # Run the birdcam_pipeline_single.py script
        python birdcam_pipeline_single.py -i "$NEW_FILE" -o "$OUTPUT_DIR" >> "$LOG_FILE" 2>&1

        echo "$(date): Finished processing file: $NEW_FILE" >> "$LOG_FILE"
    else
        echo "$(date): Skipped non-video file: $NEW_FILE" >> "$LOG_FILE"
    fi
done
