"""Edits the clips into one finished 1080x1920 reel with ffmpeg (must be installed).

What it does, in order:
  1. Optional flash-forward: the first few seconds of one clip open the reel.
  2. Each story clip is trimmed where its dialogue starts and ends (found with
     ffmpeg's silence detection), so cuts land on the action, not on dead air.
  3. Short audio fades on every cut, so joins don't click.
  4. Optional outro clip at the end.
  5. Burned-in text: hook lines over the opening, a follow card just before the outro.

Also makes a cover image (cover.jpg) with the title placed inside Instagram's
profile-grid crop.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

FONT_CANDIDATES = [
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
TEASER_SECONDS = 2.6
LEAD_IN = 0.3        # keep this much before the first word
TAIL_OUT = 0.35      # keep this much after the last word
MAX_HEAD_TRIM = 0.5  # never cut more than this off the start (keeps the action)


class StitchError(RuntimeError):
    pass


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise StitchError(f"'{tool}' was not found. Install ffmpeg and make sure it is on PATH.")


def _run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise StitchError(f"ffmpeg failed: {result.stderr.strip()[-500:]}")
    return result


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    try:
        return float(out.strip())
    except ValueError:
        raise StitchError(f"Could not read the length of {path}.")


def _has_audio(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def speech_window(path: Path) -> tuple:
    """(start, end) seconds to keep: from just before the first sound to just after the last."""
    length = _duration(path)
    if not _has_audio(path):
        return 0.0, length
    log = subprocess.run(["ffmpeg", "-i", str(path), "-af", "silencedetect=n=-35dB:d=0.25",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    start, end = 0.0, length - 0.05
    if starts and starts[0] < 0.05 and ends:           # silence at the very beginning
        start = min(max(ends[0] - LEAD_IN, 0.0), MAX_HEAD_TRIM)
    if len(starts) > len(ends):                         # silence runs to the very end
        tail = starts[-1]
        if length - tail > 0.6:
            end = min(tail + TAIL_OUT, length - 0.05)
    if end - start < 1.0:                               # never trim a clip to nothing
        return 0.0, length
    return start, end


def _segment(src: Path, start: float, end: float, out: Path) -> None:
    """Re-encode one piece to a common format with short audio fades at both ends."""
    dur = end - start
    fade_out = max(dur - 0.08, 0)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-i", str(src)]
    if not _has_audio(src):
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-map", "0:v", "-map", "1:a"]
    cmd += ["-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-af", f"aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.06,"
                   f"afade=t=out:st={fade_out:.3f}:d=0.08",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
    _run(cmd)


def _font(dest_dir: Path):
    custom = Path(__file__).resolve().parent / "font.ttf"
    for candidate in [custom] + [Path(p) for p in FONT_CANDIDATES]:
        if candidate.exists():
            target = dest_dir / "_font.ttf"
            shutil.copyfile(candidate, target)
            return target
    return None


def _text(dest_dir: Path, tag: str, lines: list, y0: int, size: int, colors: tuple, enable: str) -> list:
    filters = []
    for i, line in enumerate(lines):
        (dest_dir / f"_{tag}{i}.txt").write_text(line, encoding="utf-8")
        fs = size if i == 0 else int(size * 0.72)
        y = y0 + (0 if i == 0 else int(size * 1.25) + (i - 1) * int(fs * 1.25))
        filters.append(f"drawtext=fontfile=_font.ttf:textfile=_{tag}{i}.txt:fontsize={fs}:"
                       f"fontcolor={colors[min(i, 1)]}:borderw=9:bordercolor=black:"
                       f"x=(w-text_w)/2:y={y}:enable='{enable}'")
    return filters


def stitch(clips: list, out_path: Path, hook_lines=None, end_lines=None,
           teaser=None, outro=None) -> dict:
    """Build the reel. Returns timings: {'total', 'story_end', 'hook_end'}."""
    _require("ffmpeg")
    _require("ffprobe")
    clips = [Path(c).resolve() for c in clips]
    for clip in clips + ([Path(teaser)] if teaser else []) + ([Path(outro)] if outro else []):
        if not Path(clip).exists():
            raise StitchError(f"Missing clip: {clip}")
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pieces = []
        if teaser:
            t = Path(teaser).resolve()
            _segment(t, 0.0, min(TEASER_SECONDS, _duration(t)), tmp / "p00.mp4")
            pieces.append(tmp / "p00.mp4")
        for i, clip in enumerate(clips, start=1):
            start, end = speech_window(clip)
            seg = tmp / f"p{i:02d}.mp4"
            _segment(clip, start, end, seg)
            pieces.append(seg)
        story_end = sum(_duration(p) for p in pieces)
        if outro:
            o = Path(outro).resolve()
            _segment(o, 0.0, _duration(o), tmp / "p99.mp4")
            pieces.append(tmp / "p99.mp4")

        (tmp / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in pieces))
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=tmp)
        total = _duration(tmp / "joined.mp4")
        hook_end = _duration(pieces[0]) if teaser else 3.0

        filters = []
        if (hook_lines or end_lines) and _font(tmp):
            if hook_lines:
                filters += _text(tmp, "h", hook_lines, 250, 110, ("yellow", "white"),
                                 f"lt(t,{hook_end:.2f})")
            if end_lines:
                filters += _text(tmp, "e", end_lines, 1180, 80, ("yellow", "white"),
                                 f"between(t,{max(story_end - 2.8, 0):.2f},{story_end:.2f})")
        elif hook_lines or end_lines:
            print("[stitch] No bold font found, so the reel has no on-screen text. "
                  "Put a font file named font.ttf in the project folder to enable it.")

        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", "joined.mp4"]
        if filters:
            cmd += ["-vf", ",".join(filters)]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final.mp4"]
        _run(cmd, cwd=tmp)
        shutil.move(str(tmp / "final.mp4"), str(out_path))
    return {"total": total, "story_end": story_end, "hook_end": hook_end}


def make_cover(source_clip: Path, out_jpg: Path, title: str, badge: str, top_line="Sheru Bhai") -> Path:
    """Cover image: a frame from source_clip with the title inside the 3:4 profile-grid crop."""
    _require("ffmpeg")
    source_clip, out_jpg = Path(source_clip).resolve(), Path(out_jpg).resolve()
    t = _duration(source_clip) * 0.25
    words = title.split()
    # "|" marks where to break the title; otherwise long titles split near the middle.
    if "|" in title:
        lines = [part.strip() for part in title.split("|") if part.strip()]
    elif len(title) > 14 and len(words) > 1:
        cut = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(title) / 2))
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
    else:
        lines = [title]
    size = max(60, min(122, int(1000 / (0.62 * max(len(l) for l in lines)))))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if not _font(tmp):
            raise StitchError("No bold font found for the cover. Put font.ttf in the project folder.")
        (tmp / "top.txt").write_text(top_line, encoding="utf-8")
        (tmp / "badge.txt").write_text(badge, encoding="utf-8")
        dt = "drawtext=fontfile=_font.ttf:borderw=11:bordercolor=black:x=(w-text_w)/2"
        f = ["scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
             "drawbox=x=0:y=1010:w=1080:h=560:color=black@0.45:t=fill",
             f"{dt}:textfile=top.txt:fontsize=74:fontcolor=white:y=1040"]
        y = 1135
        for i, line in enumerate(lines):
            (tmp / f"t{i}.txt").write_text(line, encoding="utf-8")
            f.append(f"{dt}:textfile=t{i}.txt:fontsize={size}:fontcolor=yellow:y={y}")
            y += int(size * 1.18)
        bw = 60 + int(len(badge) * 50)
        f += [f"drawbox=x={(1080 - bw) // 2}:y={y + 10}:w={bw}:h=105:color=red:t=fill",
              f"{dt}:textfile=badge.txt:fontsize=80:fontcolor=white:y={y + 23}"]
        _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(source_clip),
              "-frames:v", "1", "-vf", ",".join(f), "-q:v", "3", "cover.jpg"], cwd=tmp)
        shutil.move(str(tmp / "cover.jpg"), str(out_jpg))
    return out_jpg


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python stitch.py out.mp4 clip1.mp4 [clip2.mp4 ...]")
        raise SystemExit(1)
    print(stitch(sys.argv[2:], Path(sys.argv[1])))
