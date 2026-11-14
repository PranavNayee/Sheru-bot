"""Runs one episode: story -> clips from Google Flow -> stitched reel -> Instagram.

    python run_daily.py                 # 1st run: prints today's story to paste into
                                        # the Sheeru Bhai Studio tool in Google Flow.
                                        # 2nd run (after you save the clips into the
                                        # episode folder as 1.mp4, 2.mp4, ...): joins
                                        # them, adds the text and posts.
    python run_daily.py --dry-run       # do everything except post
    python run_daily.py --episode 5     # run a specific episode number (starts at 0)
    python run_daily.py --prompts-only  # just print the story and caption
    python run_daily.py --teaser 3      # open the reel with the first 2.6 s of clip 3
                                        # (a flash-forward hook)
    python run_daily.py --skip 3        # leave clip 3 out of the story (e.g. a continuity
                                        # mistake); combine with --teaser 3 to use only
                                        # its opening as the hook
    python run_daily.py --cover-clip 4  # take the cover frame from clip 4 (default: last)
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
    parser.add_argument("--teaser", type=int, help="clip number whose opening seconds start the reel")
    parser.add_argument("--skip", default="", help="clip numbers to leave out, e.g. 3 or 3,5")
    parser.add_argument("--cover-clip", type=int, help="clip number for the cover frame (default: last)")
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

    # 2. Edit: optional flash-forward hook, trimmed story clips, outro, text, cover
    import stitch
    numbered = {i: c for i, c in enumerate(clips, start=1)}
    skip = {int(x) for x in args.skip.split(",") if x.strip().isdigit()}
    for n in [args.teaser, args.cover_clip, *skip]:
        if n is not None and n not in numbered:
            print(f"[run] There is no clip {n}; found {len(clips)} clip(s).")
            return 1
    story_clips = [c for i, c in numbered.items() if i not in skip]
    teaser = numbered.get(args.teaser) if args.teaser else None
    outro = config.ROOT / "outro.mp4"
    outro = outro if outro.exists() else None
    reel = work_dir / "reel.mp4"
    cover = work_dir / "cover.jpg"
    try:
        timing = stitch.stitch(story_clips, reel, hook_lines=episode.hook_lines,
                               end_lines=episode.end_lines, teaser=teaser, outro=outro)
        cover_src = numbered[args.cover_clip] if args.cover_clip else story_clips[-1]
        stitch.make_cover(cover_src, cover, episode.cover_title or episode.item_short,
                          episode.cover_badge)
    except Exception as exc:
        print(f"[run] Editing failed: {exc}")
        return 1
    print(f"[run] reel ready: {reel} ({timing['total']:.1f} s"
          f"{', with flash-forward' if teaser else ''}{', with outro' if outro else ''})")
    print(f"[run] cover ready: {cover}  (set it in the Instagram app: Edit > Edit cover)")

    # 3. Post
    dry = args.dry_run or config.DRY_RUN
    media_id = None
    if dry:
        print("[run] DRY RUN: not posting. Watch the reel, then set DRY_RUN=false in .env to go live.")
    else:
        import post_instagram
        try:
            # Point the API's cover at the hook frame, which carries the title text.
            media_id = post_instagram.post_reel(reel, episode.caption,
                                                thumb_offset_ms=int(min(timing["hook_end"], 3) * 400))
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
