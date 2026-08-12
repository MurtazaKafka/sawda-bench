# Sawda pilot — results

All systems are open-weights; the full comparison reproduces with one Fireworks API key (NLLB ran on a Modal CPU worker; same checkpoint). All numbers below derive from `results/human_judgments.jsonl` (n=180 blind judgments by one native Dari-speaking validator over a stratified 30-item subset), `results/translations.jsonl`, and `calls/*.jsonl`.

## Headline: intent preservation (human labels)

| system                  |   n |   preserved |   degraded |   inverted |   approp |
|:------------------------|----:|------------:|-----------:|-----------:|---------:|
| C kimi-k3 audience      |  30 |       0.167 |      0.767 |      0.067 |    4.733 |
| D kimi-k3 instructional |  30 |       0.3   |      0.533 |      0.167 |    4.567 |
| B kimi-k3 naive         |  30 |       0.2   |      0.667 |      0.133 |    3.4   |
| A nllb-600M             |  30 |       0.133 |      0.767 |      0.1   |    3.467 |
| F gpt-oss-20b audience  |  30 |       0.233 |      0.7   |      0.067 |    4.933 |
| E gpt-oss-20b naive     |  30 |       0.2   |      0.667 |      0.133 |    4.667 |

### By direction

| system                  | direction   |   n |   preserved |   degraded |   inverted |   approp |
|:------------------------|:------------|----:|------------:|-----------:|-----------:|---------:|
| C kimi-k3 audience      | en2fa       |  15 |       0.267 |      0.6   |      0.133 |    4.133 |
| C kimi-k3 audience      | fa2en       |  15 |       0.067 |      0.933 |      0     |    5.333 |
| D kimi-k3 instructional | en2fa       |  15 |       0.2   |      0.467 |      0.333 |    3.933 |
| D kimi-k3 instructional | fa2en       |  15 |       0.4   |      0.6   |      0     |    5.2   |
| B kimi-k3 naive         | en2fa       |  15 |       0.067 |      0.733 |      0.2   |    3.2   |
| B kimi-k3 naive         | fa2en       |  15 |       0.333 |      0.6   |      0.067 |    3.6   |
| A nllb-600M             | en2fa       |  15 |       0.133 |      0.8   |      0.067 |    4     |
| A nllb-600M             | fa2en       |  15 |       0.133 |      0.733 |      0.133 |    2.933 |
| F gpt-oss-20b audience  | en2fa       |  15 |       0.267 |      0.667 |      0.067 |    5     |
| F gpt-oss-20b audience  | fa2en       |  15 |       0.2   |      0.733 |      0.067 |    4.867 |
| E gpt-oss-20b naive     | en2fa       |  15 |       0.2   |      0.6   |      0.2   |    4.733 |
| E gpt-oss-20b naive     | fa2en       |  15 |       0.2   |      0.733 |      0.067 |    4.6   |

### Validator quick-flags

| system                  |   n |   iranian_register |   broken_syntax |   wrong_language |
|:------------------------|----:|-------------------:|----------------:|-----------------:|
| C kimi-k3 audience      |  30 |                  0 |               7 |                3 |
| D kimi-k3 instructional |  30 |                  0 |               6 |                4 |
| B kimi-k3 naive         |  30 |                  1 |              25 |                8 |
| A nllb-600M             |  30 |                  7 |               2 |                0 |
| F gpt-oss-20b audience  |  30 |                  4 |               0 |                0 |
| E gpt-oss-20b naive     |  30 |                  1 |               1 |                2 |

## Preregistered questions

**Q1 (threshold test).** D (instructional) preserved intent in 30.0% of judgments vs C (audience) 16.7% (n=30 each; 30-item subset). Mean appropriateness: D 4.57 vs C 4.73.

**Q2 (direction asymmetry).** Intent inversion/deletion (rating 1): fa2en 5.6% vs en2fa 16.7% (n=90 / 90).

## LLM judge calibration — failed, reported as a finding

Machine labels were **not** extended to unjudged items: both judge arms stayed far below the preregistered 80% exact-agreement bar after one rubric iteration, so every evaluation number in this report is human-labeled.

- DeepSeek v4-pro: n=178, intent exact 48.3%, off-by-one 96.6%, appropriateness Pearson r 0.38
- Fable agents: n=180, intent exact 48.9%, off-by-one 99.4%, appropriateness Pearson r 0.63

Judge families: systems are Kimi (B–D) and gpt-oss (E–F); judges are DeepSeek (scripted via Fireworks, reproducible) and Claude Fable 5 agents (run via a Claude Code subscription session — not reproducible from the API key alone; Fable also drafted the item pool's reference renders, a possible style-affinity bias).

## Cost per 1,000 messages

| system                  | basis            |   usd_per_1k |
|:------------------------|:-----------------|-------------:|
| A nllb-600M             | self-hosted est. |       0.0625 |
| B kimi-k3 naive         | API measured     |      10.3192 |
| C kimi-k3 audience      | API measured     |      10.5453 |
| D kimi-k3 instructional | API measured     |       7.8746 |
| E gpt-oss-20b naive     | API measured     |       0.0994 |
| F gpt-oss-20b audience  | API measured     |       0.2237 |
| E/F gpt-oss-20b         | self-hosted est. |       0.4167 |

Assumptions for self-hosted rows: $2.50/GPU-hour (A100-80G class, mid-2026 on-demand); NLLB-600M ~40k msgs/GPU-h batched; gpt-oss-20B ~6k msgs/GPU-h via vLLM on short messages. API rows use measured tokens at pinned prices (kimi-k3 $3/$15 per 1M in/out; gpt-oss-20b $0.07/$0.30; docs.fireworks.ai, 2026-08-10). API rows are per 1,000 SUCCESSFUL messages: 4 of 108 small-system calls produced no translation at any reasoning budget; their (unrecorded) tokens are excluded from the averages. The 3 of those 4 that fell in the judged subset were rated intent 1, appropriateness 1.


Total pilot API spend (all cached calls in `calls/*.jsonl`, translation + judging): **$3.83** ($1.87 kimi-k3, $1.94 deepseek-v4-pro judge, $0.02 gpt-oss-20b), plus ~1 minute of Modal CPU for NLLB.

## Five side-by-side failures

### syn-01

> **Source:** چی پیسه خیر است جان برادر؟ موتر از خود ماست، اصلا قابل شما ره نداره!
>
> **Context:** Speaker: a mechanic who has just finished repairing a taxi's brakes. Listener: the taxi driver, a repeat customer, holding out the payment. The bill was agreed that morning.

- **A nllb-600M** (intent 1, approp 1):

  What is wrong with us, John? We are dead, so you cannot escape.

- **B kimi-k3 naive** (intent 3, approp 6):

  **Translation:**

"What money, dear brother? The car is ours anyway — it's not even worthy of you!"

**A more natural-sounding English version:**

"Forget about the money, brother! The car belongs to us — don't even mention it!"

**Note:** This message is written in Dari (Afghan Persian) and reflects the cultural practice of *ta'arof* — polite hospitality. The phrase "قابل شما نیست" (literally "it

### lit-18

> **Source:** Thanks so much for sorting out the shipment — we owe you one!
>
> **Context:** Speaker: a British importer whose Afghan partner spent a day fixing a customs problem for him. Listener: that partner. Sent as a quick text message.

- **E gpt-oss-20b naive** (intent 1, approp 1):

  

- **D kimi-k3 instructional** (intent 3, approp 6):

  خیلی سپاس که مشکل محموله را حل کردید — واقعاً مدیون لطف تان هستیم!

### lit-20

> **Source:** That's very kind of you, but I really can't accept this — company policy doesn't allow gifts.
>
> **Context:** Speaker: a foreign inspector offered a box of saffron by a factory owner at the end of a site visit. Listener: the owner, for whom the gift is hospitality, not a bribe. The refusal is real and final, not politeness.

- **E gpt-oss-20b naive** (intent 1, approp 1; validator: “translation does not exist.”):

  

- **C kimi-k3 audience** (intent 3, approp 1):

  The task: translate a message into Dari. The speaker is a foreign inspector who was offered a box of saffron by a factory owner at the end of a site visit. The listener is the owner, for whom the gift is hospitality, not a bribe. The refusal is real and final, not politeness (not ta'arof). The translation must convey warmth/gratitude but firm, final refusal, citing company policy.

Key challenge: 

### syn-25

> **Source:** Don't worry about the invoice for now. let's sort it out later this week.
>
> **Context:** Speaker: a British buyer whose Afghan supplier apologized that the invoice was delayed by a banking problem. Listener: the supplier. The buyer means the payment schedule slips a few days, nothing more.

- **E gpt-oss-20b naive** (intent 1, approp 2; validator: “wrong translation of invoice into فاکتور! Intent has not been persevered as well.”):

  حالا در مورد فاکتور نگران نشو. این هفته بعد آن را حل می‌کنیم.

- **D kimi-k3 instructional** (intent 3, approp 6):

  فعلاً به خاطر فاکتور نگران نباشید، هیچ مشکلی نیست. همین هفته آن را حل می‌کنیم.

### syn-12

> **Source:** فکرهایمه میکنم؛ اگر قسمت بود، فردا میایم.
>
> **Context:** Speaker: a customer at an electronics shop after an hour of comparing two televisions and hearing the last price. Listener: the shopkeeper, who has offered to set one aside.

- **B kimi-k3 naive** (intent 1, approp 2):

  **Translation:**

"I'm lost in my thoughts; if it's meant to be, I'll come tomorrow."

**A few notes on the nuances:**

- **فکرهایمه میکنم** (colloquial for فکرهایم را می‌کنم) literally means "I'm doing my thoughts" — idiomatically, it conveys being deep in thought or pondering something.
- **اگر قسمت بود** is a common Persian expression meaning "if it's fated/destined" — similar in spirit to "God

- **C kimi-k3 audience** (intent 2, approp 6):

  I'll think it over — if it's meant to be, we'll come back tomorrow.

## By failure class

| system                  | failure_class              |   n |   preserved |   degraded |   inverted |   approp |
|:------------------------|:---------------------------|----:|------------:|-----------:|-----------:|---------:|
| C kimi-k3 audience      | indirect_refusal_as_assent |   6 |       0     |      0.833 |      0.167 |    5     |
| C kimi-k3 audience      | intent_inversion           |   7 |       0     |      1     |      0     |    4.429 |
| C kimi-k3 audience      | obligation_face_deleted    |   5 |       0.4   |      0.6   |      0     |    4.4   |
| C kimi-k3 audience      | register_violation         |   6 |       0.167 |      0.667 |      0.167 |    5.333 |
| C kimi-k3 audience      | ritual_refusal_literal     |   6 |       0.333 |      0.667 |      0     |    4.5   |
| D kimi-k3 instructional | indirect_refusal_as_assent |   6 |       0     |      1     |      0     |    4.667 |
| D kimi-k3 instructional | intent_inversion           |   7 |       0.571 |      0.429 |      0     |    5.429 |
| D kimi-k3 instructional | obligation_face_deleted    |   5 |       0.6   |      0.4   |      0     |    6.2   |
| D kimi-k3 instructional | register_violation         |   6 |       0.167 |      0.5   |      0.333 |    4.333 |
| D kimi-k3 instructional | ritual_refusal_literal     |   6 |       0.167 |      0.333 |      0.5   |    2.333 |
| B kimi-k3 naive         | indirect_refusal_as_assent |   6 |       0     |      0.667 |      0.333 |    2.667 |
| B kimi-k3 naive         | intent_inversion           |   7 |       0.286 |      0.571 |      0.143 |    3.714 |
| B kimi-k3 naive         | obligation_face_deleted    |   5 |       0.2   |      0.8   |      0     |    3.2   |
| B kimi-k3 naive         | register_violation         |   6 |       0     |      1     |      0     |    3.167 |
| B kimi-k3 naive         | ritual_refusal_literal     |   6 |       0.5   |      0.333 |      0.167 |    4.167 |
| A nllb-600M             | indirect_refusal_as_assent |   6 |       0.167 |      0.833 |      0     |    3.5   |
| A nllb-600M             | intent_inversion           |   7 |       0     |      0.857 |      0.143 |    3.429 |
| A nllb-600M             | obligation_face_deleted    |   5 |       0     |      1     |      0     |    3.2   |
| A nllb-600M             | register_violation         |   6 |       0.167 |      0.667 |      0.167 |    3.833 |
| A nllb-600M             | ritual_refusal_literal     |   6 |       0.333 |      0.5   |      0.167 |    3.333 |
| F gpt-oss-20b audience  | indirect_refusal_as_assent |   6 |       0     |      1     |      0     |    5     |
| F gpt-oss-20b audience  | intent_inversion           |   7 |       0.143 |      0.857 |      0     |    5     |
| F gpt-oss-20b audience  | obligation_face_deleted    |   5 |       0.2   |      0.6   |      0.2   |    3.4   |
| F gpt-oss-20b audience  | register_violation         |   6 |       0.333 |      0.667 |      0     |    5.167 |
| F gpt-oss-20b audience  | ritual_refusal_literal     |   6 |       0.5   |      0.333 |      0.167 |    5.833 |
| E gpt-oss-20b naive     | indirect_refusal_as_assent |   6 |       0.167 |      0.833 |      0     |    5     |
| E gpt-oss-20b naive     | intent_inversion           |   7 |       0     |      0.857 |      0.143 |    4.571 |
| E gpt-oss-20b naive     | obligation_face_deleted    |   5 |       0.2   |      0.6   |      0.2   |    3.6   |
| E gpt-oss-20b naive     | register_violation         |   6 |       0.333 |      0.667 |      0     |    5.667 |
| E gpt-oss-20b naive     | ritual_refusal_literal     |   6 |       0.333 |      0.333 |      0.333 |    4.333 |

## Caveats, honestly

- n=30 items judged (of 54 evaluated; 60 validated minus 6 held out for few-shot), 180 judgments; single validator who is also the item author/editor; no inter-annotator data.
- Both LLM-judge families failed calibration; results are human-only and the judged subset, while stratified, is small.
- Items are fictional and partly synthetic (32 of 60); synthetic items were human-validated but share pragmatic cores with their parents.
- kimi-k3 outputs sometimes include visible deliberation/commentary; judged verbatim as delivered text. This also means the 'blind' judging batches carry stylistic tells (headers, leaked reasoning) that could let a judge guess the model family, though never the system label.
- The Dari register target is Afghan; several systems drifted to Iranian Farsi (see flags table) — flagged by the validator, penalized mainly in appropriateness.
