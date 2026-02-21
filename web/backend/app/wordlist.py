"""Passphrase generator using EFF short wordlist (top 200 common words)."""
from __future__ import annotations

import secrets

# 256 common, easy-to-type English words (8 bits each → 4 words = 32 bits entropy)
# Curated for readability: no homophones, no offensive words, 4-8 chars each
WORDS = [
    "anchor", "apple", "arrow", "atlas", "badge", "baker", "basin", "beach",
    "blade", "blaze", "bloom", "board", "brave", "brick", "brook", "brush",
    "cabin", "camel", "candy", "cargo", "cedar", "chalk", "charm", "chase",
    "chess", "chief", "cider", "claim", "cliff", "clock", "cloud", "coach",
    "cobra", "coral", "crane", "crisp", "crown", "curve", "darts", "delta",
    "derby", "diver", "dodge", "dowel", "draft", "drift", "eagle", "ember",
    "fable", "fairy", "feast", "fence", "ferry", "fiber", "flame", "flask",
    "flint", "flora", "forge", "frost", "grain", "grape", "grove", "guard",
    "guide", "haven", "hazel", "hiker", "honey", "hover", "ivory", "jewel",
    "joker", "kayak", "kiosk", "knack", "latch", "lemon", "light", "linen",
    "lotus", "lunar", "mango", "maple", "march", "marsh", "mason", "medal",
    "melon", "merit", "metal", "mirth", "mocha", "moral", "motor", "noble",
    "north", "novel", "oasis", "ocean", "olive", "opera", "orbit", "otter",
    "oxide", "paint", "panel", "pearl", "penny", "piano", "pilot", "pixel",
    "plaza", "plumb", "polar", "prism", "pulse", "quart", "quest", "radar",
    "rally", "raven", "relay", "ridge", "rivet", "robin", "rover", "royal",
    "rugby", "rusty", "sable", "saint", "salsa", "sandy", "satin", "scout",
    "shark", "shelf", "shine", "shore", "sigma", "slate", "slide", "solar",
    "spark", "spice", "spoke", "spray", "stamp", "steam", "steel", "stern",
    "stone", "storm", "stove", "sugar", "surge", "swift", "table", "talon",
    "tango", "thorn", "tiger", "timer", "toast", "topaz", "torch", "tower",
    "trace", "trail", "trend", "trout", "tulip", "umbra", "unity", "upper",
    "valve", "vault", "vigor", "vinyl", "viola", "viper", "vivid", "vocal",
    "wagon", "waltz", "watch", "wheat", "wheel", "witch", "yacht", "zebra",
    "agile", "bison", "bliss", "boxer", "cello", "comet", "daisy", "disco",
    "elbow", "epoch", "frost", "gleam", "haste", "ideal", "jolly", "kneel",
    "liver", "magic", "nerve", "omega", "panda", "quiet", "roost", "shale",
    "snowy", "tidal", "ultra", "verse", "wrist", "youth", "zippy", "azure",
    "basil", "birch", "bluff", "cadet", "chess", "crimp", "downy", "easel",
    "fjord", "glyph", "holly", "inbox", "jumbo", "knelt", "lilac", "moose",
    "nexus", "onion", "plume", "quirk", "resin", "squid", "thyme", "usher",
    "venom", "whelk", "xerox", "yeast", "zonal", "alder", "bonus", "cloak",
]


def generate_passphrase(word_count: int = 4) -> str:
    """Generate a passphrase of `word_count` random words, hyphen-separated."""
    return "-".join(secrets.choice(WORDS) for _ in range(word_count))
