# Sheru Bhai daily reel bot

Makes one Sheeru Bhai reel a day and posts it to Instagram.

1. `prompts.py` writes the day's story (Hinglish) and caption from `episodes.json`.
2. You paste the story into the **Sheeru Bhai Studio** tool in Google Flow and click
   "Poori Video Banao". The tool makes the clips (9:16, 720p, Hindi speech).
3. `stitch.py` joins the clips into one 1080x1920 reel and adds the on-screen text.
4. `post_instagram.py` publishes it through Instagram's official Graph API.

`run_daily.py` runs steps 1, 3 and 4. Step 2 is done by hand for now.

## Signature ending

Put a short clip named `outro.mp4` in this folder (for example Sheeru's catchphrase,
made once in Flow) and the bot adds it to the end of every reel. Use your own clip,
not audio or footage cut from other creators' reels.

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
| Joining clips and on-screen text (ffmpeg) | Tested with sample clips |
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
