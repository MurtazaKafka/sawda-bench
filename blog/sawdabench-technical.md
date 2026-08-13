# How I built a translation benchmark in three days for $3.83

This is the engineering companion to [The shopkeeper who refuses your money](/writing/shopkeeper). That post is about what I found; this one is about how the machine that found it works, and the five or six decisions that turned out to matter. If you have ever wanted to run a real evaluation — with human judgment in the loop, statistics you can defend, and numbers you can trace — this is the whole playbook. Total API spend: $3.83.

## The shape of the thing

Sawda is 60 short Dari/English trade messages, six translation systems, 180 blind human judgments (mine), and two LLM judges that failed to replace me. The pipeline is five phases with two human gates:

```
items (drafted) -> GATE A: validate -> translate (6 systems) ->
GATE B: blind judging -> LLM judge calibration -> analysis
```

The core design constraint was honest and selfish at the same time: my hours were the scarce resource. I am the only native Dari speaker on this project, so every design decision pushed work away from me and toward the machine — except the two gates, where my judgment is the entire point and nothing was allowed to touch it.

## Every API call is cached by its own hash

The first piece of infrastructure I built was not a model call — it was a cache. Every request to the API gets serialized, hashed, and looked up in an append-only JSONL file before any network call happens:

```python
key = sha256(json.dumps(body, sort_keys=True)).hexdigest()
```

Temperature 0 everywhere, so a repeated request is by definition the same request. This sounds like a cost optimization, and it is — reruns are free — but the real payoff is psychological: **when reruns cost nothing, you rerun everything.** Crashed mid-run? Rerun. Changed one system's prompt? Rerun; only the changed calls hit the network. The cache also logs tokens per call, which is how I can tell you the exact spend, per model, at any moment. If you build one piece of infrastructure for an eval, build this.

## Pin your models against the live catalog, and write down what you find

The plan said "use a 32B-class open model as the cheap arm." The live serverless catalog, the day I pinned models, had no 32B-class model at all. So the cheap arm became gpt-oss-20b, and that deviation is written down in the README with the pin date. This felt like bookkeeping at the time. It became load-bearing later, when the paper needed to say precisely what was compared and a reviewer needed to check it. Model IDs drift, catalogs change weekly; "the strongest open model" is not a fact, but "kimi-k3, pinned 2026-08-10, verified with a 1-token ping" is.

## The failures you keep are data; the failures you fix are bugs — know which is which

Three model behaviors nearly wrecked the runs, and the interesting part is that each one demanded a different response.

**gpt-oss-20b reasons itself to death.** It spends its token budget on internal chain-of-thought (`reasoning_content`) before emitting a single character of translation. At a 1,024-token budget it frequently produced *nothing*. I raised the budget to 4,096, then 16,384, then 32,768 — and four calls still returned zero translation, having spent thirty thousand tokens thinking about taarof. Those four are **recorded as empty outputs with a flag, and scored as deleted intent where judged**. That's a real property of the system a buyer would deploy, not an infrastructure hiccup to paper over.

**Kimi K3 thinks out loud in its output field.** No think-tags, no separate channel — deliberation just arrives as content, and at my original 1,024-token cap, 23 outputs were truncated mid-thought. That one *was* a bug — mine. A truncated deliberation isn't what the system produces; it's what my budget produced. I discarded those, reran everything at 4,096, and kept the chatty outputs verbatim, commentary and all, because a text message with three paragraphs of cultural footnotes *is* what your business partner would receive.

**My laptop couldn't run a 600M-parameter model.** The dedicated MT baseline (NLLB-600M) computed at roughly a 4% duty cycle on my 8GB MacBook — it was swap-thrashing, 14.6GB deep. Instead of fighting it, I moved that one system to a cloud CPU worker: same checkpoint, same decoding settings, done in about a minute, host recorded in every output row. Knowing when the machine is the problem saves an afternoon.

## Blind judging is a data structure, not a vibe

"I judged blind" is easy to claim and easy to fake by accident. The blindness here is constructed: a judging plan — built once, saved to disk — takes a stratified 30-item subset (balanced across direction and failure class), crosses it with all six systems, shuffles the 180 pairs with a fixed seed, and enforces one constraint: **two translations of the same item are never adjacent**, so I can't diff systems side by side. The web UI shows me source, context, one candidate, and nothing else; system identity never leaves the server. Every judgment appends to disk immediately, so quitting mid-session costs nothing. I rated intent (preserved / degraded / inverted) and appropriateness (1–7), and — after the first four judgments made the pattern obvious — added three one-click flags (Iranian register, broken syntax, wrong language) so a recurring observation became a countable column instead of a pile of free-text notes.

## The judges failed, and the interesting number is *why*

After my 180 labels existed, I calibrated two LLM judges against them — deliberately from model families different from every system being judged, to dodge self-preference. Both landed near 48–49% exact agreement, which sounds like "half right" until you compute the baseline: my labels are 68% "degraded," so a judge that answers "degraded" every single time beats both models by twenty points. Chance-corrected, the judges score kappa 0.14 and 0.17. Meanwhile they agree with me *within one point* 96.6% and 99.4% of the time. That pair of numbers is the finding: LLM judges track coarse quality and cannot see the category boundary a native speaker feels instantly. The protocol mattered here — I pre-committed to an 80% agreement bar and one rubric iteration before any machine label could substitute for a human one. The bar did its job: it failed loudly, and every number in the paper stayed human-labeled.

## Small-n statistics, or: let the reviewer live in your repo

With 30 judged items, most differences between systems are not statistically resolvable, and the temptation is to narrate around that. The discipline that worked: exact tests only (McNemar on paired items, Fisher for the direction contrast, sign tests for ordinal ratings), Wilson intervals on every headline rate, an item-level test wherever judgments cluster within items — and every statistic computed by a script that lives in the repo, so any number in the paper can be regenerated by anyone.

Then I did the thing I'd recommend most: **I ran adversarial review agents against my own results before anyone else could.** One audit recomputed every table cell from the raw files (it found the numbers clean but caught two undisclosed methodology wordings). A second, harsher review of the paper draft caught two swapped superlatives, a mechanism claim contradicted by my own data, and the missing chance correction above. Every fix made the findings smaller and the paper stronger. Adversarial review is cheap now. There is no excuse.

## The bill

$1.87 for the frontier translation arm, $1.94 for the judge calibration, two cents — really — for the small model, about a minute of cloud CPU for the MT baseline. $3.83, plus one native speaker's evening of judging. The expensive ingredient was never compute. It was the 180 human judgments, and the infrastructure's whole job was to make sure not one of them was wasted, contaminated, or unaccountable.

The repo — pipeline, judging studio, stats scripts, and all 180 judgments — is at [github.com/MurtazaKafka/sawda-bench](https://github.com/MurtazaKafka/sawda-bench), private while the release checklist finishes. If you're building an eval with humans in the loop, steal the shape: cache by request hash, pin and datestamp everything, record failures as data, construct your blindness, pre-commit your bars, and hire an adversary before your reviewers do it for free.
