# Sheru Bhai daily reel bot

Makes one Sheeru Bhai reel a day and posts it to Instagram.

1. `prompts.py` writes the day's story (Hinglish) and caption from `episodes.json`.
2. You paste the story into the **Sheeru Bhai Studio** tool in Google Flow and click
   "Poori Video Banao". The tool makes the clips (9:16, 720p, Hindi speech).
3. `stitch.py` joins the clips into one 1080x1920 reel and adds the on-screen text.
4. `post_instagram.py` publishes it through Instagram's official Graph API.

`run_daily.py` runs steps 1, 3 and 4. Step 2 is done by hand for now.

## Signature ending

`outro.mp4` (Sheeru's golden sunglasses finale, made in Flow) is included and is added
to the end of every reel. Replace it with your own clip of the same name to change it.

## Editing options

The bot edits each reel the way Part 1 was edited by hand:

- trims every clip where its dialogue starts and ends, with short audio fades on each cut
- burns in the hook text over the opening and the follow card just before the outro
- makes `cover.jpg`, a designed cover with the title inside Instagram's profile-grid crop

Options for when the AI clips need help:

```
python run_daily.py --teaser 3       # open with the first 2.6 s of clip 3 (flash-forward hook)
python run_daily.py --skip 3         # leave clip 3 out (e.g. a continuity mistake)
python run_daily.py --cover-clip 4   # take the cover frame from clip 4 (default: last clip)
```

Part 1 was made with `--teaser 3 --skip 3 --cover-clip 4`.

When the bot posts through the API, Instagram's cover is set to a frame from the hook.
To use the designed `cover.jpg` instead, change it in the app: open the reel, Edit, Edit cover.

## Daily use

```
python run_daily.py        # prints today's story
```

Paste the story into the tool, wait for the clips, and download them into the folder
the command names (`output/episode_NNN/`) as `1.mp4`, `2.mp4`, `3.mp4` ... in order.

```
python run_daily.py        # joins the clips, adds text, posts
```

In the tool, set a Sheeru reference image and a Billa reference image once, so both
characters look the same in every episode.

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
| Editing: trims, fades, text, flash-forward, outro, cover | Tested on the real Part 1 clips (2026-11-14) |
| Results tracker (`insights.py`) | **Not tested.** Needs posted reels and a working token. |
| Sheeru Bhai Studio tool (Flow) | Run once by hand on 2026-11-14; it planned and queued clips. Automating it is not built. |
| `--auto-flow` (Flow chat via `flow_generate.py`) | **Experimental.** Prompt box and generate button checked on the live page; the rest is untested. Flow uses reCAPTCHA, which may block it. |
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
python run_daily.py --prompts-only     # read the story and caption
python run_daily.py --dry-run          # after saving the clips: make the reel, do not post
```

Watch `output/episode_000/reel.mp4`. When you are happy, set `DRY_RUN=false` in `.env`
and run `python run_daily.py`.

## Things to know

- **Credits:** each clip in the tool uses an image generation and a video generation.
  Check your Flow credit balance after the first story to see what one episode costs.
- **Watch before posting:** AI clips sometimes come out with a wrong face or wrong
  dialogue. Use "Regenerate Clip" in the tool for a bad one.
- **Trend audio:** the API cannot attach Instagram's trending audio. The reel uses the
  dialogue audio that Flow generates.
- **`--auto-flow`:** drives Flow's normal chat with a script. It may be against
  Google's terms, and Google's reCAPTCHA may block it. Treat it as experimental.
- **New episodes:** edit `episodes.json` to add items, lines and endings.
- **Secrets:** never share or upload `.env` or the `browser_profile` folder.
