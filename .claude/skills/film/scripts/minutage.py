#!/usr/bin/env python3
"""Timing of a film without a voice: the on-screen text is the clock, the music gives the beat.

Reads <project>/TEXTE.md (one line = one phrase shown on screen, word by word; [silence N], [pivot N] and [fin N]
are silent beats), gives every phrase its reading time, scales the whole to the target duration, snaps every phrase
onto a beat of the music when a track is given, and writes <project>/onsets.json in the format of onsets.py, so the
storyboard and the frame packets of the motion-design skill work unchanged.

Reading model (per word, then per phrase), multiplied by --rythme and by the scale that meets --cible:
  reveal of a word = 0.10 s + 0.022 s per letter, between 0.16 and 0.38 s
  hold after the last word = 0.20 s per word of the phrase, at least 0.8 s
Silent beats keep their written duration. A scale under 0.8 means the text is too long for the target.

Beat grid: the tempo comes from analyze-music.py, the phase from the onset envelope. Film time 0 is track time
--debut. With --elan, the grid after the pivot is the elan track's, anchored on the end of the pivot (its drop lands
there, see analyze-music.py --drop-at). Without --elan, one grid for the whole film and the pivot lasts whole beats.

Usage (from the repository root):
  python .claude/skills/film/scripts/minutage.py <project> [--cible 40] [--rythme 1.0]
        [--musique F --debut S [--bpm N]] [--elan F [--bpm-elan N]] [--mots-sur-temps]
  python .claude/skills/film/scripts/minutage.py <project> --fenetre 14.50 17.36   # frame-local cues
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ANALYZER = os.path.join(ROOT, ".claude", "skills", "motion-design", "scripts", "analyze-music.py")
BEAT = re.compile(r"^\[(silence|pivot|fin)\s+([0-9]+(?:[.,][0-9]+)?)\s*s?\]$", re.I)


def parse_text(path):
    """Items of TEXTE.md after its '## Texte' heading: ("phrase", text) or (kind, seconds)."""
    if not os.path.exists(path):
        sys.exit(f"minutage: {path} not found")
    s = re.sub(r"<!--.*?-->", "", open(path, encoding="utf-8").read(), flags=re.S)
    m = re.search(r"(?m)^##\s+Texte\s*$", s)
    if not m:
        sys.exit(f"minutage: no '## Texte' heading in {path}")
    items = []
    for line in s[m.end():].splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ">")):
            continue
        beat = BEAT.match(line)
        if beat:
            items.append((beat.group(1).lower(), float(beat.group(2).replace(",", "."))))
        elif line.startswith("["):
            sys.exit(f"minutage: unknown marker {line!r} (known: [silence N], [pivot N], [fin N])")
        else:
            items.append(("phrase", line))
    if not any(kind == "phrase" for kind, _ in items):
        sys.exit(f"minutage: no phrase under '## Texte' in {path}")
    if sum(kind == "pivot" for kind, _ in items) > 1:
        sys.exit("minutage: only one [pivot N] per film")
    if any(kind == "fin" for kind, _ in items[:-1]):
        sys.exit("minutage: [fin N] must be the last line")
    return items


def tokens(text):
    """Words of a phrase; French spaced punctuation (« : », « ! », « » ») sticks to its word."""
    out = []
    for raw in text.split():
        if out and not re.search(r"\w", raw) and raw != "«":
            out[-1] += " " + raw
        elif out and out[-1].endswith("«"):
            out[-1] += " " + raw
        else:
            out.append(raw)
    return out


def reveal(word):
    return min(max(0.10 + 0.022 * len(word), 0.16), 0.38)


def hold(n_words):
    return max(0.8, 0.20 * n_words)


def natural(items):
    """Natural duration of the phrases and fixed duration of the silent beats."""
    phrases = sum(sum(reveal(w) for w in tokens(text)) + hold(len(tokens(text)))
                  for kind, text in items if kind == "phrase")
    beats = sum(value for kind, value in items if kind != "phrase")
    return phrases, beats


def load_analyzer():
    sys.dont_write_bytecode = True  # no __pycache__ in the motion-design skill
    if not os.path.exists(ANALYZER):
        sys.exit(f"minutage: {ANALYZER} not found")
    spec = importlib.util.spec_from_file_location("analyze_music", ANALYZER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def beat_grid(path, start, bpm, length):
    """Beat times in film time (film 0 = track time `start`) over `length` seconds, and the tempo used."""
    mod = load_analyzer()
    np = mod.np
    x = mod.decode(path, start + length + 5)
    if bpm is None:
        found = mod.tempo(x)
        if not found:
            sys.exit(f"minutage: no clear beat in {path}, pass --bpm")
        bpm = found["bpm"]
        print(f"{os.path.basename(path)}: {bpm} BPM (or {found['alt_bpm']}), clarity {found['clarity']}")
    hop = 256
    mag = mod.stft_mag(x, 1024, hop)
    flux = np.maximum(0.0, np.diff(np.log1p(100 * mag), axis=0)).sum(axis=1)
    fps = mod.SR / hop
    latency = (hop + 512) / mod.SR  # flux index i peaks when the onset sits at the centre of STFT frame i + 1
    period = 60.0 / bpm
    phases = np.arange(0.0, period, 0.005)
    score = [flux[np.clip(((np.arange(ph, len(flux) / fps, period) - latency) * fps).round().astype(int),
                          0, len(flux) - 1)].sum() for ph in phases]
    phase = float(phases[int(np.argmax(score))])
    first = phase + period * max(0, int((start - phase) // period))
    grid = [round(t - start, 3) for t in np.arange(first, start + length + period, period) if t >= start - 1e-6]
    return grid, period


def snap(t, grid, not_before):
    """Nearest beat to t that is not before `not_before` (t itself when there is no grid)."""
    if not grid:
        return max(t, not_before)
    ok = [b for b in grid if b >= not_before - 1e-6]
    return min(ok, key=lambda b: abs(b - t)) if ok else max(t, not_before)


def build(items, scale, grid, grid_after, period_after, words_on_beat):
    words, phrases, beats = [], [], []
    t, pivot = 0.0, None
    current = grid
    prev_reveal_end = 0.0
    for kind, value in items:
        if kind != "phrase":
            if kind in ("pivot", "fin") and phrases:  # the music cut and the end card land on a beat
                t = snap(t, current, prev_reveal_end + 0.6 * scale)
            end = t + value
            if kind == "pivot":
                if grid_after is None and grid:  # one track: the pivot lasts whole beats
                    end = snap(end, grid, t + 1.0)
                pivot = {"start": round(t, 2), "end": round(end, 2)}
                if grid_after is not None:
                    current = [round(end + k * period_after, 3) for k in range(len(grid_after))]
            beats.append({"kind": kind, "start": round(t, 2), "end": round(end, 2)})
            t = end
            continue
        toks = tokens(value)
        start = snap(t, current, prev_reveal_end + 0.6 * scale if phrases else 0.0)
        offsets, acc = [], 0.0
        for w in toks:
            offsets.append(acc)
            acc += reveal(w) * scale
        if words_on_beat and current and len(current) > 1:
            sub = (current[1] - current[0]) / 2
            offsets = [round(o / sub) * sub for o in offsets]
            for i in range(1, len(offsets)):
                offsets[i] = max(offsets[i], offsets[i - 1] + sub)
            acc = offsets[-1] + reveal(toks[-1]) * scale
        first = len(words)
        for i, (w, o) in enumerate(zip(toks, offsets)):
            end = start + (offsets[i + 1] if i + 1 < len(offsets) else acc)
            words.append({"w": w, "s": round(start + o, 2), "e": round(end, 2)})
        prev_reveal_end = start + acc
        end = prev_reveal_end + hold(len(toks)) * scale
        phrases.append({"start": round(start, 2), "end": round(end, 2), "text": value,
                        "words": list(range(first, len(words)))})
        t = end
    starts = sorted([p["start"] for p in phrases] + [b["start"] for b in beats])
    for b in beats:
        if b["kind"] == "silence":  # a silence lasts until the next event, wherever its beat snapped
            b["end"] = next((s for s in starts if s > b["start"]), b["end"])
    for k, p in enumerate(phrases):
        nxt = next((s for s in starts if s > p["start"]), round(t, 2))
        p["end"] = min(p["end"], nxt)  # a snapped next event may start before the full hold
        nxt_phrase = phrases[k + 1]["start"] if k + 1 < len(phrases) else round(t, 2)
        p["silence_after"] = round(max(nxt_phrase - p["end"], 0.0), 2)
        p["cut_point"] = None
    return {"duration": round(t, 2), "phrases": phrases, "words": words, "beats": beats, "pivot": pivot}


def cue_token(text):
    token = re.sub(r"[.,;:!?…«»\"()]+", "", text).strip()
    return token.replace(" ", "-") or text


def show(result, window=None):
    origin = window[0] if window else 0.0
    if window:
        print(f"window {window[0]:.2f} to {window[1]:.2f}: times below are relative to {origin:.2f}")
    events = [("phrase", p) for p in result["phrases"]] + [("beat", b) for b in result.get("beats", [])]
    events.sort(key=lambda e: e[1]["start"])
    for n, (kind, e) in enumerate(events):
        if window and not (window[0] <= e["start"] < window[1]):
            continue
        if kind == "beat":
            print(f"      {e['start'] - origin:6.2f} to {e['end'] - origin:6.2f}   [{e['kind']}]")
            continue
        k = result["phrases"].index(e)
        print(f"#{k + 1:02d}  {e['start'] - origin:6.2f} to {e['end'] - origin:6.2f}   {e['text']}")
        cues = " ".join(f"{cue_token(result['words'][i]['w'])}@{result['words'][i]['s'] - origin:.2f}" for i in e["words"])
        print(f"     {cues}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--cible", type=float, help="target duration in seconds (default: film.json, 0 = natural)")
    ap.add_argument("--rythme", type=float, default=1.0, help="slower > 1 > faster (before the target scaling)")
    ap.add_argument("--musique", help="track playing from film time 0 (tension, or the only track)")
    ap.add_argument("--debut", type=float, default=0.0, help="track time at film time 0")
    ap.add_argument("--bpm", type=float, help="tempo of --musique (default: measured)")
    ap.add_argument("--elan", help="track coming back after the pivot, its drop on the end of the pivot")
    ap.add_argument("--bpm-elan", type=float, help="tempo of --elan (default: measured)")
    ap.add_argument("--mots-sur-temps", action="store_true", help="words on half beats too, not only phrase starts")
    ap.add_argument("--fenetre", nargs=2, type=float, metavar=("START", "END"),
                    help="print the cues of onsets.json between START and END, relative to START")
    args = ap.parse_args()

    project = args.project if os.path.isabs(args.project) else os.path.join(ROOT, args.project)
    out = os.path.join(project, "onsets.json")
    if args.fenetre:
        if not os.path.exists(out):
            sys.exit(f"minutage: {out} not found, run the timing first")
        show(json.load(open(out, encoding="utf-8")), args.fenetre)
        return

    items = parse_text(os.path.join(project, "TEXTE.md"))
    cible = args.cible
    if cible is None:
        state = os.path.join(project, "film.json")
        cible = json.load(open(state, encoding="utf-8")).get("duree") if os.path.exists(state) else 0
    phrases_len, beats_len = natural(items)
    phrases_len *= args.rythme
    scale = args.rythme
    if cible:
        if cible <= beats_len:
            sys.exit(f"minutage: the silent beats alone last {beats_len:.1f} s, more than the target {cible:.1f} s")
        scale = args.rythme * (cible - beats_len) / phrases_len
    words_count = sum(len(tokens(v)) for k, v in items if k == "phrase")
    print(f"text: {words_count} words, natural {phrases_len + beats_len:.1f} s, target "
          f"{f'{cible:.1f} s' if cible else 'none'}, reading scale {scale / args.rythme:.2f}")
    if scale / args.rythme < 0.8:
        print("warning: the text is too long for the target, it will read fast: cut words or lengthen the film")
    elif scale / args.rythme > 1.3:
        print("warning: the text is short for the target, phrases will linger: add a silent beat or shorten the film")

    length = (cible or phrases_len + beats_len) + 10
    grid = grid_after = period_after = None
    if args.musique:
        grid, _ = beat_grid(args.musique, args.debut, args.bpm, length)
    if args.elan:
        if not any(k == "pivot" for k, _ in items):
            sys.exit("minutage: --elan needs a [pivot N] in TEXTE.md")
        grid_after, period_after = beat_grid(args.elan, 0.0, args.bpm_elan, length)
    result = build(items, scale, grid, grid_after, period_after, args.mots_sur_temps)
    result.update({"audio": None, "source": "TEXTE.md", "cible": cible or None, "scale": round(scale, 3),
                   "musique": args.musique, "debut": args.debut, "elan": args.elan})
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    show(result)
    print(f"total {result['duration']:.2f} s -> {out}")
    piv = result["pivot"]
    ends = [b for b in result["beats"] if b["kind"] == "fin"]
    hints = [f"TOTAL={result['duration']:.2f}"]
    if piv:
        hints += [f"PIVOT={piv['start']:.2f}", f"LIGHT={piv['end']:.2f}", f"LEAK_AT={piv['end'] - 0.05:.2f}"]
    if ends:
        hints.append(f"IRIS_AT={ends[0]['start'] - 0.05:.2f}")
    print("settings: " + "  ".join(hints))


if __name__ == "__main__":
    main()
