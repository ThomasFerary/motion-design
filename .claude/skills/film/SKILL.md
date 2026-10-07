---
name: film
description: Start a new film or resume one in this repository, without a voice-over. Creates the film folder with ./film new and drives the production of the motion-design method with the on-screen text as the clock and the music as the beat (text, timing, storyboard, animation, sound, checks, render). Use when the user asks here to create, start, continue or render a film, a motion design or a video project, or types /film [name]. When the user wants a voice-over, use the motion-design skill instead.
---

# Film without a voice: start, resume, produce

The `motion-design` skill is the method: read its `SKILL.md` and follow it, its gates, house rules, control grid and
dispatch template. This file only says what changes without a voice, and the commands of the `./film` tool.

**Without a voice, the on-screen text is the clock and the music gives the beat.** `TEXTE.md` replaces the voice:
`./film minutage` gives every phrase its reading time, scales the whole to the target duration, snaps the phrases onto
the beats of the music and writes `<film>/onsets.json` in the format of `onsets.py`. From there the storyboard, the
frame packets and the assembly work as in the method.

## Commands: always through ./film

`./film` (bash) or `film.cmd` (PowerShell) sets the environment of the method on every call: the pinned local
HyperFrames, telemetry off, the portable Node of `.node/`, a `python3` that runs Python (the Store alias otherwise) and
the Git bash (never the WSL one). Never call `npx`, `node`, `python3` or a `.sh` of the method directly.

| Need | Command |
|---|---|
| state of every film | `./film liste` |
| new film | `./film new <nom> --format 16:9 --duree 40` (9:16, 1:1, 4:5; `--sans-polices` offline) |
| timing | `./film minutage <nom> [--musique F --debut S] [--elan F] [--mots-sur-temps] [--rythme X] [--cible S]` |
| cues of one frame | `./film minutage <nom> --fenetre START END` |
| music options | `./film musique <nom> [M1 ...] [--mux renders/video.mp4]` |
| assembly | `./film assemble <nom> [--mix mix-M1.wav]` (the mix is kept in `film.json`) |
| HyperFrames | `./film hf <nom> snapshot --at 1.2,3.4` · `check` · `validate` · `lint` · `preview` |
| render | `./film rendu <nom> --brouillon`, then `./film rendu <nom>` |
| any other script | `./film exec node …` · `./film exec python3 …` · `./film exec bash ….sh …` |
| progress | `./film etape <nom> <1-texte, 2-minutage, 3-storyboard, 4-animation, 5-son, 6-controle, 7-livre>` |

Paths in the commands are relative to the repository root. Record the stage with `./film etape` at every gate passed.

## Start or resume

- **`/film <nom>` on an existing film**: `./film liste`, read `<nom>/film.json` (stage, format, duration, mix) and
  the files of that stage, then `./film exec python3 .claude/skills/motion-design/scripts/check-frames.py <nom>` from
  stage 4 on. Tell the user where the film stands in two lines and continue from there.
- **New film**: ask once, in one grouped question, what is missing: the subject (the pain, the promise), where it will
  be seen (format), the duration (30 to 60 s), the call to action and its URL, the real interfaces to show (recent
  screenshots), and whether there will be music (CC0 tracks they drop in the film folder) or a silent film. Pick a
  kebab-case name, then `./film new <nom> --format <f> --duree <s>`.

## 1. Text (gate)

The method's step 1, written for the screen instead of the ear. Propose 5 to 7 concepts in one line each, then 2
versions in full in `<nom>/SCRIPT.md`, each with its staging. The chosen one goes under `## Texte` in `<nom>/TEXTE.md`:

- one line = one phrase shown word by word, one idea, 3 to 9 words, 45 characters at most;
- budget about 1.6 to 2 words per second of film, silences included (40 s: 65 to 80 words);
- the same 6 parts: a concrete hook, a silent gag (`[silence 2.5]`), three concrete pains, the pivot on black
  (`[pivot 1.5]`, one per film), the solution and its benefits, the brand and the call to action, then `[fin 4]`;
- a demo that speaks for itself is a `[silence N]` too: the storyboard gives it its action.

## 2. Music and timing (gate)

1. **Music** (skip for a silent film): the user drops CC0 tracks in `<nom>/assets/music/` (sources and licence checks:
   `motion-design/references/music.md`). `./film exec python3 .claude/skills/motion-design/scripts/analyze-music.py <nom>/assets/music/*.mp3`
   gives tempo, rises, drops and bright or dark. Choose with the user: one track, or a tension track until the pivot
   and an elan track after it. `--debut` skips a sparse intro: take the tension from a full section, a sparse start
   makes the film feel soft.
2. **Timing**: `./film minutage <nom> --musique <nom>/assets/music/tension.mp3 --debut 8.5 --elan <nom>/assets/music/elan.mp3`
   (one track: no `--elan`; silent film: no music option). `--mots-sur-temps` puts the words on half beats too, for a
   kinetic text. Show the listing; if the scale is under 0.8 the text reads too fast: cut words or lengthen the film.
3. **Elan drop**: with `--elan`, its grid is anchored on LIGHT (the end of the pivot), so its drop must land there:
   `./film exec python3 .claude/skills/motion-design/scripts/analyze-music.py <nom>/assets/music/elan.mp3 --drop-at <LIGHT>`
   gives the track start to write in `musique.py`.
4. Copy the printed `settings:` line into `<nom>/assemble.sh` (TOTAL, LEAK_AT, IRIS_AT; place LEAK_X/Y and IRIS_X/Y at
   the storyboard step). `musique.py` reads DUR, PIVOT and LIGHT from `onsets.json` itself.

Gate: the user validates the rhythm on the listing (and by ear if there is music: play the track from `--debut`
while reading the cues). Any change to `TEXTE.md` or the music means `./film minutage` again before the storyboard.

## 3. Storyboard (gate)

The method's step 3 unchanged (three directions with styleframes, `frame.md`, `STORYBOARD.md`, the checks), with:

- styleframes: `./film exec python3 .claude/skills/motion-design/scripts/render-styleframes.py <nom>`;
- the header: `voice: "aucune : texte à l'écran, minutage <nom>/onsets.json (./film minutage)"`, and the **VOIX**
  section becomes **TEXTE**: the silent beats from `onsets.json`, each written as a shot with its own action;
- per frame, `voiceover:` quotes the TEXTE.md lines of that frame verbatim (the packet builder reads this field), and
  the word cues come from `./film minutage <nom> --fenetre <frame start> <frame end>`;
- **SON**: the music cut (PIVOT) and its return (LIGHT) come from `onsets.json`; no ducking, the music carries the film;
- canvas: `largeur` x `hauteur` of `film.json`. Outside 16:9, place the text band of `frame.md` in the lower third,
  above the bottom 20 % that the apps cover in 9:16, and scale the type to the width.

## 4. Animation (pilot gate)

The method's step 4 unchanged, with these commands:

- packets: `./film exec node .claude/skills/product-launch-video/scripts/frame-packets.mjs --project <nom> --storyboard <nom>/STORYBOARD.md`
- pilot: `./film assemble <nom>`, then `./film hf <nom> snapshot --at <3 or 4 times in frame 1>`
- the dispatch template of `motion-design/SKILL.md`, with `canvas: <largeur>x<hauteur>, 30 fps` from `film.json` and
  the house rule on captions read as: the on-screen text of TEXTE.md is the narration, word by word on its cues;
- after a session cut: `./film exec python3 .claude/skills/motion-design/scripts/check-frames.py <nom>`.

## 5. Sound (gate: the user chooses by ear)

Sound effects locked on the picture in `<nom>/assets/audio/sfx-events.json` (format
`motion-design/templates/sfx-events.json`, names from `.claude/skills/media-use/audio/assets/sfx/`). Fill `OPTIONS` in
`<nom>/musique.py` (3 or 4 options when there are tracks enough), `./film musique <nom>`, then
`./film assemble <nom> --mix mix-M1.wav` for the chosen one. The check prints the loudness (-16 LUFS) and, with a
pivot, the silence between PIVOT and LIGHT and the tension against the elan (2 to 3 dB under at most).

## 6 to 8. Checks, render, delivery

The method's steps 6 to 8 unchanged, through the tool: `./film hf <nom> check`, `./film hf <nom> validate`,
`./film hf <nom> snapshot --at …`, `./film rendu <nom> --brouillon`, `./film rendu <nom>`, then
`./film exec bash .claude/skills/motion-design/scripts/contact-sheets.sh <nom>/renders/video.mp4`. The duration of the
render equals TOTAL (`onsets.json` duration), with a video and an audio stream (only video for a silent film). Other
music options without a new render: `./film musique <nom> --mux renders/video.mp4`. Never say it is done before the
control of the real file; then `./film etape <nom> 7-livre`.
