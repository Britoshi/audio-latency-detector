import sounddevice as sd
import numpy as np
from scipy.signal import butter, filtfilt
import argparse
import sys

# ── Config ──────────────────────────────────────────────────────────────────
SAMPLE_RATE     = 44100
BURST_DURATION  = 0.08      # seconds — short enough to avoid reflection overlap
SILENCE_PRE     = 0.3       # silence before burst (let mic settle)
SILENCE_POST    = 0.5       # silence after burst (capture tail)
FREQ_L          = 400.0     # Hz — left channel (internal speaker)
FREQ_R          = 700.0     # Hz — right channel (BT speaker, non-harmonic of L)
BURST_AMPLITUDE = 0.8
FILTER_BW       = 80        # Hz — bandpass half-width around each frequency
ONSET_THRESHOLD = 0.15      # fraction of peak — tune if detecting noise or missing onset
RUNS            = 5         # number of measurements to average
# ────────────────────────────────────────────────────────────────────────────


def make_burst(freq, duration, sr, amplitude):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    burst = amplitude * np.sin(2 * np.pi * freq * t)
    # apply short fade in/out to avoid clicks
    fade_samples = int(sr * 0.005)
    fade = np.hanning(fade_samples * 2)
    burst[:fade_samples]  *= fade[:fade_samples]
    burst[-fade_samples:] *= fade[fade_samples:]
    return burst


def bandpass(signal, center, bandwidth, sr):
    low  = (center - bandwidth) / (sr / 2)
    high = (center + bandwidth) / (sr / 2)
    low  = max(low, 0.01)
    high = min(high, 0.99)
    b, a = butter(4, [low, high], btype='band')
    return filtfilt(b, a, signal)


def envelope(signal, smooth_samples=256):
    env = np.abs(signal)
    kernel = np.ones(smooth_samples) / smooth_samples
    return np.convolve(env, kernel, mode='same')


def detect_onset(env, threshold_frac, search_from=0):
    threshold = np.max(env) * threshold_frac
    indices = np.where(env[search_from:] > threshold)[0]
    if len(indices) == 0:
        return None
    return indices[0] + search_from


def build_playback(sr, burst_dur, pre_silence, post_silence):
    pre_samples  = int(sr * pre_silence)
    post_samples = int(sr * post_silence)
    burst        = make_burst(1.0, burst_dur, sr, BURST_AMPLITUDE)  # placeholder
    total        = pre_samples + len(burst) + post_samples

    left_burst  = make_burst(FREQ_L, burst_dur, sr, BURST_AMPLITUDE)
    right_burst = make_burst(FREQ_R, burst_dur, sr, BURST_AMPLITUDE)

    left_channel  = np.zeros(total)
    right_channel = np.zeros(total)

    left_channel[pre_samples:pre_samples + len(left_burst)]   = left_burst
    right_channel[pre_samples:pre_samples + len(right_burst)] = right_burst

    stereo = np.stack([left_channel, right_channel], axis=1).astype(np.float32)
    return stereo, pre_samples


def run_single_measurement(output_device, input_device, verbose=False):
    playback, pre_samples = build_playback(
        SAMPLE_RATE, BURST_DURATION, SILENCE_PRE, SILENCE_POST
    )
    total_samples = len(playback)

    recording = sd.playrec(
        playback,
        samplerate=SAMPLE_RATE,
        channels=1,
        device=(input_device, output_device),
        dtype='float32'
    )
    sd.wait()

    mono = recording[:, 0]

    # bandpass around each frequency
    filtered_l = bandpass(mono, FREQ_L, FILTER_BW, SAMPLE_RATE)
    filtered_r = bandpass(mono, FREQ_R, FILTER_BW, SAMPLE_RATE)

    env_l = envelope(filtered_l)
    env_r = envelope(filtered_r)

    # only search after pre-silence to avoid false early detections
    search_from = int(SAMPLE_RATE * SILENCE_PRE * 0.8)

    onset_l = detect_onset(env_l, ONSET_THRESHOLD, search_from)
    onset_r = detect_onset(env_r, ONSET_THRESHOLD, search_from)

    if onset_l is None or onset_r is None:
        print("  ⚠  Could not detect one or both onsets — check mic placement or threshold")
        return None

    offset_samples = onset_r - onset_l
    offset_ms = offset_samples / SAMPLE_RATE * 1000

    if verbose:
        print(f"  L onset: {onset_l} samples ({onset_l/SAMPLE_RATE*1000:.1f} ms)")
        print(f"  R onset: {onset_r} samples ({onset_r/SAMPLE_RATE*1000:.1f} ms)")
        print(f"  Raw offset: {offset_ms:+.2f} ms")

    return offset_ms


def list_devices():
    print("\nAvailable audio devices:\n")
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        tag = []
        if d['max_input_channels'] > 0:
            tag.append("IN")
        if d['max_output_channels'] > 0:
            tag.append("OUT")
        print(f"  [{i:2d}] {'  '.join(tag):<6} {d['name']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Measure left/right speaker delay offset using frequency bursts"
    )
    parser.add_argument("--list",   action="store_true", help="List audio devices and exit")
    parser.add_argument("--out",    type=int, default=None, help="Output device index")
    parser.add_argument("--in",     type=int, default=None, dest="inp", help="Input (mic) device index")
    parser.add_argument("--runs",   type=int, default=RUNS, help=f"Number of measurements to average (default: {RUNS})")
    parser.add_argument("--verbose",action="store_true", help="Print per-run onset details")
    args = parser.parse_args()

    if args.list:
        list_devices()
        sys.exit(0)

    print("\n── Bluetooth Speaker Offset Detector ──────────────────")
    print(f"  L channel: {FREQ_L:.0f} Hz  →  internal speaker")
    print(f"  R channel: {FREQ_R:.0f} Hz  →  BT speaker")
    print(f"  Runs: {args.runs}")

    if args.out is None or args.inp is None:
        print("\n⚠  No devices specified. Listing devices:\n")
        list_devices()
        print("Re-run with:  python detect_offset.py --out <OUT_INDEX> --in <IN_INDEX>\n")
        sys.exit(1)

    print(f"\n  Output device : [{args.out}] {sd.query_devices(args.out)['name']}")
    print(f"  Input device  : [{args.inp}] {sd.query_devices(args.inp)['name']}")
    print("\n  Place mic roughly between both speakers, then press Enter...")
    input()

    results = []
    for i in range(args.runs):
        print(f"\n  Run {i+1}/{args.runs}...")
        offset = run_single_measurement(args.out, args.inp, verbose=args.verbose)
        if offset is not None:
            results.append(offset)

    if not results:
        print("\n✗ No valid measurements. Check mic, device indices, and speaker routing.\n")
        sys.exit(1)

    results = np.array(results)

    # IQR outlier rejection
    q1, q3 = np.percentile(results, [25, 75])
    iqr = q3 - q1
    clean    = results[(results >= q1 - 1.5 * iqr) & (results <= q3 + 1.5 * iqr)]
    rejected = results[(results <  q1 - 1.5 * iqr) | (results >  q3 + 1.5 * iqr)]

    avg = np.mean(clean)
    std = np.std(clean)

    print("\n── Results ─────────────────────────────────────────────")
    print(f"  Raw          : {[f'{r:+.1f}' for r in results]}")
    if len(rejected) > 0:
        print(f"  Rejected     : {[f'{r:+.1f}' for r in rejected]} (outliers)")
    print(f"  Clean        : {[f'{r:+.1f}' for r in clean]}")
    print(f"  Average      : {avg:+.2f} ms")
    print(f"  Std dev      : {std:.2f} ms")
    print()

    if avg > 5:
        print(f"  → Delay the INTERNAL (L) speaker by {avg:.0f} ms to match BT")
    elif avg < -5:
        print(f"  → Delay the BT (R) speaker by {abs(avg):.0f} ms to match internal")
    else:
        print("  → Speakers are within 5ms — essentially in sync")
    print()


if __name__ == "__main__":
    main()
