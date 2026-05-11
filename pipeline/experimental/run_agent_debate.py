#!/usr/bin/env python3
"""
run_agent_debate.py

Runs a multi-agent AI debate over the canonical wealth-tax positions.
Agents are assigned personas from site/data/agent_personas.json and
vote/respond over 3 rounds. Output is a timestamped event log used by
the site/debate.html replay visualisation.

Usage:
    python3 pipeline/run_agent_debate.py
    python3 pipeline/run_agent_debate.py --rounds 2 --positions 15
    python3 pipeline/run_agent_debate.py --out site/data/agent_debate_log.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not found. pip install anthropic")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PERSONAS_PATH   = Path("site/data/agent_personas.json")
POSITIONS_PATH  = Path("site/data/claim_positions.json")
OUT_PATH        = Path("site/data/agent_debate_log.json")
MODEL           = "claude-haiku-4-5-20251001"   # fast + cheap for many short calls


def load_data():
    personas  = json.loads(PERSONAS_PATH.read_text())
    pos_data  = json.loads(POSITIONS_PATH.read_text())
    positions = pos_data.get("positions", []) + [
        {**p, "side": "shared"} for p in pos_data.get("shared", [])
    ]
    return personas, positions


def vote_prompt(persona: dict, position: dict) -> tuple[str, str]:
    system = persona["persona_prompt"] + (
        "\n\nRespond ONLY with valid JSON — no preamble:\n"
        '{"vote": "agree"|"disagree"|"neutral", "reasoning": "<1-2 sentence response>"}'
    )
    user = (
        f'Position ({position["side"].upper()} — {position["stasis"]}): '
        f'"{position["label"]}"\n\n'
        f'Claim: {position["claim"]}\n\n'
        f'How do you vote on this position? agree / disagree / neutral?'
    )
    return system, user


def evidence_prompt(persona: dict, position: dict, prior_votes: list[dict]) -> tuple[str, str]:
    system = persona["persona_prompt"] + (
        "\n\nYou are submitting evidence for a contested position. "
        "Respond ONLY with valid JSON:\n"
        '{"evidence_quote": "<a specific fact, statistic, or quote you would cite>", '
        '"evidence_source": "<where this comes from>", '
        '"note": "<why this matters, 1 sentence>"}'
    )
    # Summarise what others said about this position
    others = [v for v in prior_votes if v["position_label"] == position["label"]
              and v["agent"] != persona["id"] and v["vote"] in ("agree", "disagree")]
    context = ""
    if others:
        context = "\n\nOther participants said:\n" + "\n".join(
            f'- {v["agent_name"]} ({v["vote"]}): "{v["reasoning"]}"'
            for v in others[:3]
        )
    user = (
        f'Contested position: "{position["label"]}"\n'
        f'Claim: {position["claim"]}{context}\n\n'
        f'Submit the most important piece of evidence you have on this position.'
    )
    return system, user


def rebuttal_prompt(persona: dict, position: dict, target_evidence: dict) -> tuple[str, str]:
    system = persona["persona_prompt"] + (
        "\n\nYou are rebutting another participant's evidence. "
        "Respond ONLY with valid JSON:\n"
        '{"rebuttal": "<your response to their evidence, 1-2 sentences>", '
        '"concedes": true|false}'
    )
    user = (
        f'Position: "{position["label"]}"\n\n'
        f'{target_evidence["agent_name"]} submitted this evidence:\n'
        f'"{target_evidence["evidence_quote"]}" (source: {target_evidence["evidence_source"]})\n\n'
        f'Respond to this evidence.'
    )
    return system, user


def call_api(client, system: str, user: str) -> dict:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": raw}


def run_debate(personas: list, positions: list, n_rounds: int, max_positions: int, client) -> list:
    events = []
    event_id = 0
    all_votes = []       # accumulated vote records for context in later rounds

    # Sort positions by frequency so most-cited come first
    positions_sorted = sorted(positions, key=lambda p: -p.get("frequency", 0))
    debate_positions = positions_sorted[:max_positions]

    # Identify contested positions for rounds 2+
    # (will be determined after round 1)

    # ── Round 1: Vote on all positions ────────────────────────────────────────
    print(f"\nRound 1: voting on {len(debate_positions)} positions across {len(personas)} agents")
    for pos in debate_positions:
        for persona in personas:
            event_id += 1
            print(f"  [{event_id}] {persona['name']} → '{pos['label']}'", end=" ", flush=True)

            system, user = vote_prompt(persona, pos)
            result = call_api(client, system, user)

            vote    = result.get("vote", "neutral")
            reason  = result.get("reasoning", "")
            print(f"[{vote}]")

            event = {
                "event_id":       event_id,
                "round":          1,
                "agent":          persona["id"],
                "agent_name":     persona["name"],
                "agent_role":     persona["role"],
                "agent_color":    persona["avatar_color"],
                "action":         "voted",
                "position_label": pos["label"],
                "position_side":  pos["side"],
                "vote":           vote,
                "reasoning":      reason,
                "evidence_quote": None,
                "evidence_source": None,
                "rebuttal_to":    None,
                "concedes":       None,
                "ts":             time.time(),
            }
            events.append(event)
            all_votes.append(event)
            time.sleep(0.3)

    if n_rounds < 2:
        return events

    # ── Round 2: Evidence on contested positions ───────────────────────────────
    # Contested = positions where ≥2 agents disagree with each other
    vote_map: dict[str, dict[str, str]] = {}
    for v in all_votes:
        vote_map.setdefault(v["position_label"], {})[v["agent"]] = v["vote"]

    contested = [
        p for p in debate_positions
        if (sum(1 for v in vote_map.get(p["label"], {}).values() if v == "agree") >= 2
            and sum(1 for v in vote_map.get(p["label"], {}).values() if v == "disagree") >= 2)
    ][:5]

    research_agents = [p for p in personas if p.get("research_permitted")]
    print(f"\nRound 2: evidence on {len(contested)} contested positions from {len(research_agents)} research agents")

    evidence_events = []
    for pos in contested:
        for persona in research_agents:
            event_id += 1
            print(f"  [{event_id}] {persona['name']} → evidence for '{pos['label']}'", flush=True)

            system, user = evidence_prompt(persona, pos, all_votes)
            result = call_api(client, system, user)

            ev = {
                "event_id":        event_id,
                "round":           2,
                "agent":           persona["id"],
                "agent_name":      persona["name"],
                "agent_role":      persona["role"],
                "agent_color":     persona["avatar_color"],
                "action":          "evidence",
                "position_label":  pos["label"],
                "position_side":   pos["side"],
                "vote":            vote_map.get(pos["label"], {}).get(persona["id"], "neutral"),
                "reasoning":       result.get("note", ""),
                "evidence_quote":  result.get("evidence_quote", ""),
                "evidence_source": result.get("evidence_source", ""),
                "rebuttal_to":     None,
                "concedes":        None,
                "ts":              time.time(),
            }
            events.append(ev)
            evidence_events.append(ev)
            time.sleep(0.3)

    if n_rounds < 3:
        return events

    # ── Round 3: Rebuttals ────────────────────────────────────────────────────
    print(f"\nRound 3: rebuttals")
    for pos in contested[:3]:
        pos_evidence = [e for e in evidence_events if e["position_label"] == pos["label"]]
        if len(pos_evidence) < 2:
            continue
        # Each agent rebuts the evidence of one opponent (opposite vote)
        for persona in personas[:6]:
            my_vote = vote_map.get(pos["label"], {}).get(persona["id"], "neutral")
            # Find evidence from an opponent
            targets = [
                e for e in pos_evidence
                if e["agent"] != persona["id"]
                and e["vote"] != my_vote
                and e.get("evidence_quote")
            ]
            if not targets:
                continue
            target = targets[0]
            event_id += 1
            print(f"  [{event_id}] {persona['name']} rebuts {target['agent_name']} on '{pos['label']}'", flush=True)

            system, user = rebuttal_prompt(persona, pos, target)
            result = call_api(client, system, user)

            ev = {
                "event_id":        event_id,
                "round":           3,
                "agent":           persona["id"],
                "agent_name":      persona["name"],
                "agent_role":      persona["role"],
                "agent_color":     persona["avatar_color"],
                "action":          "rebuttal",
                "position_label":  pos["label"],
                "position_side":   pos["side"],
                "vote":            my_vote,
                "reasoning":       result.get("rebuttal", ""),
                "evidence_quote":  None,
                "evidence_source": None,
                "rebuttal_to":     target["agent"],
                "rebuttal_to_name": target["agent_name"],
                "concedes":        result.get("concedes", False),
                "ts":              time.time(),
            }
            events.append(ev)
            time.sleep(0.3)

    return events


def main():
    parser = argparse.ArgumentParser(description="Run AI agent debate over wealth-tax positions")
    parser.add_argument("--rounds",    type=int,  default=3,         help="Number of debate rounds (1-3)")
    parser.add_argument("--positions", type=int,  default=37,        help="Max positions to debate")
    parser.add_argument("--model",     default=MODEL,                help="Claude model to use")
    parser.add_argument("--out",       type=Path, default=OUT_PATH,  help="Output event log path")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set.")

    personas, positions = load_data()
    client = anthropic.Anthropic(api_key=api_key)

    print(f"DIM Agent Debate")
    print(f"  Agents    : {len(personas)}")
    print(f"  Positions : min({args.positions}, {len(positions)})")
    print(f"  Rounds    : {args.rounds}")
    print(f"  Model     : {args.model}")

    events = run_debate(personas, positions, args.rounds, args.positions, client)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_agents":     len(personas),
        "n_positions":  min(args.positions, len(positions)),
        "n_rounds":     args.rounds,
        "n_events":     len(events),
    }
    output = {"meta": meta, "personas": personas, "events": events}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2))
    print(f"\nWritten {len(events)} events → {args.out}")


if __name__ == "__main__":
    main()
