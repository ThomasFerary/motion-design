#!/usr/bin/env python3
"""Music options of a film without a voice (template of the film skill, from motion-design's build-music-options.py).

Same picture, several soundtracks: each option is a full mix (music + sound effects), so the music is chosen by ear
without rendering the video again (--mux swaps the soundtrack of a rendered MP4 in a second).

The film duration, the pivot and the light come from onsets.json (minutage.py), so the music follows the timing:
- with a pivot: the music is cut to silence on PIVOT with a low impact, a riser crests exactly there, and it comes
  back on LIGHT with its drop on it (track_start = the drop time printed by analyze-music.py --drop-at LIGHT);
- without a pivot: the segments play as written;
- no voice, so no ducking: the music carries the film, faded out on the end card, normalized for the web.

Fill OPTIONS, then from the repository root:
  ./film musique <project>                    # all options -> assets/audio/mix-<id>.wav, then a check
  ./film musique <project> M1 M3              # some options only
  ./film musique <project> --mux renders/video.mp4   # also renders/video-<id>.mp4 (no re-render)
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(os.path.join(HERE, "onsets.json")):
    sys.exit("musique: onsets.json not found, run ./film minutage <project> first")
TIMING = json.load(open(os.path.join(HERE, "onsets.json"), encoding="utf-8"))

# ---- settings -------------------------------------------------------------------------------------------------------
DUR = TIMING["duration"]                                       # film duration (s) = TOTAL in assemble.sh
PIVOT = TIMING["pivot"]["start"] if TIMING.get("pivot") else None   # music cut
LIGHT = TIMING["pivot"]["end"] if TIMING.get("pivot") else None     # music back, drop on it
SFX_EVENTS = "assets/audio/sfx-events.json"    # [["name", seconds, gain], ...] on the film timeline
OUT = "assets/audio/mix-{id}.wav"
MUSIC_DIR = os.environ.get("MUSIC_DIR", os.path.join(HERE, "assets", "music"))
SFX_DIR = os.environ.get("SFX_DIR", os.path.join(HERE, "..", ".claude", "skills", "media-use", "audio", "assets", "sfx"))

# Music segments: (file in MUSIC_DIR, track_start, film_start, film_end, gain, fade_in, fade_out).
# With a pivot, pattern 1: two tracks, tension until PIVOT, then elan from LIGHT (track_start = its drop time).
# With a pivot, pattern 2: one track, same file twice, the second segment starts at (first track_start + LIGHT).
# Without a pivot: one segment from 0 to DUR.
OPTIONS = {
    # "M1": {"name": "tension then elan", "riser": 0.18, "segments": [
    #     ("tension.mp3", 0.0, 0.0, PIVOT, 0.42, 0.4, 0.02),
    #     ("elan.mp3", 5.59, LIGHT, DUR, 0.34, 0.0, 2.4),
    # ]},
    # "M2": {"name": "one track", "riser": 0.0, "segments": [
    #     ("track.mp3", 0.0, 0.0, DUR, 0.40, 0.6, 2.4),
    # ]},
}

# Sound effects of the pivot, on top of SFX_EVENTS: (name in SFX_DIR, time, gain).
PIVOT_SFX = [("impact-bass-1", PIVOT, 0.34), ("sparkle", LIGHT - 0.04, 0.18), ("whoosh", LIGHT - 0.04, 0.22)] if PIVOT else []
RISER = "riser"            # media-use riser: a 10 s build that crests at its very end
RISER_LEN = 3.2            # seconds of riser kept before the pivot
LOUDNESS = "I=-16:TP=-1.5:LRA=11"                                   # web delivery
LIMIT = 0.79                 # final limiter ceiling (linear, -2 dBFS) so the true peak stays under -1.5 dBTP
# ---------------------------------------------------------------------------------------------------------------------


def path(rel):
    return rel if os.path.isabs(rel) else os.path.join(HERE, rel)


def sfx_file(name):
    for ext in (".wav", ".mp3"):
        f = os.path.join(SFX_DIR, name + ext)
        if os.path.exists(f):
            return f
    sys.exit(f"musique: sound effect '{name}' not found in {SFX_DIR} (.wav or .mp3)")


def duration(f):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def build(oid):
    opt = OPTIONS[oid]
    inputs, fc, bus, idx = [], [], [], 0
    for i, (f, ts, fs, fe, g, fi, fo) in enumerate(opt["segments"]):
        src = os.path.join(MUSIC_DIR, f)
        if not os.path.exists(src):
            sys.exit(f"musique: {src} not found (set MUSIC_DIR)")
        inputs += ["-i", src]
        d = fe - fs
        chain = f"[{idx}]atrim=start={ts:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo"
        if fi > 0:
            chain += f",afade=t=in:d={fi}"
        ms = int(round(fs * 1000))
        chain += f",afade=t=out:st={max(d - fo, 0):.3f}:d={fo},volume={g},adelay={ms}|{ms},apad=whole_dur={DUR}[m{i}]"
        fc.append(chain)
        bus.append(f"[m{i}]")
        idx += 1
    if PIVOT and opt.get("riser", 0) > 0:
        riser = sfx_file(RISER)
        inputs += ["-i", riser]
        ms = int(round((PIVOT - RISER_LEN) * 1000))
        fc.append(f"[{idx}]atrim=start={duration(riser) - RISER_LEN:.3f},asetpts=PTS-STARTPTS,"
                  f"aformat=sample_rates=44100:channel_layouts=stereo,afade=t=in:d=1.2,"
                  f"afade=t=out:st={RISER_LEN - 0.03:.3f}:d=0.03,volume={opt['riser']},adelay={ms}|{ms},apad=whole_dur={DUR}[mr]")
        bus.append("[mr]")
        idx += 1
    fc.append("".join(bus) + f"amix=inputs={len(bus)}:normalize=0:duration=longest,asplit=2[mmix][mraw]")
    labels = ["[mmix]"]
    events = json.load(open(path(SFX_EVENTS), encoding="utf-8")) if os.path.exists(path(SFX_EVENTS)) else []
    for j, (name, t, g) in enumerate(list(events) + PIVOT_SFX):
        inputs += ["-i", sfx_file(name)]
        ms = int(round(float(t) * 1000))
        fc.append(f"[{idx}]aformat=sample_rates=44100:channel_layouts=stereo,volume={g},adelay={ms}|{ms}[e{j}]")
        labels.append(f"[e{j}]")
        idx += 1
    fc.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,apad=whole_dur={DUR},"
              f"atrim=0:{DUR},loudnorm={LOUDNESS},alimiter=limit={LIMIT}:level=disabled,apad=whole_dur={DUR}[out]")
    out = path(OUT.format(id=oid))
    music_raw = out.replace(".wav", ".music-raw.wav")     # music alone, before the mix (levels check)
    cmd = ["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fc),
           "-map", "[out]", "-ar", "44100", "-t", str(DUR), out, "-map", "[mraw]", "-t", str(DUR), music_raw]
    subprocess.run(cmd, check=True)
    print(f"{oid} ({opt['name']}) -> {out}")
    check(out, music_raw)
    os.remove(music_raw)
    return out


def level(f, start, end, lowpass=None):
    """Mean level (dBFS) of a window, optionally under a low-pass (energy under 150 Hz shows the bass and kicks)."""
    af = f"atrim={max(start, 0):.3f}:{end:.3f}" + (f",lowpass=f={lowpass}:p=2,lowpass=f={lowpass}:p=2" if lowpass else "") + ",volumedetect"
    err = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", f, "-af", af, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[0-9.]+|-inf) dB", err)
    return float(m.group(1)) if m and m.group(1) != "-inf" else -120.0


def loudness(f, start, end):
    """Integrated loudness (LUFS) of a window."""
    err = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", f, "-af",
                          f"atrim={max(start, 0):.3f}:{end:.3f},ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    found = re.findall(r"I:\s+(-?[0-9.]+) LUFS", err)
    return float(found[-1]) if found else -70.0


def check(mix, music_raw):
    """The whole mix at -16 LUFS; with a pivot, the music silent between PIVOT and LIGHT and the tension 2 to 3 dB
    under the elan at most (lower, the start of the film feels soft)."""
    print(f"   mix {loudness(mix, 0.0, DUR):.1f} LUFS (aim -16)")
    if not PIVOT:
        return
    gap = level(music_raw, PIVOT + 0.05, LIGHT - 0.02, 150)
    tension = loudness(music_raw, 0.0, PIVOT - RISER_LEN)
    elan = loudness(music_raw, LIGHT, DUR - 3.0)
    print(f"   music alone: pivot to light {gap:.1f} dB under 150 Hz | tension {tension:.1f} LUFS, elan {elan:.1f} LUFS "
          f"(tension {tension - elan:+.1f} dB, aim -3 to -2 dB)")
    if gap > -60:
        print("   warning: the music is not silent between the pivot and the light")


def mux(video, mixes):
    base, _ = os.path.splitext(path(video))
    for oid, wav in mixes:
        out = f"{base}-{oid}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path(video), "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
        print(f"{oid} -> {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    video = None
    if "--mux" in args:
        k = args.index("--mux")
        video = args[k + 1] if k + 1 < len(args) else sys.exit("--mux needs a video path")
        del args[k:k + 2]
    if not OPTIONS:
        sys.exit("musique: OPTIONS is empty, fill it at the top of musique.py")
    unknown = [a for a in args if a not in OPTIONS]
    if unknown:
        sys.exit(f"musique: unknown option(s) {', '.join(unknown)} (known: {', '.join(OPTIONS)})")
    built = [(oid, build(oid)) for oid in (args or list(OPTIONS))]
    if video:
        mux(video, built)
