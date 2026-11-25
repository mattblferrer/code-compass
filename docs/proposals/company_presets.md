# Proposal: company pattern presets for interviews

**Status: adopted on 2026-11-25.** The author chose D1 to D8 and took the recommended option for D9 to D12. R-60 and the changes below are now in `docs/requirements.md`, `docs/rules.md`, and `docs/data_model.md`, which are the source of truth; this file records the reasoning.

Two corrections were made after approval. First, the snapshot's size and date: 84 companies have at least 25 problems (the draft's "about 113" was estimated from file sizes), and the mirror's latest commit, which the build uses, is dated 2026-10-20, although its README still says 1 June 2025. Second, D10's reason. The draft said an advanced pattern on an interview would plan days with no new problems, but `docs/rules.md` makes an interview's patterns active while it is in focus, so it would not. The choice stands for the reason now given under D10.

## Summary

When adding an interview (R-15), the user can pick a company from a list and fill in the patterns that company asks most, instead of choosing them by hand. The presets cover every company with at least 25 tagged problems in a public snapshot of LeetCode's company tags, 84 companies. Each preset is a short ranked list of patterns, worked out once by the maintainer from that snapshot through the catalog's reviewed pattern tags, and shipped with the app as `codecompass/data/companies.csv`.

A preset only fills in the form. Once saved, the interview is an ordinary interview: the user can change its patterns, and focus (R-15) and the prep plan (R-44) work exactly as today. A company not on the list is typed in and its patterns chosen by hand, as now.

The app does not predict questions and ships no company question lists. It shows which patterns a company's tagged problems use most, and the user decides.

## Decisions

| # | Decision | Choice | Why |
| --- | --- | --- | --- |
| D1 | Scope | **Pattern presets only.** No company tags on problems, no company problem lists, no change to which problems are recommended. | This is the smallest change to the PRD's exclusion of company-specific question banks, and it keeps the user choosing each company's focus (R-15). |
| D2 | Data source | **Derived from LeetCode's company tags**, through a public GitHub mirror (see Data). Only pattern-level results are shipped. | It is the only widely used source with per-company frequencies. Official company prep pages name broad topics, not frequencies. |
| D3 | Effect on rules | **Pre-fill only.** No schema change, no change to `docs/rules.md`, no stored link between an interview and a preset. | Rules and tests for R-13, R-15, and R-44 stay as they are. |
| D4 | Process | **This proposal first**, then the requirement changes below, then code. | Same process as `hosted_mode.md`. |
| D5 | Which companies | **Every company with at least 25 tagged problems** in the snapshot's all-time list (`COMPANY_MIN_PROBLEMS = 25`), 84 companies. | A fixed threshold, not a hand-picked list, so a newer snapshot is handled the same way. Each preset shows how many problems it rests on, so thin ones are visible. |
| D6 | Time window | **All time** (`5. All.csv`). | It has the most data and the most stable shares. The snapshot is already from 2025, so the recent windows are not current either. |
| D7 | Problems not in the catalog | **Catalog tags first, then only unambiguous LeetCode topics.** | Reviewed tags are preferred. LeetCode's topics fill in the rest only where a topic means one pattern (for example Sliding Window, Trie, Union Find). Broad topics such as Array or Dynamic Programming map to nothing, like Codeforces' broad tags (`core/codeforces_tags.py`). |
| D8 | Pre-filling over existing checks | **Replace the checks.** | It's an explicit click, so the result should be predictable: exactly the preset's patterns are checked. Nothing is saved until the user submits. |

### Decisions taken on approval

The author took option (a) for each.

| # | Decision | Options | Recommendation |
| --- | --- | --- | --- |
| D9 | How many patterns a preset fills in | (a) the top 6 by share, and only those with at least 5% share; (b) every pattern with at least 5% share; (c) a fixed top 8 | **(a).** The prep plan (R-44) covers two patterns a day, so 6 patterns fill three days before the mixed review. A cap keeps a 4% pattern from crowding the plan. Both values are named constants (`COMPANY_PRESET_MAX = 6`, `COMPANY_PRESET_MIN_SHARE = 5`). |
| D10 | Advanced patterns in presets | (a) core patterns only; (b) any pattern | **(a).** Advanced patterns are rarely asked in interviews, and R-32 keeps them off by default for that reason. An interview's patterns are active while it is in focus (`docs/rules.md`), so a preset with an advanced pattern would plan whole days around a niche topic such as segment trees. Advanced shares still appear in `docs/companies.md` for reference. |
| D11 | What the form shows beside a preset | (a) the ranked patterns with whole-number shares, the problem count, and the snapshot date; (b) the ranked patterns only | **(a).** The shares and count let the user judge a thin preset, and the date says the data is not current. |
| D12 | Licensing | (a) ship only derived shares, cite the mirror and snapshot date, never commit the raw lists; (b) don't ship presets until a licensed source exists | **(a).** See Risks. |

## Data

**Source.** [liquidslr/leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems), described by its owner as "based on the leetcode company tags". Its README says "updated as of 1 June 2025", but its latest commit ("Update Problem [Oct 20]", `2b71796`) is dated 2026-10-20, and that commit is the snapshot used. It has one folder per company, 470 in all, each with five CSV files (`1. Thirty Days.csv` to `5. All.csv`). The columns are `Difficulty, Title, Frequency, Acceptance Rate, Link, Topics`, for example `EASY,Two Sum,100.0,0.0058…,https://leetcode.com/problems/two-sum,"Array, Hash Table"`. Frequency is relative within a company, with 100 for its most-asked problem.

**Method** (to be added to `docs/rules.md` once approved, as the rule that builds `companies.csv`):

1. Take a company's `5. All.csv`. Skip the company if it has fewer than `COMPANY_MIN_PROBLEMS` rows.
2. Match each row to a catalog problem by link (ignoring a trailing slash and case). A matched problem uses its catalog patterns.
3. An unmatched row uses the patterns its LeetCode topics map to through a fixed table of unambiguous topics, drafted in `core/` and reviewed by the author. A row that maps to nothing is left out of the shares.
4. Each counted row adds its Frequency to its patterns, split evenly among them.
5. A pattern's share is its total over the total of all counted rows, as a percentage.
6. Record the company's problem count, how many rows were counted, and how much of its total Frequency came from catalog matches, so `docs/companies.md` can show how much rests on reviewed tags.

**Build.** A Flask command, `flask --app codecompass build-companies <snapshot folder>`, reads a copy of the snapshot that the maintainer downloads by hand. It makes no requests, runs only by hand, and writes `codecompass/data/companies.csv` (columns `company`, `pattern`, `share`, `problems`, `counted`, `catalog_share`, `snapshot`) and the coverage table in `docs/companies.md`. This works the same way `resources.csv` is built from `docs/resources.md`. The computation is a plain function in `core/companies.py` with no Flask or database, so it is tested with fixture data. The raw snapshot is never committed.

**Names and aliases.** Company names are kept as the snapshot spells them. A short alias table in `core/companies.py` maps common other names to them, for example Facebook to Meta, Alphabet to Google, Walmart and Walmart Global Tech to Walmart Labs, and Twitter to X. Matching ignores case and surrounding spaces.

## How it works for the user

On the Interviews page, the Company field offers the preset companies as suggestions while the user types (a `<datalist>`, so any name can still be typed). When the typed name matches a preset, a "Fill in patterns for Google" button appears under it, with the preset's patterns, their shares, the number of problems, and "from LeetCode's company tags", with the snapshot's date (D11). Clicking it checks exactly those pattern chips (D8) and unchecks the rest, without saving.

Without JavaScript, the button is a submit button that sends the form back with the preset's patterns checked and the other fields kept, and saves nothing. This follows R-38's rule that forms work without JavaScript.

Nothing else changes: the interview's own patterns drive R-15 and R-44 as they do now, the help page (R-58) gains a short paragraph about presets, and the interview list and prep plan look the same.

**Both modes.** `companies.csv` is shared, read-only data loaded at startup like `resources.csv`. It holds nothing per user, so R-52, backups (R-46), and deleting all data (R-39) are unaffected, and it works offline (R-24).

## Changes to sections 1 to 4

| Section | Now | Proposed |
| --- | --- | --- |
| 1. Overview | "It excludes … company-specific interview prediction." | "It excludes … company-specific question prediction and question lists. Optional pattern presets for companies, derived from public company tags, can fill in an interview's patterns (R-60)." |
| 2. Data | (no row) | New row, **Data: company presets**: pattern shares for 84 companies, derived once from a 2026 snapshot of LeetCode's company tags through the catalog's tags (R-60). *Limitations:* the tags are self-reported by LeetCode users and reflect LeetCode's audience; the snapshot is from a mirror with no license and will go stale; problems outside the catalog are tagged only by unambiguous LeetCode topics, so shares are approximate. |
| 2. Coverage | "No team features, no company-specific question banks, …" | Unchanged: there are still no question banks. Presets are pattern-level only. |
| 4. Included | (none) | Add: "optional company pattern presets for interviews". |
| 4. Excluded | "company-specific question prediction" | "company-specific question prediction or problem lists". |

## Changes to existing requirements

| ID | Change |
| --- | --- |
| R-15 | "Why it is needed" changes from "The user enters each company's focus, so the app does not predict questions." to "The user chooses each company's focus, optionally starting from a preset (R-60), so the app does not predict questions." The pass criteria are unchanged. |
| R-58 | The help page also covers company presets: where they come from, what the share means, and that they only fill in the form. |

## New requirement

| ID | Requirement | Why it is needed | What counts as passing | How you will check |
| --- | --- | --- | --- | --- |
| R-60 | [Recommendations] When adding or editing an interview (R-15), the user must be able to choose a company from a built-in list of presets and fill in its patterns: up to 6 core patterns with at least 5% share (provisional values), in order of share, worked out by the rule in `docs/rules.md` from a snapshot of LeetCode's company tags for every company with at least 25 tagged problems. Filling in checks exactly the preset's patterns and saves nothing. The form shows each pattern's share, the number of problems the preset rests on, and the snapshot's date. Any other company name can still be entered with patterns chosen by hand. Presets are shared and read-only, and change no score, due date, or recommendation rule. | Candidates often don't know which patterns a company favors, and finding out means searching paid or scattered sources. A preset gives a starting point the user can change, which keeps the choice theirs. | Typing a preset company's name, in any case or by a listed alias, offers its preset. Filling it in checks exactly its patterns, with or without JavaScript, and saves nothing. A company not on the list offers no preset and saves as before. An interview saved from a preset gives the same recommendations and prep plan as one with the same patterns chosen by hand. For fixture data, each company's shares equal the values worked out by hand. No page loads anything from outside the app. | Unit tests of the share rule with fixture data, integration tests in both modes, and a check at 375 px. |

## Risks

- **Licensing and terms.** The mirror has no license file, and its data comes from LeetCode's Premium company tags. CodeCompass ships no problem list from it, only pattern shares derived through its own reviewed tags, and cites the source. That reduces the exposure, but it does not make the source licensed. If that is not acceptable, D12(b) holds the feature until a licensed source appears.
- **What the data measures.** Company tags are reported by LeetCode users. They lean toward LeetCode-style rounds and toward the companies and roles LeetCode's users apply to. They say nothing about system design, practical coding rounds (common at Stripe and OpenAI, for example), or level.
- **Staleness.** The snapshot is from October 2026. Rebuilding from a newer snapshot is one command, and the date is shown beside every preset.
- **Catalog bias.** Matched problems use reviewed tags, unmatched ones use topics. The share of each company's total that came from catalog matches is listed in `docs/companies.md`, so the author can see where the shares rest on unreviewed tags.

## Work, once approved

1. Update `docs/requirements.md` (sections 1, 2, and 4, R-15, R-58, and new R-60), `docs/rules.md` (the share rule and constants), `docs/data_model.md` (`companies.csv`), and `CLAUDE.md` (requirement range).
2. Add `core/companies.py` (the share rule, topic table, aliases, and preset lookup) and its constants in `core/constants.py`, with unit tests on fixture data.
3. Add the `build-companies` command, run it on the downloaded snapshot, and have the author review `companies.csv`, the topic table, and `docs/companies.md`.
4. Add the Interviews form changes (datalist, fill button, no-JavaScript fallback), the help page paragraph, and integration tests in both modes.
