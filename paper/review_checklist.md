# Review checklist for the Sawda paper

Distilled from current (*ACL / ARR-era) best-practice guidance for benchmark + evaluation
papers and from experimental-design norms for small-n human-evaluation studies.
Compiled 2026-08-12 for the Sawda pilot paper. Each item ends with the sources it derives from.

## A. Benchmark / resource-paper checklist (what reviewers reward and punish)

1. **Fill the Responsible NLP Checklist mindset into the paper itself, not an appendix
   afterthought.** ARR's Responsible NLP Research checklist (based on the NeurIPS 2021
   checklist, Rogers/Baldwin/Leins EMNLP 2021 "responsible data use" checklist, and Dodge
   et al. 2019 "Show Your Work") maps directly onto what reviewers ask: experimental
   details, annotation protocols, consent/IRB, limitations, societal impact. Since EMNLP 2025
   the filled checklist is published with accepted papers, and a bad-faith checklist is
   grounds for desk rejection.
   Sources: https://aclrollingreview.org/responsibleNLPresearch/ ,
   https://aclrollingreview.org/static/responsibleNLPresearch.pdf ,
   https://arxiv.org/abs/2109.06598 (Rogers, Baldwin & Leins 2021),
   https://arxiv.org/html/2608.09280 (EMNLP 2025 checklist analysis).

2. **Document the annotation protocol completely**: who annotated, their relationship to
   the data (author-annotator must be disclosed), instructions/rubric given, interface,
   blinding, item order randomization, payment/consent where applicable, and
   inter-annotator agreement — or an explicit statement of why IAA is absent and what
   replaces it. Reviewers of resource papers check annotator provenance first.
   Sources: ARR reviewer guidelines https://aclrollingreview.org/reviewerguidelines ;
   van der Lee et al. 2021, "Human evaluation of automatically generated text"
   https://www.sciencedirect.com/science/article/pii/S088523082030084X .

3. **Data documentation in the data-statement / datasheet sense**: language varieties
   (dialect! — Afghan Dari vs Iranian Farsi is exactly the kind of variety distinction
   Bender & Friedman require), speaker/annotator demographics as relevant, curation
   rationale, tranche provenance, licensing, intended use, and known coverage gaps.
   Sources: Bender & Friedman 2018 (TACL, "Data Statements for NLP")
   https://aclanthology.org/Q18-1041/ ; Gebru et al., "Datasheets for Datasets"
   https://arxiv.org/abs/1803.09010 .

4. **Report quality control and position against existing datasets.** A survey of
   benchmark papers found 23% report no quality control and 49% never compare to other
   datasets; reviewers increasingly expect both (validation pass rates, edit rates,
   discard counts; explicit deltas from the nearest benchmarks).
   Sources: https://arxiv.org/pdf/2602.06221 (BenchMarker) ; ARR reviewer guidelines.

5. **Reproducibility block**: model identifiers pinned with dates, decoding parameters,
   prompts, token budgets, caching, exact costs, and code/data release. Dodge et al.'s
   "Show Your Work" items (compute, hyperparameters, expected variation) are the floor.
   Sources: https://arxiv.org/abs/1909.03004 (Dodge et al. 2019); ARR checklist B/C items.

6. **Claims must match the evidence type.** "Reject-if-not-SOTA" style reviewing is
   discouraged, but its mirror obligation on authors is calibration: a 30-item pilot
   licenses "suggests/consistent with", not "establishes/demonstrates". Reviewers are
   explicitly told to flag overclaiming ("lazy thinking" taxonomy includes unsupported
   generality claims).
   Sources: ARR reviewer guidelines; https://arxiv.org/pdf/2504.11042 (LazyReview).

7. **Limitations and ethics sections that do work**: name the single-annotator risk,
   dialect-authority concentration, synthetic-item share, contamination/leakage vectors,
   and community-impact considerations (data about communities under persecution needs
   an explicit consent + de-identification statement).
   Sources: ARR Responsible NLP checklist; Rogers et al. 2021.

## B. Small-n human-evaluation statistics (what to report and how)

8. **Report a test, or don't use test-flavored language.** Only ~23% of NLG papers report
   statistical analyses at all (van der Lee et al. 2021); silent claims of
   "indistinguishable"/"significant" without a named test are a standard reviewer
   complaint. Every comparison-flavored sentence should either carry a computed statistic
   or be phrased descriptively.
   Source: https://www.sciencedirect.com/science/article/pii/S088523082030084X .

9. **Paired designs need paired tests.** When the same items are judged under every
   system (as here), binary outcomes (preserved vs not) call for McNemar's test; with
   discordant-pair counts below ~25, use the **exact** (binomial) McNemar. Dietterich
   1998 shows it is the only test with acceptable Type I error when systems are run once
   on one test set.
   Sources: Dietterich 1998 https://doi.org/10.1162/089976698300017197 ;
   https://rasbt.github.io/mlxtend/user_guide/evaluate/mcnemar/ ;
   Cambridge NLE "How to do human evaluation"
   https://www.cambridge.org/core/journals/natural-language-engineering/article/how-to-do-human-evaluation-a-brief-introduction-to-user-studies-in-nlp/85A5D9550233DFC3CF356DD7041E3306 .

10. **Unpaired proportions with small counts: Fisher's exact test**, not chi-square/Wald.
    For CIs on proportions, use Wilson score (or adjusted-Wald/exact) intervals — normal
    approximations misbehave near 0 and at n≤30.
    Sources: https://measuringu.com/small-n/ ; Newcombe 1998 via
    https://pubmed.ncbi.nlm.nih.gov/15719354/ .

11. **Ordinal data is not interval data.** Likert/appropriateness scales should be
    analyzed with rank/ordinal methods (Wilcoxon signed-rank for paired) rather than
    t-tests on means; treating ordinal as interval further reduces power (Howcroft &
    Rieser 2021).
    Source: https://aclanthology.org/2021.emnlp-main.501/ .

12. **Multiple comparisons**: with 6 systems there are 15 pairwise tests; either correct
    (Bonferroni/Holm) or — better for a pilot — preregister the few comparisons that
    matter and report the rest descriptively. State clearly which comparisons were
    preregistered.
    Sources: Cambridge NLE guide; van der Lee et al. 2021.

13. **Acknowledge clustering/non-independence.** 180 judgments over 30 items × 6 systems
    are not 180 independent observations for between-direction or pooled comparisons;
    either test at the item level or state the dependence when reporting judgment-level
    tests.
    Source: van der Lee et al. 2021; https://arxiv.org/pdf/2202.06935 ("Repairing the
    Cracked Foundation").

14. **Expect and admit underpowering.** Median human evals (~100 items) are underpowered
    for small effects (Card et al. 2020, "With Little Power Comes Great Responsibility");
    a 30-item pilot cannot distinguish moderate effects, so absence of significance is
    not evidence of equivalence — never convert a non-significant test into "matches" or
    "indistinguishable" without a CI on the difference.
    Sources: https://aclanthology.org/2020.emnlp-main.745/ (Card et al. 2020);
    https://measuringu.com/small-n/ .

15. **CIs even when wide.** Report 95% intervals for headline rates; wide intervals are
    informative, and overlapping CIs mean rankings should be presented as provisional.
    Sources: https://measuringu.com/small-n/ ; van der Lee et al. 2021.

16. **MT-specific norms**: paired bootstrap resampling (Koehn 2004) is the community
    default for system comparison on shared test sets; for human paired binary judgments,
    exact McNemar; report per-direction results separately (Müller's "seven
    recommendations").
    Sources: https://aclanthology.org/W04-3250.pdf (Koehn 2004);
    https://bricksdont.github.io/posts/2020/12/seven-recommendations-for-mt-evaluation/ .

## C. Sawda-specific action items derived from A+B

- [ ] Replace "statistically indistinguishable" (Sec. 5.4) with a computed exact test +
      CI on the difference, or descriptive phrasing (items 8, 9, 14).
- [ ] Add Wilson 95% CIs for headline preserved rates (item 10, 15).
- [ ] Exact McNemar for the two preregistered comparisons (D vs C; direction asymmetry
      handled as unpaired Fisher at judgment level with clustering caveat, or item-level
      test) (items 9, 12, 13).
- [ ] State that pairwise system tests beyond the preregistered ones are exploratory
      (item 12).
- [ ] Verify section cross-references, table/caption consistency, terminology
      (fa2en/en2fa vs Dari-to-English) (item 6, clarity).
- [ ] Ensure annotator-provenance disclosure is prominent and IAA absence is scoped
      (items 2, 7 — already partially present in Limitations).
- [ ] Keep claims verbs calibrated to pilot scale (item 6, 14).
