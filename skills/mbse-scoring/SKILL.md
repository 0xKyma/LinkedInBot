---
name: mbse-scoring
description: Topic priorities, exclusion rules, publication-quality rules, and the 25-point evaluation rubric for scoring MBSE/SysML/Systems Engineering content. Load when researching and shortlisting candidates for the MBSE track.
---

TOPIC PRIORITY (high to low):
1. SysML v2 — spec updates, OMG balloting, tooling support, adoption reports, migration guides
2. SysML v1 — community usage trends, v1-to-v2 migration discussions, deprecation signals
3. MBSE methodology — new frameworks, ROI studies, failure post-mortems, process debates
4. Digital engineering standards — DoD DE Strategy updates, UPDM, UAF, OpenMBEE, Capella
5. Systems Engineering research — peer-reviewed papers with practical implications
6. Adjacent signals — formal methods, model-based testing, digital twin integration with SE

EXCLUDE — do not surface these:
- Vendor press releases with no technical substance ("Company X announces partnership")
- "Introduction to MBSE / SysML" evergreen explainers with no new angle
- Paywalled content with no accessible summary or preprint
- Blog posts older than 10 days
- Anything primarily about software engineering or DevOps that only mentions SE in passing
- arXiv papers about general ML/AI that mention "systems" only in passing

PUBLICATION QUALITY — apply these rules to academic and technical report sources:
- Peer-reviewed papers in INCOSE Systems Engineering journal, IEEE Trans. on Systems
  Man and Cybernetics, MDPI Systems, or INCOSE symposia proceedings: weight Relevance
  and Practicality heavily; accept Timeliness as low as 2/5 if the content is genuinely
  novel for LinkedIn purposes (i.e., not already widely cited in the SE community).
- arXiv preprints with direct MBSE/SysML relevance: score Novelty at 4 if the technique
  or finding has not appeared in prior posts.
- NASA/MITRE/RAND technical reports: score Practicality at 4–5 for operational findings;
  score Timeliness at 3 if published within the last 90 days.
- Timeliness exception: for peer-reviewed publications and technical reports, reduce the
  Timeliness penalty. A 60-day-old IEEE paper is still a Timeliness-3 if it has not been
  widely discussed in SE community channels.
- Papers with no accessible abstract or preprint (fully paywalled, no summary): exclude.
- Workshop position papers with no empirical content or novel argument: exclude.

EVALUATION CRITERIA — score each candidate 1–5 on:

  Relevance: How directly does it address SysML/MBSE practice?
    5 — directly addresses SysML/MBSE practice with specific findings or tools
        (e.g. a new SysML v2 tooling adoption study in aerospace)
    1 — mentions "systems" in passing; primarily about another field
        (e.g. a software DevOps post with one sentence referencing SE)

  Novelty: Is this genuinely new information or a fresh angle on a live debate?
    5 — first empirical study, new spec release, or original finding not yet
        discussed in SE community channels
    1 — restatement of existing MBSE documentation or widely-known information
        with no new angle or argument

  Practicality: Can a working systems engineer act on or argue with this?
    5 — a practitioner can directly apply, adopt, or push back on this
        (new tool comparison, methodology ROI data, process failure analysis)
    1 — purely theoretical with no actionable takeaway for practitioners

  Timeliness: How recent is it?
    5 — published in the last 2 days
    4 — published 3–4 days ago
    3 — published 5–7 days ago
    2 — published 8–10 days ago
    1 — older (publications only, up to 90 days, if genuinely novel)

  Debate Potential: Will this generate a professional reaction from Photi's audience?
    5 — challenges a prevailing assumption or presents data that contradicts
        common practice (e.g. empirical evidence that MBSE ROI claims are overstated)
    1 — uncontroversial announcement or incremental update nobody will disagree with
