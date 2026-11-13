# Sheru Bhai daily reel bot

Makes one Sheru Bhai auction reel a day and posts it to Instagram.

1. `prompts.py` builds the day's two 10-second prompts and the caption from `episodes.json`.
2. `flow_generate.py` opens Google Flow in Chrome and generates the two clips.
3. `stitch.py` joins them into one 1080x1920 reel with ffmpeg.
4. `post_instagram.py` publishes it through Instagram's official Graph API.

`run_daily.py` runs all four steps.

## What makes the reels stronger

- **Hook first:** every prompt starts on the punch (Sheru's bid, or Sheru being insulted) with no slow intro.
- **Two formats:** auction ("boli") and disguise ("garib") rotate, so the page is not the same reel every day.
- **On-screen text:** big hook text for the first 3 seconds and a follow reminder at the end, burned in by ffmpeg. To use your own font, put a file named `font.ttf` in this folder.
- **Captions:** each one asks a question to pull comments and rotates hashtag sets.
- **Results:** `python insights.py` lists posted episodes by views so you can make more of what works (edit `episodes.json`).

None of this guarantees views. It raises the odds; the content and the audience decide.

## What has and has not been tested

| Part | Status |
|---|---|
| Prompts, captions, episode counter | Tested |
| Joining clips and on-screen text (ffmpeg) | Tested with sample clips |
| Results tracker (`insights.py`) | **Not tested.** Needs posted reels and a working token. |
| Google Flow step | **Not tested.** Written without access to the live site. Expect to fix `selectors.json` on first run. |
| Instagram posting | **Not tested.** Needs your account ID and token. Check the API version in `.env`. |

The bot ships with `DRY_RUN=true`, so it will not post anything until you switch that off.

## Laptop setup (once)

You need Python 3.10+, Google Chrome and ffmpeg installed.

```
pip install -r requirements.txt
playwright install chrome
```

Copy `.env.example` to `.env` and fill in the Instagram values.

### Instagram

- The account must be a professional account (Creator or Business).
- You need its numeric ID and a long-lived access token with publishing permission, from a Meta developer app.
- If your AIVerse bot already posts through the Graph API, the same app can issue a token for the new account.
- Test it: `python post_instagram.py --check` should print the account's username.

### Google Flow

```
python flow_generate.py --setup
```

A Chrome window opens. Sign in to Google yourself, open a Flow project and set
9:16, Omni Flash, 720p, one output. Flow should keep these settings for later runs.
Press Enter in the terminal to save the session.

Then generate one test clip (this uses credits):

```
python flow_generate.py --test
```

If it fails, run `python flow_generate.py --inspect`, use the inspector to find the
right element, and put its selector at the front of the matching list in `selectors.json`.

## First full run

```
python run_daily.py --prompts-only     # read the prompts
python run_daily.py --dry-run          # make the reel, do not post
```

Watch `output/episode_000/reel.mp4`. When you are happy, set `DRY_RUN=false` in `.env`
and run `python run_daily.py`.

## Run it every day

The laptop must be on, awake and online at the scheduled time.

- **Windows:** Task Scheduler > Create Basic Task > Daily > Start a program:
  `python`, arguments `run_daily.py`, "Start in" = this folder.
- **Mac/Linux:** `crontab -e`, then for 3:00 PM daily:
  `0 15 * * * cd /path/to/sheru-bot && python run_daily.py >> log.txt 2>&1`

Pick a time outside roughly 7:30-10:30 PM India time, when free Flow accounts can be
blocked from generating video.

## Things to know

- **Free limit:** the free Flow allowance covers about two short clips a day, so one
  reel a day with no retakes. If a clip comes out badly, that day's credits are gone.
- **If Flow fails:** make the two clips by hand using the prompt files in
  `output/episode_NNN/`, save them there as `part1.mp4` and `part2.mp4`, and run
  `python run_daily.py --skip-flow`.
- **Google sign-in:** Google sometimes refuses sign-in in an automated Chrome window.
  If that happens, use the `--skip-flow` route above.
- **Site rules:** driving the Flow website with a script may be against Google's
  terms and could get the account limited. Use an account you can afford to lose
  access to, and keep it to one run a day.
- **Trend audio:** the API cannot attach Instagram's trending audio. The reel uses the
  dialogue audio that Flow generates.
- **New episodes:** edit `episodes.json` to add items, lines and endings.
- **Secrets:** never share or upload `.env` or the `browser_profile` folder.
