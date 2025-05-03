# Birds!

This code is intended to be run on a Raspberry Pi and associated camera module mounted inside of a birdhouse in the hopes of observing a nesting pair of birds.  Videos here:
https://www.youtube.com/@HackedBirdhouse

>**_Disclaimer/Note:_**
Weather sealing up the Pi inside the birdhouse, and running power, etc., can be a challenge.  Please research this on your own to come up with a safe and viable solution.  What worked for me, may not work in all scenarios.  I make no assertions or guarantees about safety!

I based the initial version off of the project listed here:

https://projects.raspberrypi.org/en/projects/infrared-bird-box/

However, some modifications were needed to be compatible with the most recent version of Raspberry Pi OS and the camera module v3, which I'll discuss below.

There are two bash scripts which are used to record the video, and a set of python scripts which are used (on a separate machine, i.e. not the birdcam Pi) to post process the videos.

>**Note**: This is a work in progress, so I'll try to fill in more details in this guide.  But for now, this gives a general idea of the setup.  Later, I'll post some pictures and video of the build process.

## Hardware

The hardware I'm using for this setup is as follows:

* [Raspberry Pi Zero 2W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/) with headers soldered on.
* [Raspberry Pi Camera Module v3 NoIR Wide](https://www.raspberrypi.com/products/camera-module-3/)
* [Pi Zero case](https://www.raspberrypi.com/products/micro-usb-male-to-usb-a-female-cable/)
* [Raspberry Pi micro USB power supply](https://www.raspberrypi.com/products/micro-usb-power-supply/)
* [USB Microphone](https://www.sparkfun.com/usb-2-0-mini-microphone-dongle.html) + [micro USB to USB-A adapter](https://www.raspberrypi.com/products/micro-usb-male-to-usb-a-female-cable/)
* 2x 850nm IR LEDs (for night vision!)
* 2x 220 ohm resistors (for use with the LEDs)
* A very long extension cord.

Check out the linked [project instructions](https://projects.raspberrypi.org/en/projects/infrared-bird-box/) for details on how to wire up the LED and general guidance on the concept.  However, for the specifics of this particular setup, see below.

### The Pi

You can choose just about any model of Raspberry Pi that supports a camera module. However, the Zero line of Pis is more than capable for this task. The Zero 2W in particular, I found, is capable of recording 1080p video at 30 frames per seconds. I recommend installing the latest version of Raspberry Pi OS Lite. The "Lite" version is "headless", meaning that it won't include the desktop interface. But since this will be running inside a birdhouse, you won't need that. In addition, the lite version will consume far less resources, which will allow for better video streaming, etc.

The Pi Zero 2W also has a few other advantages.  Namely that it's smaller, which will be useful when mounting it inside the birdhouse.  It is also much much cheaper (around $15 at present).  Make sure to get the "2W" variant, as opposed to the "2".  The "W" indicates that it includes a wifi (and also bluetooth) module, which you will need for this project in order to retrieve data and log in remotely, etc.

Note: Even with the older Pi Zero W (or older Pis in general) it should still be possible to do this.  My initial prototype a few years ago used a Pi Zero W (1st gen) and a v2 camera module, and I was still able to stream at 720p.

### The Camera

The guide above uses a v2 camera which requires some modification.  However, here I went with the Camera Module v3 NoIR Wide variant.  I highly recommend the v3 because you'll avoid having to modify the focal length of the camera.  
"NoIR" means that there is no IR filter on the camera, which means that it will be sensitive to infra-red light.  This, along with the IR LEDs, means that we can see in the dark, without disturbing the birds since IR light is invisible to birds (and us humans).  Again, check out that guide on the official raspberry pi website for details.  
The "Wide" indicator means that we are using the wide-angle version of the camera (new to the v3 lineup).  I went with the wide angle version because it has the ability to focus much closer to the lens.  It can focus on objects as little as 5cm from the lens, which will be very useful in close quarters.  The v3 cameras also have autofocus, which helps a lot.

### Other Hardware

Again, check out that guide for the LED wiring. The GPIO pinout is the same for all "B" type and "Zero" type Raspberry Pis, so that guide is applicable in all cases. Don't forget the 220 ohm resistor or you could fry the LED!

In my case, I wired two of the LED + resistor combos in parallel on a small breadboard to increase the brightness at night.

I used the official case for the Pi Zero because it comes with a very short camera ribbon cable which you'll need, and it also comes with a few different lids, one of which exposes the GPIO pins, which you'll need for the LEDs.

The USB microphone is nice if you want to hear the birds, but not strictly necessary. The code in this repo assumes that the microphone is present. But with some slight modifications you could omit that.

## Accessing the Pi

*Before* deploying the birdhouse/pi/camera out into the wild, make sure that you've connected it to your wifi and that you can access it via ssh over your network.  Once it’s in the birdhouse you likely won’t be able to physical access it, so you’ll need to do everything remotely.  When you set up the Pi with the Raspberry Pi Imager app (from your Mac or Windows machine) you can set up ssh access at that time. You can also give it a unique hostname and username and password in the Imager app.

Then, any time you need to log into the pi, launch a terminal on your local machine and type:
```
ssh <your_birdcam_hostname>
```
where you can run the script, copy files, etc.  You can also copy video files from your Pi to your local machine like so.  Open a terminal on your local machine and type something like:
```
rsync -azv <your_birdcam_hostname>:/path/to/videos/*.mp4 /local/path/to/save/videos/
```


## Software

### birdcam_stream.bash

This does the main work of recording from the camera and saving to disk (or optionally streaming to youtube if you want to set that up).

This again differs from the official guide above (which uses an older camera API).  Here the script uses the newer ["rpicam-vid" and associated utilities](https://www.raspberrypi.com/documentation/computers/camera_software.html), and has some really nice features.

The script can be called like so:

```
birdcam_stream.bash -o output_file.mp4 -t 60 -a
```

The `-o` specifies the output file.  The `-t` indicates the number of seconds to record.  The `-a` indicates that you want audio included.  If you don't want audio, just leave off the `-a`.  

Checkout the details of the script for the specifics of the rpicam-vid command.

Note: The YouTube streaming is also discussed in the guide linked above.  This requires some setup on your youtube channel to set up a streaming key.  I won't go into details here, but it can be fun to do if you want to try it out.  However, due to bandwidth limitations that I ran into, I wasn't able to get it to stream reliably.  Namely the Pi is outside and far from my router, so the connection can be spotty.

### birdcam_runner.bash

This script wraps birdcam_stream.bash and uses it to continuously create 30 minute videos of the inside of the birdhouse.  You can either start this manually just by running the script.  Or you can set it to run via a cron job or by setting up a service on the Pi.

This script also does an rsync to another Raspberry Pi that I have set up in the house for video archiving and post processing.  More on that later.  It also checks available disk space (on the SD card), and if it's over 50% it deletes the oldest video.  Video files are large, so this can fill up quickly.  This keeps the disk usage down and allows time to copy the files off before that happens.

### Archiving to another Pi

I found it beneficial to automate pushing files to another Raspberry Pi that I have on my network.  This can be any Pi really, no need to break the bank.  I'm using a Raspberry Pi 5 and an external hard drive plugged in for storage.  The birdcam_runner.bash script running on the Pi Zero 2W does an rsync down to the Pi 5 after each video file is created.

### Post Processing

#### Annotating, reencoding:
The Pi Zero does a pretty good job of recording and encoding the videos.  However, I found that it sometimes drops a few frames, which can lead to problems in playback in certain software.  Reencoding the video and forcing a constant frame rate fixes this issue.  In addition, I wanted to overly an annotation showing the date and time in the lower left corner of the video.  The Pi Zero has limited resources so I didn't want to add this additional burden to it.  
The Pi 5 handles these jobs by running the `annotate_video.py` script against each video file.

#### Finding Birds:
As you might expect, the birds may not always be in the birdhouse.  This was especially the case when I first installed the birdhouse in the back yard.  In fact it took about two months for a pair of birds to decide to move in.  And now that they are there building their nest, they are only in there a few hours out of the day.  So there is a lot of boring video of an empty birdhouse!  

To make the footage more interesting, I put together a script which uses pytorch, and a YoloV5 machine learning model to identify any time the bird(s) are present in the birdhouse.  This code is in the `find_birds.py` script.  It parses through the videos and identifies time stamps where birds are present, and then saves a set of video clips.  The code then combines these clips into a daily-highlights video.

This again, runs on the Pi 5, not on the Pi Zero in the birdhouse.  It’s very compute intensive, so you’ll want to run this either on another Pi as I have, or on your Mac/Linux/Windows machine.

#### Putting it all together:
The `birdcam_pipeline.py` script ties it all together, first annotating, reencoding, finding the birds, and creating the highlights video.

You can run that script like so:
```
python birdcam_pipeline.py -d <date> -i <input_path> -o <output_path>
```