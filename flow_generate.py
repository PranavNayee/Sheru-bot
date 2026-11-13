"""Generates clips in Google Flow by driving your own Chrome window.

There is no free public API for Flow, so this opens the Flow website in a Chrome
profile kept in ./browser_profile and types the prompts for you.

    python flow_generate.py --setup      # first time: log in to Google by hand
    python flow_generate.py --inspect    # open Flow with the Playwright inspector
    python flow_generate.py --test       # generate one short test clip

You log in yourself in the browser window. This script never sees or stores your
password. The page selectors live in selectors.json and are unverified guesses.
"""
import argparse
import base64
import json
import time
from pathlib import Path

import config


class FlowError(RuntimeError):
    pass


def _selectors() -> dict:
    return json.loads(config.SELECTORS_FILE.read_text(encoding="utf-8"))


def _open_context(playwright):
    config.PROFILE_DIR.mkdir(exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(config.PROFILE_DIR),
        channel="chrome",
        headless=False,
        accept_downloads=True,
        viewport={"width": 1280, "height": 900},
    )


def _first_visible(page, candidates, timeout_ms=4000):
    """Return the first visible locator from a list of selectors, or None."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for selector in candidates:
            locator = page.locator(selector).first
            try:
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                continue
        time.sleep(0.3)
    return None


def _video_sources(page, candidates) -> set:
    sources = set()
    for selector in candidates:
        try:
            found = page.eval_on_selector_all(
                selector,
                "els => els.map(v => v.currentSrc || v.src || "
                "(v.querySelector('source') ? v.querySelector('source').src : ''))",
            )
            sources.update(s for s in found if s)
        except Exception:
            continue
    return sources


def _save_video(page, src: str, out_path: Path) -> None:
    if src.startswith("blob:"):
        data = page.evaluate(
            """async (url) => {
                const blob = await (await fetch(url)).blob();
                const buf = new Uint8Array(await blob.arrayBuffer());
                let bin = '';
                for (let i = 0; i < buf.length; i += 0x8000) {
                    bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
                }
                return btoa(bin);
            }""",
            src,
        )
        out_path.write_bytes(base64.b64decode(data))
    else:
        response = page.context.request.get(src)
        if not response.ok:
            raise FlowError(f"Could not download the clip (HTTP {response.status}).")
        out_path.write_bytes(response.body())
    if out_path.stat().st_size < 50_000:
        raise FlowError(f"Downloaded file looks too small to be a video: {out_path}")


def _generate_one(page, prompt: str, out_path: Path, sel: dict, timeout_s: int) -> None:
    before = _video_sources(page, sel["video"])

    box = _first_visible(page, sel["prompt_box"], timeout_ms=15000)
    if box is None:
        raise FlowError("Could not find the prompt box. Update 'prompt_box' in selectors.json.")
    box.click()
    box.fill(prompt)

    button = _first_visible(page, sel["generate_button"], timeout_ms=3000)
    if button is not None:
        button.click()
    else:
        box.press("Enter")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        error = _first_visible(page, sel["error_text"], timeout_ms=300)
        if error is not None:
            raise FlowError(f"Flow showed a message: {error.inner_text()[:200]}")
        new = _video_sources(page, sel["video"]) - before
        if new:
            time.sleep(3)  # let the player settle on its final source
            new = (_video_sources(page, sel["video"]) - before) or new
            _save_video(page, sorted(new)[-1], out_path)
            return
        time.sleep(5)
    raise FlowError(f"No new clip appeared within {timeout_s} seconds.")


def generate_clips(prompts: list, out_dir: Path) -> list:
    """Generate one clip per prompt. Returns the saved file paths in order."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    sel = _selectors()
    paths = []
    with sync_playwright() as p:
        context = _open_context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(config.FLOW_URL, wait_until="domcontentloaded")
            new_project = _first_visible(page, sel["new_project_button"], timeout_ms=15000)
            if new_project is not None:
                new_project.click()
            for i, prompt in enumerate(prompts, start=1):
                out_path = out_dir / f"part{i}.mp4"
                print(f"[flow] generating clip {i} of {len(prompts)} ...")
                try:
                    _generate_one(page, prompt, out_path, sel, config.FLOW_TIMEOUT_SECONDS)
                except FlowError:
                    page.screenshot(path=str(out_dir / f"flow_error_part{i}.png"))
                    raise
                print(f"[flow] saved {out_path}")
                paths.append(out_path)
        finally:
            context.close()
    return paths


def _open_for_human(inspect: bool) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _open_context(p)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.FLOW_URL, wait_until="domcontentloaded")
        if inspect:
            page.pause()
        else:
            print(
                "\nA Chrome window is open.\n"
                " 1. Sign in to your Google account in that window.\n"
                " 2. Open a Flow project and set: aspect ratio 9:16, model Omni Flash, 720p, 1 output.\n"
                " 3. Come back here and press Enter to save the session.\n"
            )
            input("Press Enter when done... ")
        context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Flow clip generator")
    parser.add_argument("--setup", action="store_true", help="log in by hand and save the session")
    parser.add_argument("--inspect", action="store_true", help="open Flow with the Playwright inspector")
    parser.add_argument("--test", action="store_true", help="generate one test clip (uses credits)")
    args = parser.parse_args()

    if args.setup or args.inspect:
        _open_for_human(inspect=args.inspect)
    elif args.test:
        saved = generate_clips(
            ["Vertical 9:16, 5 seconds: a lion in a white suit waves at the camera in a marble hall."],
            config.OUTPUT_DIR / "flow_test",
        )
        print("Test clip:", saved[0])
    else:
        parser.print_help()
