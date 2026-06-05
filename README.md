# Audio Latency Detector

Measures the timing offset between two speakers — typically an internal laptop speaker and a Bluetooth speaker — using short frequency bursts and onset detection. Reports the offset in milliseconds and tells you which speaker to delay in your DAW or system audio settings.

**Requires a split-channel output setup:** the left and right audio channels must be routed to different physical output devices (e.g. left → internal speakers, right → Bluetooth speaker). On macOS this is done with a Multi-Output Device in Audio MIDI Setup combined with a channel-splitting tool such as BlackHole or Loopback. Without this routing, both bursts play through the same device and no offset can be measured.

## How it works

1. Plays a 400 Hz burst on the left channel (internal speaker) and a 700 Hz burst on the right channel (BT speaker) simultaneously, relying on the split-channel routing to send each to a different physical device.
2. Records the result with a nearby microphone.
3. Bandpass-filters each frequency out of the recording, detects each burst's onset, and computes the time difference.
4. Repeats for the configured number of runs, rejects outliers (IQR method), and reports the average offset.

A positive result means the BT speaker is arriving later; a negative result means it arrived earlier than internal.

## Requirements

- macOS (tested) — should work on Linux/Windows with minor path changes
- Python 3.9+
- A microphone placed between both speakers

## Quick start

```bash
# Clone and run — the script handles venv creation automatically
git clone https://github.com/YOUR_USERNAME/audio-latency-detector.git
cd audio-latency-detector
./run.sh           # opens the GUI
```

The first run creates a `.venv` and installs dependencies automatically.

## Usage

### GUI (default)

```bash
./run.sh
# or
./run.sh --gui
```

Select your output device (loopback / multi-output) and mic input, set the number of runs, and click **Run Detection**.

### CLI

```bash
# List available audio devices
./run.sh --list

# Run a measurement
./run.sh --out <OUTPUT_INDEX> --in <INPUT_INDEX>

# More options
./run.sh --out 2 --in 1 --runs 7 --verbose
```

| Flag | Default | Description |
|------|---------|-------------|
| `--out` | — | Output device index (required) |
| `--in` | — | Input (mic) device index (required) |
| `--runs` | 5 | Number of measurements to average |
| `--verbose` | off | Print per-run onset sample positions |
| `--list` | — | List all audio devices and exit |

## Setup for Bluetooth + Internal speaker measurement

1. In **Audio MIDI Setup** (macOS), create a **Multi-Output Device** that includes both your internal speakers and your Bluetooth speaker.
2. Set that Multi-Output Device as your system output.
3. Select it as the **Output** device in the detector.
4. Place your mic roughly equidistant between both speakers.
5. Run the detector — it will tell you how many milliseconds to delay the faster speaker.

## Applying the offset

Once you have your measurement, use one of these tools to introduce the compensating delay:

### [Loopback](https://rogueamoeba.com/loopback/) (Rogue Amoeba) — recommended
A virtual audio cable app that lets you build custom audio pipelines with per-source delay controls. Create a virtual device, route each physical output through it, and dial in the measured offset on the faster channel. Also handles the split-channel routing needed to run this detector.

### [Audio Hijack](https://rogueamoeba.com/audiohijack/) (Rogue Amoeba)
Captures audio from any app or device and applies effects per-stream. Add a **Delay** block to the faster speaker's stream and enter your measured offset. Best if you want app-level control (e.g. delay BT only when a specific app is playing).

### [BlackHole](https://existential.audio/blackhole/) + DAW
BlackHole creates a zero-latency virtual audio device. Route it into any DAW (Logic, Reaper, Ableton) or audio host, then use a simple delay plugin on the faster channel's track. Free and open-source.

### Audio MIDI Setup (built-in, limited)
macOS Multi-Output Devices have no built-in delay control. Use one of the tools above to actually apply an offset — Audio MIDI Setup alone is only useful for the routing step.

## Dependencies

```
sounddevice
numpy
scipy
```

Installed automatically by `run.sh`, or manually:

```bash
pip install -r requirements.txt
```

## Project structure

```
audio-latency-detector/
├── audio_latency_detector.py   # tkinter GUI
├── detect_offset.py            # core measurement logic (also a standalone CLI)
├── run.sh                      # entry point — bootstraps venv, launches GUI or CLI
├── build_mac.sh                # builds .app (macOS) or binary (Linux)
├── build_win.bat               # builds .exe (Windows)
└── requirements.txt
```

## License

MIT
