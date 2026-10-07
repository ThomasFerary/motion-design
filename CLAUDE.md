@AGENTS.md

## Repository layout

This repository is the shared base (method, pinned HeyGen skills, patterns, templates, HyperFrames 0.8.82). Each film
lives in its own folder at the root, created with `bash .claude/skills/motion-design/scripts/new-project.sh <project>`.
Never edit the core (`.claude/skills/`, `patterns/`, `templates/`) for a single film: copy what you need into the
project folder instead.

Remotes: `origin` is this repository, `upstream` is the original method
(`cblain100-prog/motion-design-claude-code`), to pull its updates.

## Windows machine notes

- Node: HyperFrames needs Node 22 or newer. If `node --version` is older and a portable Node exists in `.node/`, start
  every shell command that runs `npx`, `npm` or `node` with `export PATH="$PWD/.node:$PATH" &&`.
- Python: `python3` is the Microsoft Store alias on this machine and does not run Python. Use `python` wherever the
  method says `python3`.
