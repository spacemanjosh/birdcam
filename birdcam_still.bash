#!/bin/bash

# This script captures still images from a Raspberry Pi camera.
# -o <output> : Specify the output file name.

# Directory where this bash script exists.
script_dir=$(dirname "$0")

# Directory to save still images
output_dir="$script_dir/stills"

# Parse command line arguments.
while getopts "o:" opt; do
    case $opt in
        o) output_file="$OPTARG"
           if [ -z "$output_file" ]; then
               echo "Output file name is required."
               exit 1
           fi
        ;;
        \?) echo "Invalid option -$OPTARG" >&2
            exit 1
        ;;
    esac
done

rpicam-still --raw --output $output_file
if [ $? -ne 0 ]; then
    echo "Failed to capture still image."
    exit 1
fi
echo "Still image captured: $output_file"
