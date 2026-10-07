@AGENTS.md

## Repository layout

This repository is the shared base (method, pinned HeyGen skills, patterns, templates, HyperFrames 0.8.82). Each film
lives in its own folder at the root, created with `./film new <nom>`. Never edit the core (`.claude/skills/`,
`patterns/`, `templates/`) for a single film: copy what you need into the film folder instead.

Films are made **without a voice** by default: the `film` skill (`.claude/skills/film/SKILL.md`, `/film [nom]`) drives
the motion-design method with the on-screen text as the clock. Use `motion-design` only when the user wants a voice.

Remotes: `origin` is this repository, `upstream` is the original method
(`cblain100-prog/motion-design-claude-code`), to pull its updates. Keep upstream files unchanged so merges stay clean:
local additions live in `.claude/skills/film/`, `film`, `film.cmd` and this file.

## Running commands

Run every command of the method through the `./film` tool (`./film exec <command>` for any script): it sets Node 22
(portable in `.node/`), a working `python3` (on Windows `python3` is the Microsoft Store alias), the Git bash (from
PowerShell, `bash` may be WSL) and the telemetry variables. `./film env` checks the environment.
