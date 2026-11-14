"""Runs one episode: story -> clips from Google Flow -> stitched reel -> Instagram.

    python run_daily.py                 # 1st run: prints today's story to paste into
                                        # the Sheeru Bhai Studio tool in Google Flow.
                                        # 2nd run (after you save the clips into the
                                        # episode folder as 1.mp4, 2.mp4, ...): joins
                                        # them, adds the text and posts.
    python run_daily.py --dry-run       # do everything except post
    python run_daily.py --episode 5     # run a specific episode number (starts at 0)
    python run_daily.py --prompts-only  # just print the story and caption
    python run_daily.py --auto-flow     # experimental: generate two clips through
                                        # Flow's normal chat with flow_generate.py

The episode counter in state.json only moves forward after a successful post
(or a successful dry run with --advance).
"""
import argparse
import datetime
import json
import re
import sys

import config
import prompts


def _load_state() -> dict:
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"next_episode": 0, "history": []}


def _save_state(state: dict) -> None:
    config.STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _find_clips(work_dir) -> list:
    """All .mp4 files in the episode folder except the finished reel, in natural order."""
    def key(path):
        return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]
    return sorted((p for p in work_dir.glob("*.mp4") if p.name != "reel.mp4"), key=key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sheru Bhai daily reel")
    parser.add_argument("--dry-run", action="store_true", help="never post, whatever .env says")
    parser.add_argument("--skip-flow", action="store_true", help=argparse.SUPPRESS)  # old name, now the default
    parser.add_argument("--auto-flow", action="store_true", help="experimental: generate via Flow chat")
    parser.add_argument("--episode", type=int, help="episode number to run (default: next one)")
    parser.add_argument("--prompts-only", action="store_true", help="print prompts and exit")
    parser.add_argument("--advance", action="store_true", help="move to the next episode even on a dry run")
    args = parser.parse_args()

    state = _load_state()
    number = args.episode if args.episode is not None else state["next_episode"]
    episode = prompts.build_episode(number)
    work_dir = config.OUTPUT_DIR / f"episode_{number:03d}"
    work_dir.mkdir(parents=True, exist_ok=True)

    (work_dir / "story.txt").write_text(episode.story, encoding="utf-8")
    (work_dir / "prompt_part1.txt").write_text(episode.part1, encoding="utf-8")
    (work_dir / "prompt_part2.txt").write_text(episode.part2, encoding="utf-8")
    (work_dir / "caption.txt").write_text(episode.caption, encoding="utf-8")
    print(f"[run] episode {number} ({episode.format}): {episode.item}")

    if args.prompts_only:
        print(f"\n--- STORY (paste into Sheeru Bhai Studio) ---\n{episode.story}"
              f"\n\n--- CAPTION ---\n{episode.caption}")
        return 0

    # 1. Clips
    if args.auto_flow and episode.format == "series":
        print("[run] --auto-flow cannot make series episodes; use the Sheeru Bhai Studio tool.")
        return 1
    if args.auto_flow:
        import flow_generate
        try:
            clips = flow_generate.generate_clips([episode.part1, episode.part2], work_dir)
        except Exception as exc:
            print(f"[run] Flow step failed: {exc}")
            print(f"[run] Screenshot (if any) and prompts are in {work_dir}.")
            return 1
    else:
        clips = _find_clips(work_dir)
        if not clips:
            print(f"\n--- STORY ---\n{episode.story}\n")
            print("[run] Next steps:")
            print("  1. Paste the story above into your Sheeru Bhai Studio tool in Google Flow")
            print("     and click 'Poori Video Banao'.")
            print(f"  2. Download the clips into {work_dir}")
            print("     named in order: 1.mp4, 2.mp4, 3.mp4 ...")
            print("  3. Run this command again to join them and post.")
            return 0
        print(f"[run] found {len(clips)} clip(s): " + ", ".join(c.name for c in clips))

    # Signature ending: if outro.mp4 exists in the project folder, add it to every reel.
    outro = config.ROOT / "outro.mp4"
    if outro.exists():
        clips = list(clips) + [outro]
        print("[run] adding signature ending outro.mp4")

    # 2. Stitch
    import stitch
    reel = work_dir / "reel.mp4"
    try:
        stitch.stitch(clips, reel, hook_lines=episode.hook_lines, end_lines=episode.end_lines)
    except Exception as exc:
        print(f"[run] Joining the clips failed: {exc}")
        return 1
    print(f"[run] reel ready: {reel}")

    # 3. Post
    dry = args.dry_run or config.DRY_RUN
    media_id = None
    if dry:
        print("[run] DRY RUN: not posting. Watch the reel, then set DRY_RUN=false in .env to go live.")
    else:
        import post_instagram
        try:
            media_id = post_instagram.post_reel(reel, episode.caption)
        except Exception as exc:
            print(f"[run] Posting failed: {exc}")
            print(f"[run] The finished reel is saved at {reel}; nothing was posted.")
            return 1
        print(f"[run] posted to Instagram, media ID {media_id}")

    # 4. Remember progress
    if args.episode is None and (media_id or args.advance):
        state["next_episode"] = number + 1
    state["history"].append({
        "episode": number,
        "item": episode.item,
        "item_short": episode.item_short,
        "format": episode.format,
        "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "posted": bool(media_id),
        "media_id": media_id,
    })
    _save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
