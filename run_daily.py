"""Runs one full episode: prompts -> Flow clips -> stitched reel -> Instagram.

    python run_daily.py                 # normal daily run
    python run_daily.py --dry-run       # do everything except post
    python run_daily.py --skip-flow     # use clips you saved yourself as
                                        # output/episode_NNN/part1.mp4 and part2.mp4
    python run_daily.py --episode 5     # run a specific episode number (starts at 0)
    python run_daily.py --prompts-only  # just print today's prompts and caption

The episode counter in state.json only moves forward after a successful post
(or a successful dry run with --advance).
"""
import argparse
import datetime
import json
import sys

import config
import prompts


def _load_state() -> dict:
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"next_episode": 0, "history": []}


def _save_state(state: dict) -> None:
    config.STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sheru Bhai daily reel")
    parser.add_argument("--dry-run", action="store_true", help="never post, whatever .env says")
    parser.add_argument("--skip-flow", action="store_true", help="use existing part1.mp4 / part2.mp4")
    parser.add_argument("--episode", type=int, help="episode number to run (default: next one)")
    parser.add_argument("--prompts-only", action="store_true", help="print prompts and exit")
    parser.add_argument("--advance", action="store_true", help="move to the next episode even on a dry run")
    args = parser.parse_args()

    state = _load_state()
    number = args.episode if args.episode is not None else state["next_episode"]
    episode = prompts.build_episode(number)
    work_dir = config.OUTPUT_DIR / f"episode_{number:03d}"
    work_dir.mkdir(parents=True, exist_ok=True)

    (work_dir / "prompt_part1.txt").write_text(episode.part1, encoding="utf-8")
    (work_dir / "prompt_part2.txt").write_text(episode.part2, encoding="utf-8")
    (work_dir / "caption.txt").write_text(episode.caption, encoding="utf-8")
    print(f"[run] episode {number} ({episode.format}): {episode.item}")

    if args.prompts_only:
        print(f"\n--- PART 1 ---\n{episode.part1}\n\n--- PART 2 ---\n{episode.part2}"
              f"\n\n--- CAPTION ---\n{episode.caption}")
        return 0

    # 1. Clips
    clips = [work_dir / "part1.mp4", work_dir / "part2.mp4"]
    if args.skip_flow:
        missing = [str(c) for c in clips if not c.exists()]
        if missing:
            print("[run] --skip-flow needs these files:\n  " + "\n  ".join(missing))
            return 1
    else:
        import flow_generate
        try:
            clips = flow_generate.generate_clips([episode.part1, episode.part2], work_dir)
        except Exception as exc:
            print(f"[run] Flow step failed: {exc}")
            print(f"[run] Screenshot (if any) and prompts are in {work_dir}.")
            print("[run] You can make the two clips by hand, save them there as part1.mp4 "
                  "and part2.mp4, then run: python run_daily.py --skip-flow")
            return 1

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
