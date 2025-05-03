#!/bin/bash

# This script captures video from a Raspberry Pi camera and streams it to YouTube or saves it to a file.
# Command line options:
# -o <output> : Specify the output file name. If absent, defaults to streaming to YouTube.
# -t <duration> : Specify the duration of the stream in seconds. If absent, defaults to 0 (no limit).
# -a : Use the default audio device. If absent, defaults to a silent stream.
#

# Default values
output_type="file"
duration=0
audio_device=""
use_audio_device=false
output_option=""
libav_format="flv"

# Directory where this bash script exists.
script_dir=$(dirname "$0")

# Function to detect the correct audio device
detect_audio_device() {
    if arecord -l | grep -q "card 1:"; then
        echo "plughw:1,0"
    elif arecord -l | grep -q "card 0:"; then
        echo "plughw:0,0"
    else
        echo "No audio device found. Defaulting to silent stream."
        echo "/dev/zero"
        $use_audio_device = false
    fi
}

# Parse command line arguments.
while getopts "o:t:a" opt; do
    case $opt in
        o) output_option="$OPTARG"
          libav_format="mp4"
        ;;
        t) duration="$OPTARG"
        ;;
        a) use_audio_device=true
        ;;
        \?) echo "Invalid option -$OPTARG" >&2
            exit 1
        ;;
    esac
done

# Set audio device if -a option is present.
if [ "$use_audio_device" = true ]; then
    audio_device=$(detect_audio_device)
else
    audio_device="/dev/zero"
fi

# Set output options based on the presence of the -o option.
if [ -z "$output_option" ]; then
    output_option="rtmp://a.rtmp.youtube.com/live2/`cat $script_dir/youtubekey.txt`"
    output_type="stream"
fi

# Append "s" to duration if greater than 0. This is necessary for rpicam-vid.
# The default is 0, which means no limit.
if [ "$duration" -gt 0 ]; then
    duration="${duration}s"
fi

# Run the rpicam-vid command with the specified duration and output options
echo "Running rpicam-vid with the following options:"
echo "Duration: $duration"
echo "Audio Device: $audio_device"
echo "Output Option: $output_option"
echo "Libav Format: $libav_format"
echo "Use Audio Device: $use_audio_device"
echo "Output Type: $output_type"

if [ "$use_audio_device" = false ]; then
    if [ "$output_type" = "stream" ]; then
        # In this case we need to pipe to ffmpeg so that we can supply it with a null audio device.
        # This is a silent YouTube stream.
        rpicam-vid -o - -t $duration --width 1920 --height 1080 --framerate 30 | 
            ffmpeg -f h264 -i - \
            -f s16le -ac 1 -ar 44100 -i /dev/zero \
            -c:v copy -c:a aac -f flv $output_option
    else
        # Here we are not using audio, just a silent mp4.
        rpicam-vid -t $duration --nopreview --width 1920 --height 1080 --framerate 30 -b 8000kbps \
            --denoise cdn_off --codec libav \
            --libav-format $libav_format \
            -o $output_option
    fi
else
    # All other cases. This can be either an mp4 with audio or a YouTube stream with audio.
    rpicam-vid -t $duration --nopreview --width 1920 --height 1080 --framerate 30 -b 8000kbps \
        --denoise cdn_off --codec libav --libav-audio \
        --libav-format $libav_format \
        --audio-source alsa \
        --audio-device $audio_device \
        --audio-samplerate 48000 --audio-bitrate 128kbps --audio-channels 1 \
        -o $output_option
fi
