#!/usr/bin/env python3
"""film: create and drive the films of this repository, one folder per film at the root, without a voice.

Every command sets the environment of the method itself: the pinned local HyperFrames, telemetry off, the portable
Node of .node/ when present, and on Windows a python3 that runs this Python (the method's scripts call python3, which
is the Microsoft Store alias there) and the Git bash (never the WSL one).

  ./film new <nom> [--format 16:9|9:16|1:1|4:5] [--duree 40] [--sans-polices]
  ./film liste
  ./film minutage <nom> [--musique F --debut S] [--elan F] [--cible S] [--rythme X] [--fenetre A B] ...
  ./film musique <nom> [M1 ...] [--mux renders/video.mp4]
  ./film assemble <nom> [--mix mix-M1.wav]           (the mix is kept in film.json for the next assemblies)
  ./film hf <nom> <arguments de npx hyperframes>      (preview, snapshot --at 1,2, check, validate, lint...)
  ./film rendu <nom> [--brouillon] [--sortie renders/video.mp4]
  ./film exec <commande> [arguments]                  (any script of the method: node, python3, bash x.sh...)
  ./film etape <nom> <etape>
  ./film env
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(SKILL, "..", "..", ".."))
WINDOWS = os.name == "nt"
FORMATS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
STAGES = ["1-texte", "2-minutage", "3-storyboard", "4-animation", "5-son", "6-controle", "7-livre"]
NO_TELEMETRY = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_SKIP_SKILLS": "1",
                "HYPERFRAMES_NO_UPDATE_CHECK": "1", "PYTHONIOENCODING": "utf-8"}
if not sys.stdout.isatty():  # piped output is read as UTF-8, not the Windows code page
    sys.stdout.reconfigure(encoding="utf-8")


def die(msg):
    sys.exit(f"film: {msg}")


def environment():
    env = dict(os.environ, **NO_TELEMETRY)
    extra = []
    node_dir = os.path.join(ROOT, ".node")
    if os.path.isdir(node_dir):
        extra.append(node_dir if WINDOWS else os.path.join(node_dir, "bin"))
    if WINDOWS:
        shim_dir = os.path.join(ROOT, ".local", "bin")
        os.makedirs(shim_dir, exist_ok=True)
        exe = sys.executable.replace("\\", "/")
        with open(os.path.join(shim_dir, "python3"), "w", newline="\n") as fh:
            fh.write(f'#!/bin/sh\nexec "{exe}" "$@"\n')
        with open(os.path.join(shim_dir, "python3.cmd"), "w") as fh:
            fh.write(f'@"{sys.executable}" %*\n')
        extra.append(shim_dir)
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def node_exe(env):
    found = shutil.which("node", path=env["PATH"])
    return found or die("node not found (Node 22 or newer is required)")


def bash_exe():
    if not WINDOWS:
        return shutil.which("bash") or die("bash not found")
    git = shutil.which("git") or die("Git for Windows not found (its bash runs the project scripts)")
    d = os.path.dirname(git)
    for _ in range(4):
        candidate = os.path.join(d, "bin", "bash.exe")
        if os.path.exists(candidate):
            return candidate
        d = os.path.dirname(d)
    die(f"Git bash not found next to {git}")


def run(cmd, cwd=ROOT, env=None):
    sys.stdout.flush()
    code = subprocess.run(cmd, cwd=cwd, env=env or environment()).returncode
    if code:
        sys.exit(code)


def project_dir(name):
    d = os.path.join(ROOT, name)
    if not os.path.isdir(d):
        die(f"no film '{name}' at the repository root ({ROOT})")
    return d


def state_path(name):
    return os.path.join(project_dir(name), "film.json")


def read_state(name):
    p = state_path(name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def write_state(name, state):
    with open(state_path(name), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def check_node(env):
    out = subprocess.run([node_exe(env), "--version"], capture_output=True, text=True, env=env).stdout.strip()
    major = int(re.match(r"v(\d+)", out).group(1)) if re.match(r"v(\d+)", out) else 0
    if major < 22:
        die(f"Node {out or '?'} found, HyperFrames needs 22 or newer (or a portable Node in {ROOT}/.node)")
    return out


def hyperframes(env, args, cwd):
    cli = os.path.join(ROOT, "node_modules", "hyperframes", "bin", "hyperframes.mjs")
    if not os.path.exists(cli):
        die("HyperFrames is not installed: run npm ci at the repository root")
    run([node_exe(env), cli] + args, cwd=cwd, env=env)


# ---- commands --------------------------------------------------------------------------------------------------------

def cmd_new(a):
    if a.format not in FORMATS:
        die(f"unknown format {a.format} (known: {', '.join(FORMATS)})")
    env = environment()
    if not os.path.exists(os.path.join(ROOT, ".env")):
        shutil.copy(os.path.join(ROOT, ".env.example"), os.path.join(ROOT, ".env"))
    script = os.path.join(ROOT, ".claude", "skills", "motion-design", "scripts", "new-project.sh")
    done = subprocess.run([bash_exe(), script, a.nom] + ([] if a.sans_polices else ["--fonts"]), cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        die((done.stderr or done.stdout).strip())
    for line in done.stdout.splitlines():  # its next-step hints are those of the voice method
        if line.startswith(("fonts:", "warning:")):
            print(line)
    d = project_dir(a.nom)
    w, h = FORMATS[a.format]

    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    meta.update(width=w, height=h)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")

    # no voice: the voice montage and the voice-ducked music options give way to the film skill's own files
    for f in ("build-audio.sh", "build-music-options.py"):
        os.remove(os.path.join(d, f))
    for f in ("TEXTE.md", "musique.py"):
        shutil.copy(os.path.join(SKILL, "templates", f), os.path.join(d, f))

    sb = os.path.join(d, "STORYBOARD.md")
    s = open(sb, encoding="utf-8").read()
    s = re.sub(r"(?m)^format: .*$", f"format: {w}x{h}", s, count=1)
    with open(sb, "w", encoding="utf-8", newline="") as fh:
        fh.write(s)
    p = os.path.join(d, "assemble.sh")
    s = open(p, encoding="utf-8").read()
    # no voice, no default mix.wav: the mix is the one chosen with ./film assemble --mix (film.json), else silent
    s = re.sub(r'(?m)^AUDIO=.*$', 'AUDIO="${MIX:+assets/audio/$MIX}"   # set by ./film assemble (film.json "mix"); empty = silent', s, count=1)
    # the iris layer draws on a 1920x1080 canvas
    s = s.replace('width="1920" height="1080" viewBox="0 0 1920 1080"', f'width="{w}" height="{h}" viewBox="0 0 {w} {h}"')
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(s)

    write_state(a.nom, {"nom": a.nom, "format": a.format, "largeur": w, "hauteur": h, "duree": a.duree,
                        "voix": False, "etape": STAGES[0], "cree": datetime.date.today().isoformat()})
    print(f"\nfilm '{a.nom}' : {a.format} ({w}x{h}), {a.duree:g} s visés, sans voix")
    if a.format != "16:9":
        print("note : la méthode a été réglée en 16:9 ; en vertical ou carré, adapter la bande de sous-titre de frame.md")
    print(f"prochaine étape : écrire {a.nom}/TEXTE.md (ou demander /film {a.nom} à Claude)")


def frames_status(d):
    sb = os.path.join(d, "STORYBOARD.md")
    if not os.path.exists(sb):
        return 0, 0
    srcs = re.findall(r"(?m)^- src: (\S+)", open(sb, encoding="utf-8").read())
    srcs = [s for s in srcs if "{{" not in s]
    return sum(os.path.exists(os.path.join(d, s)) for s in srcs), len(srcs)


def cmd_liste(_):
    rows = []
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if name.startswith(".") or name in ("node_modules", "examples") or not os.path.isfile(os.path.join(d, "meta.json")):
            continue
        st = read_state(name)
        built, total = frames_status(d)
        renders = os.path.join(d, "renders")
        mp4 = sorted(f for f in os.listdir(renders) if f.endswith(".mp4")) if os.path.isdir(renders) else []
        rows.append((name, st.get("format", "?"), f"{st['duree']:g} s" if st.get("duree") else "?",
                     st.get("etape", "?"), f"{built}/{total}" if total else "-", ", ".join(mp4) or "-"))
    if not rows:
        print("aucun film : ./film new <nom>")
        return
    head = ("film", "format", "durée", "étape", "séquences", "rendus")
    widths = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    for r in [head] + rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)).rstrip())


def cmd_minutage(a, rest):
    d = project_dir(a.nom)
    run([sys.executable, os.path.join(HERE, "minutage.py"), d] + rest)


def cmd_musique(a, rest):
    d = project_dir(a.nom)
    run([sys.executable, os.path.join(d, "musique.py")] + rest, cwd=d)


def cmd_assemble(a):
    d = project_dir(a.nom)
    env = environment()
    check_node(env)
    st = read_state(a.nom)
    mix = a.mix or st.get("mix")
    if mix:
        if not os.path.exists(os.path.join(d, "assets", "audio", mix)):
            die(f"{a.nom}/assets/audio/{mix} not found (./film musique {a.nom})")
        env["MIX"] = mix
        if a.mix and st and st.get("mix") != a.mix:
            st["mix"] = a.mix
            write_state(a.nom, st)
    print(f"mix: {mix or 'none, silent film'}")
    run([bash_exe(), os.path.join(d, "assemble.sh")], cwd=d, env=env)


def cmd_exec(rest):
    if not rest:
        die("usage: ./film exec <command> [arguments]")
    env = environment()
    run([bash_exe(), "-c", 'exec "$@"', "film-exec"] + rest, env=env)


def cmd_hf(a, rest):
    env = environment()
    check_node(env)
    hyperframes(env, rest, project_dir(a.nom))


def cmd_rendu(a):
    env = environment()
    check_node(env)
    out = a.sortie or ("renders/draft.mp4" if a.brouillon else "renders/video.mp4")
    hyperframes(env, ["render", "--quality", "draft" if a.brouillon else "high", "--output", out], project_dir(a.nom))


def cmd_etape(a):
    if a.etape not in STAGES:
        die(f"unknown stage {a.etape} (known: {', '.join(STAGES)})")
    st = read_state(a.nom)
    st["etape"] = a.etape
    write_state(a.nom, st)
    print(f"{a.nom} : {a.etape}")


def cmd_env(_):
    env = environment()
    print(f"racine     {ROOT}")
    print(f"node       {check_node(env)} ({node_exe(env)})")
    print(f"python     {sys.version.split()[0]} ({sys.executable})")
    print(f"bash       {bash_exe()}")
    for tool in ("ffmpeg", "ffprobe"):
        print(f"{tool:<10} {shutil.which(tool, path=env['PATH']) or 'ABSENT'}")
    pkg = os.path.join(ROOT, "node_modules", "hyperframes", "package.json")
    print(f"hyperframes {json.load(open(pkg))['version'] if os.path.exists(pkg) else 'ABSENT (npm ci)'}")
    print(f".env       {'présent' if os.path.exists(os.path.join(ROOT, '.env')) else 'ABSENT (cp .env.example .env)'}")


def main():
    ap = argparse.ArgumentParser(prog="film", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", aliases=["nouveau"], help="créer un film")
    p.add_argument("nom")
    p.add_argument("--format", default="16:9")
    p.add_argument("--duree", type=float, default=40.0, help="durée visée en secondes")
    p.add_argument("--sans-polices", action="store_true", help="ne pas télécharger les polices par défaut")
    sub.add_parser("liste", aliases=["list", "ls"], help="les films et leur étape")
    for name, text in (("minutage", "texte -> onsets.json (minutage.py)"), ("musique", "options de musique (musique.py)"),
                       ("hf", "npx hyperframes dans le dossier du film")):
        sub.add_parser(name, help=text, add_help=False).add_argument("nom")
    p = sub.add_parser("assemble", help="assembler les séquences (assemble.sh)")
    p.add_argument("nom")
    p.add_argument("--mix", help="mix de assets/audio à monter, ex. mix-M1.wav (retenu dans film.json)")
    sub.add_parser("exec", help="lancer une commande de la méthode dans l'environnement (node, python3, bash...)",
                   add_help=False)
    p = sub.add_parser("rendu", aliases=["render"], help="faire le rendu MP4")
    p.add_argument("nom")
    p.add_argument("--brouillon", action="store_true")
    p.add_argument("--sortie")
    p = sub.add_parser("etape", help="noter l'étape du film")
    p.add_argument("nom")
    p.add_argument("etape", help=", ".join(STAGES))
    sub.add_parser("env", help="vérifier l'environnement")

    if sys.argv[1:2] == ["exec"]:  # everything after exec belongs to the command, options included
        cmd_exec(sys.argv[2:])
        return
    a, rest = ap.parse_known_args()
    passthrough = {"minutage": cmd_minutage, "musique": cmd_musique, "hf": cmd_hf}
    if a.cmd in passthrough:
        passthrough[a.cmd](a, rest)
        return
    if rest:
        ap.error(f"unrecognized arguments: {' '.join(rest)}")
    {"new": cmd_new, "nouveau": cmd_new, "liste": cmd_liste, "list": cmd_liste, "ls": cmd_liste,
     "assemble": cmd_assemble, "rendu": cmd_rendu, "render": cmd_rendu, "etape": cmd_etape, "env": cmd_env}[a.cmd](a)


if __name__ == "__main__":
    main()
