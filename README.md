# WAVExtender

A Python script for extending .wav files with sample chunks. 

There are two extension modes:

* **By length** - Length in seconds. Extend audio to the desired length. The audio will loop until it reaches the target length however the audio wont be cut at the exact length and instead will wait for last looped part to finish.

* **N times** - Repeat the looped part N times.

## Why?
I was researching how to extend video game music because i was tired of YouTube taking down my favorite music channels.

I strongly recommend using **[vgmstream](https://vgmstream.org/)** which can do what this script does and more.

## Requirements
* FFmpeg in your PATH
* A .wav file with a [sample chunk (smpl)](https://www.recordingblogs.com/wiki/sample-chunk-of-a-wave-file)

## How to run
```
python WAVExtender.py -t TYPE [-n TIMES] [-l LENGTH] -i INPUT -o OUTPUT
```

| Argument | Description |
|---|---|
| -t TYPE <br> --type TYPE | Extension Type (1 for N times and 2 for length) |
| -n TIMES <br> --number TIM | Number of loops. Only available when type equals 1. |
| -l LENGTH <br> --length LENG | Desired length. Only available when type equals 2. |
| -i INPUT <br> --input INP | Path to input file. Must be a .wav file. |
| -o OUTPUT <br> --output OUTP | Where to save the extended file. Input file won't be modified. |
| -h | Display help message |
