#!/usr/bin/env python3
from sports_ai_policy import SYSTEM_PROMPT, WRESTLING_SHOW_RULES

def main():
    required = [
        "Never invent an event",
        "Official league/promoter/competition/team evidence outranks",
        "Recurring weekly programming is real schedule data",
        "WWE, AEW, TNA, and AAA Wrestling",
        "LIVE/PREGAME events with no source require source discovery",
        "OBSERVE -> CORRELATE -> IDENTIFY GAP -> RESEARCH -> VALIDATE -> PLAN -> ACT -> VERIFY -> LEARN",
        "User-authorized Xtream is a Tier-0 playback/source provider, not schedule truth",
        "no_action is allowed only when evidence shows there is no outstanding recovery obligation",
    ]
    for text in required:
        assert text in SYSTEM_PROMPT, f"missing policy rule: {text}"
    assert WRESTLING_SHOW_RULES["WWE"]
    assert WRESTLING_SHOW_RULES["AEW"]
    assert WRESTLING_SHOW_RULES["TNA"]
    assert WRESTLING_SHOW_RULES["AAA Wrestling"]
    print("Strict sports AI policy: PASS")
    print("Wrestling leagues covered: WWE, AEW, TNA, AAA Wrestling")

if __name__ == "__main__":
    main()
