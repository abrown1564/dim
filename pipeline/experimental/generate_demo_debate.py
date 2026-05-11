#!/usr/bin/env python3
"""
generate_demo_debate.py

Generates a realistic synthetic debate event log for the debate.html
visualisation without making any API calls. Used for demos and development.

Usage:
    python3 pipeline/generate_demo_debate.py
"""

import json
from pathlib import Path
from datetime import datetime, timezone

PERSONAS_PATH  = Path("site/data/agent_personas.json")
POSITIONS_PATH = Path("site/data/claim_positions.json")
OUT_PATH       = Path("site/data/agent_debate_log.json")

# ── Hand-crafted agent stances on key positions ────────────────────────────────
# vote: agree / disagree / neutral
# Each entry: (agent_id, vote, reasoning)

ROUND1_DATA = {
    "capital flight risk": [
        ("liberty_whitmore",   "agree",    "The French 2012 wealth tax led to an estimated 10,000 millionaires leaving within two years — the evidence here is hard to dismiss."),
        ("priya_sharma",       "disagree", "Capital flight estimates are almost always produced by wealth management firms with obvious conflicts of interest; peer-reviewed evidence shows mobility is far lower."),
        ("dave_maguire",       "agree",    "I know three business owners who've already moved to Dubai — this isn't theoretical to me."),
        ("fiona_reese",        "neutral",  "Some flight will occur at the margin, but a well-designed narrow tax above £10m would affect too few people to matter macroeconomically."),
        ("tom_hargreaves",     "agree",    "The UK has already seen 17,000 millionaires leave in 2024 alone — the direction of travel is unmistakable."),
        ("amara_okonkwo",      "disagree", "The 16,000 figure was literally invented by a wealth management firm — we should not be making policy based on industry lobbying dressed up as data."),
        ("prof_james_caldwell","neutral",  "The evidence is genuinely mixed: some studies show significant flight effects, others find near-zero; this depends heavily on tax rate and design."),
        ("richard_ashworth",   "agree",    "I'm not proud to say it, but I've had conversations with my accountant about Singapore — and I'm not unusual among people I know."),
        ("mei_zhang",          "agree",    "California's wealthiest residents have been leaving for Nevada and Texas for years — the wealth tax proposals will accelerate that."),
        ("sarah_obrien",       "disagree", "Every time a tax on wealth is proposed, the same migration threat appears — it's become a ritual, not an empirical finding."),
    ],
    "rising inequality harms society": [
        ("liberty_whitmore",   "neutral",  "Inequality may be rising, but the relevant question is whether living standards are improving — which they broadly have been."),
        ("priya_sharma",       "agree",    "The bottom 50% of UK households own less than 5% of wealth while the top 1% own more than the bottom 70% combined — this is a structural crisis."),
        ("dave_maguire",       "agree",    "My workers can't afford houses anymore — that's not abstract inequality, that's my HR problem every month."),
        ("fiona_reese",        "agree",    "The Resolution Foundation's data is unambiguous: wealth inequality has widened sharply since 2008 while income inequality has stayed flat."),
        ("tom_hargreaves",     "neutral",  "Inequality statistics require careful interpretation — median household consumption, including public services, tells a more nuanced story."),
        ("amara_okonkwo",      "agree",    "When four million children live in poverty while billionaire wealth doubled during COVID, the social harm is not an abstraction."),
        ("prof_james_caldwell","agree",    "The Chetty mobility data and Piketty's r > g thesis are both well-supported — intergenerational wealth concentration is empirically real."),
        ("richard_ashworth",   "neutral",  "I accept inequality has grown, but I'm not sure a wealth tax is the right instrument — it's a complex problem with complex causes."),
        ("mei_zhang",          "neutral",  "US inequality is a serious problem, but wealth taxes aren't obviously the right fix — the evidence on what actually reduces it is thinner than advocates admit."),
        ("sarah_obrien",       "agree",    "The UK is increasingly a country with rich people in it, not a rich country — the collective data on stagnant wages against soaring asset prices is damning."),
    ],
    "wealth taxes have failed elsewhere": [
        ("liberty_whitmore",   "agree",    "Thirteen European countries tried annual wealth taxes and twelve have since abandoned them — that is not a coincidence."),
        ("priya_sharma",       "disagree", "Norway operates a wealth tax successfully today — the 'they all failed' narrative selectively ignores the cases where design worked."),
        ("dave_maguire",       "agree",    "If it worked, surely more countries would be doing it — the fact they gave it up tells you something."),
        ("fiona_reese",        "disagree", "The failures were mostly in countries with broad-based, poorly designed taxes — the Wealth Tax Commission showed a narrow UK version would be different."),
        ("tom_hargreaves",     "agree",    "France, Germany, Sweden and Denmark all tried and repealed wealth taxes — the UK would not be immune to the same dynamics."),
        ("amara_okonkwo",      "disagree", "The failures were political, not technical — governments caved to lobbying, not to economic necessity."),
        ("prof_james_caldwell","neutral",  "The international evidence is heterogeneous: design and threshold matter enormously, so broad generalisations from past failures are methodologically weak."),
        ("richard_ashworth",   "agree",    "France is the most instructive — Hollande's wealth tax was a political and economic disaster that even left-wing economists now acknowledge."),
        ("mei_zhang",          "agree",    "California has tried various forms of high wealth taxation and consistently seen more outflows than projected revenue — the pattern holds."),
        ("sarah_obrien",       "neutral",  "Some failed, some succeeded — the interesting question is why, not whether, and that depends entirely on design and political will."),
    ],
    "moral duty to contribute": [
        ("liberty_whitmore",   "disagree", "Morality doesn't override property rights — if the tax was already paid on the income, no additional moral obligation exists."),
        ("priya_sharma",       "agree",    "If you've benefited from public infrastructure, rule of law, and educated workers, contributing back is not charity — it's the social contract."),
        ("dave_maguire",       "neutral",  "I agree people should pay their fair share, but I don't trust the government to spend it well enough to justify more of it."),
        ("fiona_reese",        "agree",    "The social contract argument is correct, but it's also politically persuasive — and we need persuasion, not just moral assertion."),
        ("tom_hargreaves",     "disagree", "Framing taxation as moral duty is a rhetorical device to bypass the economic evidence — it doesn't settle the question of whether the tax will work."),
        ("amara_okonkwo",      "agree",    "Refusing to pay slightly more tax when four million children are in poverty is not a neutral economic position — it is a moral choice."),
        ("prof_james_caldwell","neutral",  "The moral argument is separate from the efficiency argument — both are legitimate but shouldn't be conflated in policy analysis."),
        ("richard_ashworth",   "neutral",  "I do believe in contributing — I pay a lot of tax already. The question is whether an additional wealth tax is the right mechanism."),
        ("mei_zhang",          "neutral",  "I'm not opposed to the moral argument in principle, but 'moral duty' alone has never designed a workable tax system."),
        ("sarah_obrien",       "agree",    "When billionaire wealth doubled during a pandemic while nurses queued at food banks, 'moral duty' isn't just rhetoric — it's an obvious description of reality."),
    ],
    "capital flight is overstated": [
        ("liberty_whitmore",   "disagree", "The academic studies showing low mobility often use old data or low-tax counterfactuals — they don't capture modern capital mobility."),
        ("priya_sharma",       "agree",    "The most rigorous peer-reviewed studies find behavioural responses of 0.1–0.3% of affected wealth, not the cliff-edge the industry claims."),
        ("dave_maguire",       "neutral",  "I don't know the academic studies, but I know people who've left — maybe they're outliers, maybe not."),
        ("fiona_reese",        "agree",    "The Wealth Tax Commission modelled this carefully — at the proposed thresholds, flight effects are small relative to revenue yield."),
        ("tom_hargreaves",     "disagree", "The Wealth Tax Commission's flight estimates were widely criticised for underweighting behavioural responses in the current political environment."),
        ("amara_okonkwo",      "agree",    "Every wealth tax proposal triggers the same scaremongering — and every time it's implemented carefully, the predicted exodus doesn't materialise at scale."),
        ("prof_james_caldwell","agree",    "The Jakobsen et al. Danish study is the most rigorous evidence we have — it shows about a 1% reduction in taxable wealth per 1% tax rate, which is small."),
        ("richard_ashworth",   "disagree", "I can tell you from my network that the modellers are not talking to the right people — the conversations happening at senior levels are more serious than academics appreciate."),
        ("mei_zhang",          "disagree", "California's actual revenue from high-earner taxes has consistently missed projections as people restructure — the models systematically understate avoidance."),
        ("sarah_obrien",       "agree",    "The 'mass exodus' narrative has been deployed against every progressive tax measure for 50 years — its track record as a prediction is terrible."),
    ],
    "narrow targeted tax is workable": [
        ("liberty_whitmore",   "disagree", "A tax above £10m sounds narrow today, but thresholds never stay where they're set — fiscal pressure always leads to expansion."),
        ("priya_sharma",       "agree",    "A 2% annual charge on wealth above £10m affects fewer than 100,000 people but could raise £25bn — the targeting is precisely the point."),
        ("dave_maguire",       "neutral",  "I'm not in the £10m bracket, but I've watched thresholds creep before — I want to see the legal guarantee before I'm reassured."),
        ("fiona_reese",        "agree",    "This is exactly what the Wealth Tax Commission designed — a one-off or annual charge with a high threshold is administratively feasible."),
        ("tom_hargreaves",     "disagree", "The compliance costs of administering a wealth registry for even 100,000 people would be enormous, and avoidance through trusts would erode the base."),
        ("amara_okonkwo",      "agree",    "A targeted tax is politically viable precisely because it only affects those who can genuinely afford it — this is the strongest design argument."),
        ("prof_james_caldwell","agree",    "The administrative evidence from Norway and Switzerland supports narrow high-threshold wealth taxes as workable — the valuation challenges are real but not insurmountable."),
        ("richard_ashworth",   "disagree", "At my level of wealth, even a 2% annual charge is not trivial — and it would mean liquidating assets every year to pay a tax on illiquid holdings."),
        ("mei_zhang",          "disagree", "My wealth is mostly in startup equity with no market price — how do you value it annually? This is the core unsolved problem."),
        ("sarah_obrien",       "agree",    "The workability objections get louder every time the threshold gets higher — at £10m+ the 'ordinary hard-working people will be hit' argument finally falls apart."),
    ],
    "double taxation objection": [
        ("liberty_whitmore",   "agree",    "If wealth was accumulated from already-taxed income, charging it again annually is a form of confiscation — it violates the principle of finality."),
        ("priya_sharma",       "disagree", "Wealth generates returns every year — taxing accumulated wealth annually is no more 'double taxation' than taxing annual income is double-taxing labour."),
        ("dave_maguire",       "agree",    "I've paid my taxes — the idea that the government can then come back every year for more of what I've saved feels fundamentally wrong."),
        ("fiona_reese",        "disagree", "Council tax, business rates, and capital gains are all taxes on existing wealth — we already accept that principle in other contexts."),
        ("tom_hargreaves",     "agree",    "The double-taxation argument is principled, not just self-interested — it reflects a legitimate philosophical position about the limits of redistribution."),
        ("amara_okonkwo",      "disagree", "Property is already taxed annually via council tax — the double-taxation framing is selectively applied only when it inconveniences the very wealthy."),
        ("prof_james_caldwell","neutral",  "The double-taxation concern is philosophically coherent but practically weak — most countries already tax wealth in various forms without accepting this as a barrier."),
        ("richard_ashworth",   "agree",    "I paid 45% income tax, 20% CGT on investments, and 40% inheritance tax applies when I die — at what point is enough enough?"),
        ("mei_zhang",          "agree",    "US tax already includes estate tax and capital gains — adding an annual wealth charge on top would be a genuine triple-taxation for many assets."),
        ("sarah_obrien",       "disagree", "The double-taxation argument is almost exclusively made by people whose effective tax rate is well below the headline rate they cite."),
    ],
    "valuation and enforcement difficulty": [
        ("liberty_whitmore",   "agree",    "Valuing private companies, art, and pension funds accurately enough for annual taxation is not a solved problem — the administrative burden would be immense."),
        ("priya_sharma",       "neutral",  "Valuation is a genuine challenge, but it's not unique to wealth taxes — inheritance tax and some business rates face the same issues and manage them."),
        ("dave_maguire",       "agree",    "My business isn't publicly traded — its value fluctuates and depends on assumptions. How do you tax something you can't price?"),
        ("fiona_reese",        "neutral",  "The Wealth Tax Commission addressed this directly — a self-assessed system with HMRC spot-checks is the proposed model, similar to existing practice."),
        ("tom_hargreaves",     "agree",    "Self-assessment of wealth creates massive incentives for undervaluation, and HMRC lacks the capacity to audit tens of thousands of complex estates."),
        ("amara_okonkwo",      "neutral",  "Other countries have built wealth registries and valuation frameworks — this is a solvable problem if there is political will to solve it."),
        ("prof_james_caldwell","agree",    "The valuation challenge is real — illiquid assets, family businesses, and intellectual property don't have obvious annual values, and getting it wrong creates serious distortions."),
        ("richard_ashworth",   "agree",    "My fund has positions that genuinely cannot be marked to market annually — any valuation would be artificial, and the tax liability would follow."),
        ("mei_zhang",          "agree",    "This is the core technical problem that killed the California proposal — the state literally could not figure out how to value venture portfolios."),
        ("sarah_obrien",       "neutral",  "Valuation complexity is real but routinely overstated as a dealbreaker — countries manage more complex financial regulation than a wealth register."),
    ],
    "fund public services and NHS": [
        ("liberty_whitmore",   "disagree", "The NHS funding problem is a spending efficiency problem, not a revenue problem — more tax won't fix a system that needs structural reform."),
        ("priya_sharma",       "agree",    "A £25bn annual yield from a narrow wealth tax would fund the NHS's entire capital investment budget — that's not marginal, it's transformative."),
        ("dave_maguire",       "neutral",  "I want the NHS funded, I just want to know the money will be spent well before I agree to pay more."),
        ("fiona_reese",        "agree",    "The case for hypothecated wealth tax revenue for public services is politically powerful and analytically sound — people support taxes when they see what they pay for."),
        ("tom_hargreaves",     "disagree", "Hypothecating tax revenue to specific services sounds appealing but is poor fiscal practice — and the NHS efficiency gap is estimated at £14bn, not addressable by a new tax."),
        ("amara_okonkwo",      "agree",    "The NHS is performing 7.6 million operations per year with facilities last upgraded in the 1970s — the funding argument is not abstract."),
        ("prof_james_caldwell","neutral",  "The revenue case is real but politically fragile — if behavioural responses erode the base, the public services promise may not be deliverable."),
        ("richard_ashworth",   "neutral",  "I support NHS funding, but I'm not convinced a wealth tax is the most efficient way to raise it — there may be less economically damaging alternatives."),
        ("mei_zhang",          "neutral",  "US context: the Medicaid/Medicare argument is similar — compelling, but the fiscal arithmetic depends heavily on compliance assumptions that are usually optimistic."),
        ("sarah_obrien",       "agree",    "Every year we debate wealth taxes, the NHS waiting list grows — at some point the 'not the right instrument' argument has to be weighed against doing nothing."),
    ],
    "cut waste not raise taxes": [
        ("liberty_whitmore",   "agree",    "UK public spending efficiency ranks poorly in international comparisons — the case for reform before further extraction is strong."),
        ("priya_sharma",       "disagree", "The 'cut waste first' argument has been made for 14 years of austerity — the waste was cut, the services deteriorated, and inequality grew."),
        ("dave_maguire",       "agree",    "Every organisation I know runs leaner than government — there is absolutely room to improve how money is spent before asking for more."),
        ("fiona_reese",        "disagree", "Austerity from 2010-2024 was the largest peacetime fiscal contraction in UK history — anyone claiming waste wasn't cut wasn't paying attention."),
        ("tom_hargreaves",     "agree",    "The Conservatives' record on spending shows there is always more waste to cut — efficiency gains through reform are less economically harmful than new taxes."),
        ("amara_okonkwo",      "disagree", "We had 14 years of cuts to everything from police numbers to social care — the idea there's fat left to trim is a myth."),
        ("prof_james_caldwell","neutral",  "Both arguments have merit — there is genuine inefficiency in public spending and genuine underinvestment; they're not mutually exclusive."),
        ("richard_ashworth",   "agree",    "I've seen how the Treasury operates — there is significant room for efficiency improvement before new taxes are justified."),
        ("mei_zhang",          "neutral",  "California has cut and taxed simultaneously for years — neither alone solves structural fiscal imbalances at state level."),
        ("sarah_obrien",       "disagree", "The 'cut waste' argument is almost always made by people who want to cut services they don't use and keep taxes low on assets they own."),
    ],
}

# Round 2: evidence on contested positions
ROUND2_DATA = {
    "capital flight risk": [
        ("liberty_whitmore",   "The 2012 French wealth tax saw an estimated 10,000 millionaires leave the country in two years, cited by Eric Pichet (Kedge Business School, 2016). This triggered its repeal in 2017.", "Pichet (2016) The Economic Consequences of the French Wealth Tax"),
        ("priya_sharma",       "The most rigorous study on wealth tax mobility (Jakobsen et al., 2020, QJE) found that a 1% wealth tax reduced reported wealth by only 0.6% — mostly avoidance, not migration.", "Jakobsen et al. (2020), Quarterly Journal of Economics"),
        ("fiona_reese",        "The Wealth Tax Commission modelled UK-specific mobility effects and concluded that a one-off charge above £500k would raise £260bn with flight effects under 5% of the base.", "Wealth Tax Commission Final Report (2020), LSE"),
        ("prof_james_caldwell","A 2019 study of Swedish wealth tax repeal found that while some migration occurred, 82% of the fiscal effect came from avoidance restructuring rather than physical relocation.", "Lundberg & Waldenström (2019), Journal of Public Economics"),
        ("sarah_obrien",       "The 16,000 millionaire departure figure cited by Reeves originated from the New World Wealth consultancy, which sells relocation services to HNWIs — an obvious conflict of interest.", "New World Wealth (2024) report, flagged by Tax Justice Network"),
    ],
    "wealth taxes have failed elsewhere": [
        ("liberty_whitmore",   "Of 12 European countries that introduced wealth taxes between 1970-2000, 10 have since repealed them — France (2018), Germany (1997), Sweden (2007) among them.", "OECD Tax Policy Studies No. 26 (2018)"),
        ("priya_sharma",       "Norway has maintained a wealth tax since 1892 and currently applies 1.1% on wealth above NOK 1.7m — it raises approximately 1.1% of GDP with limited adverse effects.", "Statistics Norway (2024), Norwegian Tax Administration"),
        ("fiona_reese",        "The Wealth Tax Commission's international review found that failures correlated with broad thresholds and poor design, not with the principle of wealth taxation itself.", "Wealth Tax Commission Evidence Paper 9 (2020)"),
        ("prof_james_caldwell","The Swiss cantonal wealth tax has operated for over 150 years at rates of 0.1-0.5% — it is the world's longest-running wealth tax and raises around 1% of cantonal revenue.", "Swiss Federal Tax Administration Annual Statistics"),
        ("sarah_obrien",       "The IEA report claiming wealth taxes 'always fail' was funded by donors including several individuals who would be directly subject to a UK wealth tax — disclosed in their accounts.", "IEA Annual Report (2023), Companies House filing"),
    ],
    "narrow targeted tax is workable": [
        ("priya_sharma",       "The Wealth Tax Commission modelled a 1% annual tax on wealth above £10m affecting approximately 140,000 people and yielding £11bn — with full administrative costings.", "Wealth Tax Commission Final Report (2020)"),
        ("fiona_reese",        "Norway's Skatteetaten (tax authority) administers a wealth tax with self-assessed valuations and algorithmic cross-checking — HMRC has equivalent or greater capability.", "Norwegian Tax Administration Annual Report (2023)"),
        ("prof_james_caldwell","Spain's annual wealth tax (0.2-3.5% above €700k) has been operational since 2011 — providing real-world administrative data on a narrow, high-threshold design.", "Agencia Tributaria (Spanish Tax Agency), 2023 statistics"),
    ],
    "rising inequality harms society": [
        ("priya_sharma",       "UK wealth inequality: the top 10% hold 43% of all wealth; the bottom 50% hold 9%. The Gini coefficient for wealth (0.63) is nearly double that for income (0.36).", "ONS Wealth and Assets Survey (2022), Wave 7"),
        ("prof_james_caldwell","Chetty et al. (2014, Science) showed that upward income mobility in the US has declined for every cohort born after 1940 — and wealth concentration is the primary driver.", "Chetty et al. (2014), Science 344(6186)"),
        ("sarah_obrien",       "Between 2020-2023, UK billionaire wealth grew by £150bn while 3.7 million UK children were in poverty — a statistic from the Sunday Times Rich List cross-referenced with JRF data.", "Sunday Times Rich List (2023) + JRF Poverty Report (2023)"),
    ],
    "moral duty to contribute": [
        ("amara_okonkwo",      "4.3 million children in the UK live in relative poverty (JRF 2024) — a figure that has risen by 400,000 since 2019 despite the economy growing in aggregate.", "Joseph Rowntree Foundation Poverty Report (2024)"),
        ("priya_sharma",       "Oxfam's 2024 global report found that the world's five richest men doubled their wealth since 2020, while 5 billion people became poorer in the same period.", "Oxfam 'Inequality Inc.' Report (January 2024)"),
    ],
}

# Round 3: rebuttals
ROUND3_DATA = [
    # (debater, target_agent, position_label, rebuttal_text, concedes)
    ("liberty_whitmore",  "priya_sharma",       "capital flight risk",
     "The Jakobsen study uses Danish data from 1989-1997 when capital mobility was a fraction of today's — extrapolating it to 2025 UK with open capital accounts is a methodological stretch.",
     False),
    ("priya_sharma",      "liberty_whitmore",   "capital flight risk",
     "The French case involved a 75% income tax and a broad-threshold ISF — comparing it to a 2% charge above £10m is comparing a sledgehammer to a scalpel.",
     False),
    ("prof_james_caldwell","liberty_whitmore",  "wealth taxes have failed elsewhere",
     "The OECD paper you cite does not conclude wealth taxes fail in principle — it concludes that poorly designed ones do. That's actually the case for targeted reform, not against it.",
     False),
    ("tom_hargreaves",    "fiona_reese",         "narrow targeted tax is workable",
     "The Wealth Tax Commission's administrative costings assumed a one-off charge, not an annual tax — their own authors have said an annual version would be substantially harder to administer.",
     False),
    ("fiona_reese",       "tom_hargreaves",      "narrow targeted tax is workable",
     "The Commission did model both options — and concluded that an annual tax above £10m is administratively feasible at a compliance cost of approximately 5% of yield, comparable to inheritance tax.",
     False),
    ("richard_ashworth",  "priya_sharma",        "rising inequality harms society",
     "I accept the ONS data on wealth distribution, but the question is whether a wealth tax is the most effective remedy — the evidence on what actually reduces wealth inequality is thinner than the evidence that it exists.",
     True),
    ("amara_okonkwo",     "liberty_whitmore",    "moral duty to contribute",
     "Property rights don't exist in a vacuum — they depend on courts, police, contract enforcement, and educated workers, all funded by taxation. The 'already paid' framing ignores this.",
     False),
    ("liberty_whitmore",  "amara_okonkwo",       "moral duty to contribute",
     "The social contract argument justifies some taxation — it doesn't determine the optimal rate or instrument. An annual wealth tax may be less efficient at funding public services than alternatives.",
     True),
    ("sarah_obrien",      "richard_ashworth",    "capital flight risk",
     "I respect the personal stake here, but 'I know people who are considering leaving' is the least reliable form of evidence — people threaten to leave in conversations and rarely do so at scale.",
     False),
    ("prof_james_caldwell","sarah_obrien",        "capital flight risk",
     "The conflict-of-interest point about New World Wealth is valid and important — but it doesn't settle the empirical question, which has been studied by genuinely independent researchers who find mixed results.",
     False),
]


def build_event_log():
    personas  = json.loads(PERSONAS_PATH.read_text())
    pos_data  = json.loads(POSITIONS_PATH.read_text())
    positions = pos_data.get("positions", []) + [
        {**p, "side": "shared"} for p in pos_data.get("shared", [])
    ]

    persona_map = {p["id"]: p for p in personas}
    pos_map     = {p["label"]: p for p in positions}

    events = []
    eid = 0

    # ── Round 1 ────────────────────────────────────────────────────────────────
    for pos_label, votes in ROUND1_DATA.items():
        pos = pos_map.get(pos_label, {"label": pos_label, "side": "unknown"})
        for agent_id, vote, reasoning in votes:
            p = persona_map[agent_id]
            eid += 1
            events.append({
                "event_id":        eid,
                "round":           1,
                "agent":           agent_id,
                "agent_name":      p["name"],
                "agent_role":      p["role"],
                "agent_color":     p["avatar_color"],
                "action":          "voted",
                "position_label":  pos_label,
                "position_side":   pos.get("side", "unknown"),
                "vote":            vote,
                "reasoning":       reasoning,
                "evidence_quote":  None,
                "evidence_source": None,
                "rebuttal_to":     None,
                "rebuttal_to_name": None,
                "concedes":        None,
            })

    # ── Round 2 ────────────────────────────────────────────────────────────────
    for pos_label, evidence_list in ROUND2_DATA.items():
        pos = pos_map.get(pos_label, {"label": pos_label, "side": "unknown"})
        for agent_id, evidence_quote, evidence_source in evidence_list:
            p = persona_map[agent_id]
            eid += 1
            # Find their round-1 vote on this position
            vote = next(
                (e["vote"] for e in events
                 if e["agent"] == agent_id and e["position_label"] == pos_label and e["round"] == 1),
                "neutral"
            )
            events.append({
                "event_id":        eid,
                "round":           2,
                "agent":           agent_id,
                "agent_name":      p["name"],
                "agent_role":      p["role"],
                "agent_color":     p["avatar_color"],
                "action":          "evidence",
                "position_label":  pos_label,
                "position_side":   pos.get("side", "unknown"),
                "vote":            vote,
                "reasoning":       None,
                "evidence_quote":  evidence_quote,
                "evidence_source": evidence_source,
                "rebuttal_to":     None,
                "rebuttal_to_name": None,
                "concedes":        None,
            })

    # ── Round 3 ────────────────────────────────────────────────────────────────
    for debater_id, target_id, pos_label, rebuttal_text, concedes in ROUND3_DATA:
        p   = persona_map[debater_id]
        pos = pos_map.get(pos_label, {"label": pos_label, "side": "unknown"})
        eid += 1
        vote = next(
            (e["vote"] for e in events
             if e["agent"] == debater_id and e["position_label"] == pos_label and e["round"] == 1),
            "neutral"
        )
        events.append({
            "event_id":        eid,
            "round":           3,
            "agent":           debater_id,
            "agent_name":      p["name"],
            "agent_role":      p["role"],
            "agent_color":     p["avatar_color"],
            "action":          "rebuttal",
            "position_label":  pos_label,
            "position_side":   pos.get("side", "unknown"),
            "vote":            vote,
            "reasoning":       rebuttal_text,
            "evidence_quote":  None,
            "evidence_source": None,
            "rebuttal_to":     target_id,
            "rebuttal_to_name": persona_map[target_id]["name"],
            "concedes":        concedes,
        })

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "demo":         True,
        "n_agents":     len(personas),
        "n_events":     len(events),
        "n_rounds":     3,
        "positions_covered": list(ROUND1_DATA.keys()),
    }

    output = {"meta": meta, "personas": personas, "events": events}
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Written {len(events)} events → {OUT_PATH}")
    for pos_label in ROUND1_DATA:
        r1 = sum(1 for e in events if e["position_label"] == pos_label and e["round"] == 1)
        r2 = sum(1 for e in events if e["position_label"] == pos_label and e["round"] == 2)
        r3 = sum(1 for e in events if e["position_label"] == pos_label and e["round"] == 3)
        print(f"  {pos_label:<40}  R1:{r1}  R2:{r2}  R3:{r3}")


if __name__ == "__main__":
    build_event_log()
