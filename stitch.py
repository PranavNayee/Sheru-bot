"""Joins clips into one 1080x1920 reel using ffmpeg (must be installed).

Optionally burns in big hook text for the first 3 seconds and a follow reminder
for the last 2.5 seconds. Text is kept inside Instagram's safe area (clear of the
top bar and the caption/buttons at the bottom).
"""
import shutil
import subprocess
from pathlib import Path

FONT_CANDIDATES = [
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


class StitchError(RuntimeError):
    pass


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise StitchError(f"'{tool}' was not found. Install ffmpeg and make sure it is on PATH.")


def _has_audio(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise StitchError(f"Could not read the length of {path}.")


def _find_font(work_dir: Path):
    """Copy a bold system font next to the reel so ffmpeg can use a simple path."""
    custom = work_dir.parent.parent / "font.ttf"  # optional: drop your own font.ttf in the project folder
    for candidate in [custom] + [Path(p) for p in FONT_CANDIDATES]:
        if candidate.exists():
            target = work_dir / "_font.ttf"
            shutil.copyfile(candidate, target)
            return target
    return None


def _text_filters(work_dir: Path, lines: list, tag: str, y_start: int, enable: str,
                  size: int, color: str) -> list:
    filters = []
    for i, line in enumerate(lines):
        text_file = work_dir / f"_{tag}{i}.txt"
        text_file.write_text(line, encoding="utf-8")
        filters.append(
            f"drawtext=fontfile=_font.ttf:textfile={text_file.name}:fontsize={size}:"
            f"fontcolor={color}:borderw=8:bordercolor=black:"
            f"x=(w-text_w)/2:y={y_start + i * int(size * 1.25)}:enable='{enable}'"
        )
    return filters


def stitch(clips: list, out_path: Path, hook_lines=None, end_lines=None) -> Path:
    _require("ffmpeg")
    _require("ffprobe")
    clips = [Path(c).resolve() for c in clips]
    for clip in clips:
        if not clip.exists():
            raise StitchError(f"Missing clip: {clip}")
    out_path = Path(out_path).resolve()
    work_dir = out_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for clip in clips:
        cmd += ["-i", str(clip)]

    filters, pairs = [], ""
    extra_input = len(clips)
    total = 0.0
    for i, clip in enumerate(clips):
        length = _duration(clip)
        total += length
        filters.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
        )
        if _has_audio(clip):
            filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        else:
            # Silent track so clips without sound can still be joined.
            cmd += ["-f", "lavfi", "-t", f"{length:.3f}",
                    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            filters.append(f"[{extra_input}:a]anull[a{i}]")
            extra_input += 1
        pairs += f"[v{i}][a{i}]"

    text = []
    if hook_lines or end_lines:
        if _find_font(work_dir) is None:
            print("[stitch] No bold font found, so the reel has no on-screen text. "
                  "Put a font file named font.ttf in the project folder to enable it.")
        else:
            if hook_lines:
                text += _text_filters(work_dir, hook_lines, "hook", 260, "lt(t,3)", 92, "yellow")
            if end_lines:
                text += _text_filters(work_dir, end_lines, "end", 1180,
                                      f"gt(t,{max(total - 2.5, 0):.2f})", 84, "white")

    if text:
        filters.append(f"{pairs}concat=n={len(clips)}:v=1:a=1[vj][a]")
        filters.append(f"[vj]{','.join(text)}[v]")
    else:
        filters.append(f"{pairs}concat=n={len(clips)}:v=1:a=1[v][a]")

    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path.name,
    ]
    # Run inside the work folder so filter paths are plain file names.
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(work_dir))
    for leftover in work_dir.glob("_*"):
        leftover.unlink()
    if result.returncode != 0:
        raise StitchError(f"ffmpeg failed: {result.stderr.strip()[:500]}")
    return out_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python stitch.py out.mp4 clip1.mp4 clip2.mp4 [...]")
        raise SystemExit(1)
    print("Saved", stitch(sys.argv[2:], Path(sys.argv[1])))
