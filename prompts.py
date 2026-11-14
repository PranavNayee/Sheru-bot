"""Builds the day's episode: a Hinglish story for the Sheeru Bhai Studio tool in
Google Flow, on-screen text and caption. (Two plain 10-second prompts are also
built, for use in Flow's normal chat if the tool is unavailable.)

Two story formats rotate so the page does not look repetitive:
  - "boli"  : the auction. Opens on Sheru's outrageous bid (the hook comes first).
  - "garib" : Sheru in disguise is insulted, a kind tea-seller helps, then the reveal.

Every third episode is "garib"; the rest are "boli". Edit episodes.json to add
items, lines and endings.
"""
import json
from dataclasses import dataclass, field

import config

STYLE = (
    "Vertical 9:16 video, 10 seconds, ultra-detailed cinematic 3D animation, "
    "comedy tone, fast pacing, clear lip-sync. Spoken dialogue in {language}. "
    "The action starts in the very first second with no slow intro. "
    "No on-screen text, no subtitles, no watermarks."
)


@dataclass
class Episode:
    number: int
    format: str
    item: str
    item_short: str
    part1: str
    part2: str
    caption: str
    story: str = ""
    hook_lines: list = field(default_factory=list)
    end_lines: list = field(default_factory=list)


def load_data() -> dict:
    return json.loads(config.EPISODES_FILE.read_text(encoding="utf-8"))


def _pick(options: list, n: int):
    return options[n % len(options)]


def _format_for(n: int) -> str:
    return "garib" if n % 3 == 2 else "boli"


def _boli(d: dict, n: int, item: str, style: str):
    rival = d["rival"]
    cast = f"{d['sheru']} {rival['look']}"
    part1 = (
        f"{style} Setting: {d['auction_setting']} Characters: {cast} "
        f"Open instantly on a close-up of Sheru Bhai dropping a golden briefcase on "
        f"the table and saying: \"{_pick(d['sheru_first_lines'], n)}\" The whole hall "
        f"gasps. Quick cut to {rival['name']} jumping to his feet, furious, shouting: "
        f"\"{_pick(d['rival_bids'], n)}\" The camera whips to the stage to show {item} "
        f"under a spotlight, then back to Sheru Bhai smiling without looking at him."
    )
    part2 = (
        f"{style} Setting: {d['auction_setting']} Characters: {cast} "
        f"Continuing the same auction for {item}. {rival['name']} wipes his forehead, "
        f"shaking. Sheru Bhai slowly stands, adjusts his gold watch, looks straight at "
        f"the camera and says: \"{_pick(d['sheru_final_lines'], n)}\" The owl's eyes go "
        f"wide and he slams the hammer. {_pick(d['auction_endings'], n)}. Gold confetti "
        f"falls and the shot ends on a close-up of Sheru Bhai's small smile."
    )
    return part1, part2


def _garib(d: dict, n: int, item: str, style: str):
    rival = d["rival"]
    part1 = (
        f"{style} Setting: {d['showroom_setting']} Characters: {d['sheru_disguised']} "
        f"{rival['look']} {d['helper']} "
        f"Open instantly on {rival['name']} shoving the disguised Sheru Bhai away from "
        f"{item} on display, sneering: \"{_pick(d['insults'], n)}\" Sheru Bhai stays "
        f"silent. Chhotu the rabbit hurries over, hands him a clay cup of tea and says "
        f"gently: \"{_pick(d['kind_lines'], n)}\" Sheru Bhai looks at Chhotu, touched."
    )
    part2 = (
        f"{style} Setting: {d['showroom_setting']} Characters: {d['sheru']} "
        f"{rival['look']} {d['helper']} "
        f"A line of white luxury cars screeches to a stop outside. A small mouse in a "
        f"chauffeur cap bows and Sheru Bhai now stands in his white three-piece suit. "
        f"{rival['name']}'s jaw drops. Sheru Bhai says calmly: "
        f"\"{_pick(d['reveal_lines'], n)}\" He places the keys to {item} in Chhotu's "
        f"paws. {_pick(d['disguise_endings'], n)}. The shot ends on Chhotu's amazed, "
        f"happy face."
    )
    return part1, part2


def _story(d: dict, n: int, fmt: str, short: str) -> str:
    if fmt == "boli":
        return (
            f"Sheeru Bhai ek shaandaar luxury auction hall mein aaram se baithe hain. "
            f"Stage par {short} ki boli lag rahi hai. Unka purana dushman Billa khada hokar "
            f"chillata hai: \"{_pick(d['rival_bids'], n)}\" Sheeru Bhai bina dekhe ek ungli "
            f"uthate hain aur shaant awaaz mein kehte hain: \"{_pick(d['sheru_first_lines'], n)}\" "
            f"Poora hall hairaan reh jaata hai aur Billa ko paseena aane lagta hai. Sheeru Bhai "
            f"dheere se khade hote hain, apni sone ki ghadi theek karte hain aur kehte hain: "
            f"\"{_pick(d['sheru_final_lines'], n)}\" Ullu neelaami-wala hathoda maar deta hai. "
            f"{_pick(d['auction_endings_hi'], n)} Sheeru Bhai halki si muskaan ke saath "
            f"{short} ki taraf chal dete hain."
        )
    return (
        f"Sheeru Bhai ek garib musafir ke bhes mein, purani phati shawl odhe, ek chamakte "
        f"luxury showroom mein {short} dekh rahe hain. Showroom ka ghamandi maalik Billa unhe "
        f"dhakka dekar kehta hai: \"{_pick(d['insults'], n)}\" Sheeru Bhai chup rehte hain. "
        f"Bahar chai bechne wala chhota khargosh Chhotu unhe garam chai deta hai aur kehta hai: "
        f"\"{_pick(d['kind_lines'], n)}\" Tabhi safed luxury gaadiyon ka kaafila aakar rukta hai. "
        f"Sheeru Bhai apne asli roop mein, safed suit aur kaale chashme mein, saamne aate hain. "
        f"Billa ka muh khula reh jaata hai. Sheeru Bhai kehte hain: "
        f"\"{_pick(d['reveal_lines'], n)}\" Woh {short} ki chaabi Chhotu ke haath mein rakh "
        f"dete hain. {_pick(d['disguise_endings_hi'], n)}"
    )


def _series_parts(d: dict) -> list:
    parts = []
    for series in d.get("series", []):
        total = len(series["parts"])
        for i, part in enumerate(series["parts"], start=1):
            parts.append((series["title"], i, total, part))
    return parts


def build_episode(n: int) -> Episode:
    """Series parts are posted first, in order; then the daily rotation starts."""
    d = load_data()
    parts = _series_parts(d)
    if n < len(parts):
        title, i, total, part = parts[n]
        return Episode(
            number=n, format="series", item=f"{title} part {i}/{total}",
            item_short=f"{title} {i}/{total}", part1="", part2="",
            caption=part["caption"], story=part["story"],
            hook_lines=part["hook"], end_lines=part["end"],
        )
    n -= len(parts)
    fmt = _format_for(n)
    if fmt == "garib":
        # Only items that make sense on display in a showroom.
        item = _pick([i for i in d["items"] if i.get("showroom")] or d["items"], n // 3)
    else:
        item = _pick(d["items"], n)
    style = STYLE.format(language=d["language"])

    if fmt == "boli":
        part1, part2 = _boli(d, n, item["prompt"], style)
        hook_lines = ["SHERU BHAI KI BOLI", f"Aaj: {item['short']}"]
        title = f"Sheru Bhai ki boli, episode {n + 1} 🦁💰"
    else:
        part1, part2 = _garib(d, n, item["prompt"], style)
        hook_lines = ["Garib samjha...", "nikla ARABPATI!"]
        title = f"Sheru Bhai ka imtihaan, episode {n + 1} 🦁"

    end_lines = [f"Episode {n + 2} kal", "FOLLOW karo"]
    caption = (
        f"{title}\n"
        f"{_pick(d['questions'], n)}\n\n"
        f"Agla episode kal. Follow karo.\n"
        f"AI-generated comedy. Fictional characters.\n"
        f"{_pick(d['hashtag_sets'], n)}"
    )
    return Episode(
        number=n, format=fmt, item=item["prompt"], item_short=item["short"],
        part1=part1, part2=part2, caption=caption,
        story=_story(d, n, fmt, item["short"]),
        hook_lines=hook_lines, end_lines=end_lines,
    )


if __name__ == "__main__":
    import sys

    ep = build_episode(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    print(f"FORMAT: {ep.format}\n\n--- STORY ---\n{ep.story}\n\n--- PART 1 ---\n{ep.part1}\n\n--- PART 2 ---\n{ep.part2}"
          f"\n\n--- ON-SCREEN ---\n{ep.hook_lines} ... {ep.end_lines}"
          f"\n\n--- CAPTION ---\n{ep.caption}")
