# OpenAI Model Experiment Report

## Executive Summary

This report documents controlled OpenAI model comparison runs for the Contextual Post Explainer backend.

The first experiment compared the latest available pre-experiment operational baseline against a new OpenAI stack using:

```text
SEARCH_PROVIDER=tavily
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-5.1
COMPARISON_GROUP_ID=llm_5_1_eval
COMPARISON_CONFIG_ID=newer_full
```

The test set contained 23 Bluesky post URLs that had already been used during development and validation. The comparison used the latest available baseline run for each URL and the latest `llm_5_1_eval/newer_full` run for the same URL.

The new model stack produced a material improvement in reliable output generation:

| Metric | Baseline | OpenAI 5.1 stack | Change |
| --- | ---: | ---: | ---: |
| Comparable URLs | 23 | 23 | 0 |
| Completed explanations | 18 | 23 | +5 |
| No-explanation outcomes | 5 | 0 | -5 |
| Success rate | 78.26% | 100.00% | +21.74 pp |
| Average bullets per completed run | 3.50 | 4.48 | +0.98 |
| Average cited sources per completed run | 4.00 | 4.83 | +0.83 |
| Average warnings per completed run | 0.33 | 0.61 | +0.28 |
| Average total execution time | 32.60s | 30.84s | -1.76s |
| Average search time | 6.05s | 6.93s | +0.88s |
| Average source fetch time | 12.76s | 10.17s | -2.59s |

The most important improvement was not a small quality shift inside already successful runs. The major improvement was conversion of previously failed or no-explanation cases into usable cited explanations. Five posts that previously returned zero bullets now returned between 3 and 5 bullets.

The second experiment tested whether the same OpenAI 5.1 stack should use `text-embedding-3-large` instead of `text-embedding-3-small`. The result did not justify changing the default embedding model. Both configurations completed all 23 URLs, while the large embedding run had slightly lower average bullet count, slightly lower average cited-source count, slightly higher warning rate, and slightly higher runtime.

The third experiment tested Brave as a standalone live search provider while keeping the selected model stack fixed. Brave was faster and, when it completed, cited more sources on average. However, it produced 3 no-explanation outcomes where Tavily produced valid explanations. That makes Brave useful as a candidate input to Composite search, but not stronger than Tavily as a standalone default for this dataset.

At the same time, the new stack behaved more conservatively in a few cases. It reduced confidence from `high` to `medium` on some politically interpretive or broad-context posts and introduced warnings where the baseline had none. This is not automatically negative: it often reflects stricter citation compatibility and a better distinction between externally confirmed facts, author interpretation, background context, and claims that require stronger support.

## Scope and Data Sources

### Completed experiment

| Field | Value |
| --- | --- |
| Experiment id | `llm_5_1_eval` |
| Config id | `newer_full` |
| Date generated | 2026-05-16 UTC |
| URL count | 23 |
| Search provider | Tavily only |
| Generation model | `gpt-5.1` |
| Judge model | `gpt-5-mini` |
| Embedding model | `text-embedding-3-small` |
| Vision model | `gpt-5.1` |
| Summary artifact | `backend/runs/comparisons/llm_5_1_eval.json` |
| Raw run artifacts | `backend/runs/live/*.json` |

### Baseline definition

The baseline in this report is the latest available non-`llm_5_1_eval/newer_full` run for each of the same 23 URLs.

Important limitation: most older baseline artifacts were created before the backend consistently recorded model metadata in the run snapshot. As a result, 22 of 23 baseline artifacts have unknown model metadata in the artifact itself. Based on the project history, these represent the pre-OpenAI-5.1 operational baseline. However, future experiment reports should rely only on runs that include explicit `comparison_group_id`, `comparison_config_id`, search provider, generation model, judge model, embedding model, and vision model.

This limitation does not affect the paired behavior comparison by URL, but it does mean that the baseline should be interpreted as "previous operational behavior" rather than a perfectly isolated model-only A/B test.

## Methodology

The comparison used a paired design:

1. Select the 23 URLs already used in live validation.
2. For each URL, identify the latest pre-experiment baseline run.
3. Execute the same URL with the `newer_full` OpenAI 5.1 stack and Tavily-only search.
4. If a run was retried due to an infrastructure issue, use the latest successful run for comparative metrics while keeping the failed attempt available in Observability.
5. Compare each URL across both runs using:
   - Outcome status: `completed`, `no_explanation`, or `failed`.
   - Bullet count.
   - Confidence.
   - Warning count.
   - Cited source count.
   - Total execution time.
   - Search and fetch node durations.

The experiment intentionally kept the search provider fixed to Tavily and kept the embedding model as `text-embedding-3-small`. That means the main model differences in this run are:

| Layer | Baseline intent | New experiment |
| --- | --- | --- |
| Generation | Pre-5.1 generation stack | `gpt-5.1` |
| Judge / repair logic | Smaller prior judge stack | `gpt-5-mini` |
| Vision | Pre-5.1 vision stack | `gpt-5.1` |
| Embeddings | `text-embedding-3-small` | `text-embedding-3-small` |
| Search | Tavily in this experiment | Tavily |

Because embeddings and search provider stayed constant in the treatment configuration, the observed behavior change is most strongly associated with generation, vision, and judge behavior, plus the current hardened pipeline state.

## Aggregate Results

### Outcome reliability

| Outcome | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Completed | 18 | 23 |
| No explanation | 5 | 0 |
| Failed | 0 | 0 |

The new stack eliminated all no-explanation outcomes in this 23 URL set. This is the most important result. The previous system still avoided unsupported claims correctly, but it often did so by returning no bullets. The new stack more often found a safe middle ground: it generated contextual, cited bullets while preserving medium confidence and warnings when the evidence was not strong enough for high certainty.

### Bullet generation

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Average bullets per completed run | 3.50 | 4.48 |
| Runs with zero bullets | 5 | 0 |
| Runs with at least 3 bullets | 18 | 23 |

The proposal target is 3 to 5 bullets when evidence is sufficient. The new stack met that target for all 23 URLs. The baseline failed that target for 5 URLs because it returned no explanation.

### Source usage

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Average cited sources per completed run | 4.00 | 4.83 |
| Average search results received | 22.17 | 20.78 |

The new stack cited more sources on average even though it received slightly fewer search results. This suggests better use of the available evidence rather than simply more retrieval volume.

### Warning behavior

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Average warnings per completed run | 0.33 | 0.61 |
| Baseline confidence distribution | 15 high, 4 medium, 4 low |
| New confidence distribution | 13 high, 10 medium, 0 low |

Warnings increased from 0.33 to 0.61 per completed run. This should not be treated as a simple regression. The new stack generated explanations in 5 cases where the baseline returned no explanation. More completed outputs create more opportunities for warnings.

The confidence distribution also changed meaningfully:

- The new stack eliminated `low` confidence outputs in this set.
- The new stack produced more `medium` confidence outputs.
- Some previously `high` confidence cases became `medium` with warnings.

This indicates more conservative treatment of interpretive or politically charged claims. That is aligned with the architecture goal: avoid presenting author interpretation, weakly supported claims, or background-only material as fully confirmed fact.

### Runtime

| Metric | Baseline | OpenAI 5.1 stack | Interpretation |
| --- | ---: | ---: | --- |
| Average total time | 32.60s | 30.84s | Slightly faster overall |
| Average search time | 6.05s | 6.93s | Slightly slower search step |
| Average source fetch time | 12.76s | 10.17s | Faster source reading step |

The new stack was slightly faster overall despite using newer generation and vision models. The reduction came primarily from source fetch time. Search time increased modestly.

This result should be treated cautiously because external search and fetch latency are volatile. Still, there is no evidence from this run that `gpt-5.1` made end-to-end latency worse in the tested configuration.

## Paired URL Findings

### Overall paired behavior

| Category | Count | Share |
| --- | ---: | ---: |
| Improved | 19 | 82.6% |
| Regressed or more conservative | 3 | 13.0% |
| Unchanged | 1 | 4.3% |

The classification above considers completion status, bullet count, confidence, and warning count. "Regressed" should be read carefully: in this project, lower confidence or new warnings may represent better caution rather than worse quality.

### Previously no-explanation cases recovered

| URL | Baseline | OpenAI 5.1 stack | Result |
| --- | --- | --- | --- |
| `cats-are-evil.../3mlukzzu75s24` | no explanation, 0 bullets, low, 3 warnings | completed, 4 bullets, high, 0 warnings | Strong recovery |
| `drrenemd.../3mlvobbwrpc2a` | no explanation, 0 bullets, medium, 1 warning | completed, 5 bullets, medium, 0 warnings | Strong recovery |
| `kackbro.../3mlwdvdll7k2i` | no explanation, 0 bullets, low, 1 warning | completed, 4 bullets, medium, 1 warning | Recovered with caution |
| `lc1summit.../3mlvoqr367k25` | no explanation, 0 bullets, low, 1 warning | completed, 4 bullets, medium, 1 warning | Recovered with caution |
| `raywoodson5.../3mlw2uzungc2g` | no explanation, 0 bullets, low, 1 warning | completed, 3 bullets, medium, 2 warnings | Minimum viable recovery |

These are the strongest evidence points for the new model stack. The old behavior correctly avoided unsupported output, but the user-facing result was empty. The new stack produced usable explanations while still applying lower confidence and warnings when appropriate.

### Important improved cases

#### Robert Reich DOJ / DC Bar post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 3 | 5 |
| Confidence | medium | high |
| Warnings | 1 | 1 |
| Cited sources | not used for pair scoring | 8 |

This was one of the main validation posts. The new stack produced a fuller explanation with 5 bullets and high confidence while preserving a warning. It also used a broader cited source set, including legal/news context retrieved through Tavily.

#### SB 2471 / Citizens United post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 3 | 5 |
| Confidence | high | high |
| Warnings | 0 | 0 |

The new stack generated the full 5-bullet target without lowering confidence or adding warnings. This is a clean improvement.

#### Puck's Glen post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 3 | 5 |
| Confidence | high | high |
| Warnings | 0 | 0 |

This case matters because earlier manual testing showed risk of no-explanation behavior for scenic or location-based posts. In the final paired comparison, the new stack generated a richer explanation while maintaining high confidence.

#### LC / Trump-Xi image quote post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | no explanation | completed |
| Bullets | 0 | 4 |
| Confidence | low | medium |
| Warnings | 1 | 1 |

This is a strong example of improved multimodal usefulness. The post included an image with visible text and political interpretation. The new stack produced an explanation, but kept confidence medium and retained a warning, which is appropriate for a post mixing a quote, visual evidence, and author framing.

### More conservative or weaker cases

#### Solar parking lot post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 3 | 3 |
| Confidence | high | medium |
| Warnings | 0 | 1 |

This is not necessarily a harmful regression. The post includes broad factual claims about French law, US parking lots, and energy equivalence. A medium-confidence result with a warning may be more honest if some parts are only background-supported or require stronger primary sources.

#### Citizens United broad claim post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 5 | 4 |
| Confidence | high | medium |
| Warnings | 0 | 1 |

The new stack became more conservative. This should be reviewed manually because the phrase "end Citizens United" can be rhetorically true in a limited state-law sense but not literally true as a reversal of a Supreme Court precedent. Medium confidence and a warning may be the safer output.

#### Ricky Davila opinion post

| Metric | Baseline | OpenAI 5.1 stack |
| --- | ---: | ---: |
| Status | completed | completed |
| Bullets | 3 | 3 |
| Confidence | high | medium |
| Warnings | 0 | 1 |

The post is opinion-heavy and broad. The new stack's lower confidence is aligned with the source validation methodology: distinguish factual background from author interpretation and avoid over-certifying rhetorical predictions or opinions.

## Full Paired URL Table

| URL | Baseline status | Baseline bullets | Baseline confidence | Baseline warnings | New status | New bullets | New confidence | New warnings | Bullet delta |
| --- | --- | ---: | --- | ---: | --- | ---: | --- | ---: | ---: |
| `bencollins.../3mlw5ds5e7k2n` | completed | 5 | high | 1 | completed | 5 | high | 1 | +0 |
| `cats-are-evil.../3mlukzzu75s24` | no_explanation | 0 | low | 3 | completed | 4 | high | 0 | +4 |
| `drrenemd.../3mlvobbwrpc2a` | no_explanation | 0 | medium | 1 | completed | 5 | medium | 0 | +5 |
| `econanalytica.../3mlvjtn3k2k24` | completed | 4 | high | 0 | completed | 5 | high | 0 | +1 |
| `endcitizensunited.../3mlvlmxuem22p` | completed | 3 | high | 0 | completed | 5 | high | 0 | +2 |
| `forbes.com.../3mltjxyxp3x2r` | completed | 3 | medium | 1 | completed | 5 | high | 0 | +2 |
| `forbes.com.../3mlvcj5owhs25` | completed | 4 | high | 0 | completed | 5 | high | 0 | +1 |
| `intruder1500stevie.../3mluuntxous2a` | completed | 3 | high | 0 | completed | 3 | medium | 1 | +0 |
| `kackbro.../3mlwdvdll7k2i` | no_explanation | 0 | low | 1 | completed | 4 | medium | 1 | +4 |
| `kirstyislathomas.../3mlvr4xyq7s2o` | completed | 3 | high | 0 | completed | 5 | high | 0 | +2 |
| `lc1summit.../3mlvoqr367k25` | no_explanation | 0 | low | 1 | completed | 4 | medium | 1 | +4 |
| `luisnassif.../3mlvoq5kps22m` | completed | 4 | high | 1 | completed | 5 | high | 1 | +1 |
| `maddow.../3mlvxvwankc2p` | completed | 4 | high | 2 | completed | 5 | medium | 1 | +1 |
| `marcelias.../3mlwh5smd322i` | completed | 3 | high | 0 | completed | 4 | medium | 2 | +1 |
| `nbcnews.com.../3mlveype5b22m` | completed | 3 | high | 0 | completed | 5 | high | 0 | +2 |
| `onemoregoodman.../3mlus6pvupc2m` | completed | 3 | high | 0 | completed | 5 | high | 0 | +2 |
| `raywoodson5.../3mlw2uzungc2g` | no_explanation | 0 | low | 1 | completed | 3 | medium | 2 | +3 |
| `rbreich.../3mltultyalm2v` | completed | 3 | medium | 1 | completed | 5 | high | 1 | +2 |
| `repstansbury.../3mlvgeagk2c2p` | completed | 3 | high | 0 | completed | 5 | high | 0 | +2 |
| `romulobdias.../3mlvpwutjek2u` | completed | 3 | medium | 0 | completed | 4 | medium | 1 | +1 |
| `santiagomayer.com.../3mlvdf35orc24` | completed | 4 | high | 0 | completed | 5 | high | 0 | +1 |
| `sicilianrick.../3mlvwziwors2g` | completed | 5 | high | 0 | completed | 4 | medium | 1 | -1 |
| `therickydavila.../3mlvn22dr6s2h` | completed | 3 | high | 0 | completed | 3 | medium | 1 | +0 |

## Operational Findings

### 1. The new stack improves recovery from sparse or difficult posts

The clearest improvement was on posts that previously returned no explanation. The new stack recovered all 5 no-explanation cases while keeping confidence at medium when evidence quality required caution.

This matters for product usefulness. A system that frequently returns no bullets is safe but less helpful. A system that returns 3 to 5 cautious, cited bullets is both safer and more useful.

### 2. More warnings are acceptable when they reflect better claim discipline

Warnings increased from 0.33 to 0.61 per completed run. In isolation that looks worse, but the context matters:

- The new stack completed 5 additional posts.
- The new stack used medium confidence more often.
- The new stack flagged more cases where claims were interpretive, broad, or not fully supported by primary sources.

This aligns with the source validation methodology: the system should not only ask "is this source related?" It should ask "can this source support this type of claim?"

### 3. The new stack did not create a latency penalty in this run

Average runtime improved slightly from 32.60s to 30.84s. The result should not be overgeneralized because live search/fetch latency changes across runs. Still, the new model stack did not introduce an obvious runtime regression in this dataset.

### 4. The reranker needed hardening for long source text

One run initially failed during `rank_evidence` because an embedding input exceeded the model token limit:

```text
Invalid input: maximum input length is 8192 tokens.
```

The failure happened on the Romulo Dias post. This was not a model quality issue. It was an input management bug in the ranker. The ranker now truncates embedding input text to a bounded size before calling the embedding API. After the fix, the same URL completed successfully:

| URL | Retry result |
| --- | --- |
| `romulobdias.../3mlvpwutjek2u` | completed, 4 bullets, medium confidence, 5 sources, 1 warning, 38.13s |

This hardening should remain part of the production path. A single long source must not be able to fail the whole explanation pipeline.

### 5. Query planning still has room for improvement

The last run in the batch produced broad Trump/legal-case queries for an opinion-heavy post. The output still completed, but the search stage was not as targeted as it could be.

This suggests future work:

- Add stronger query decomposition rules for opinion-heavy posts.
- Require the query planner to preserve the specific event or claim anchor when available.
- Add a query-quality diagnostic metric to Analysis.

## Interpretation: What Improved With The New OpenAI Stack

The main improvement appears to be better decision-making under uncertainty.

The baseline often chose between two extremes:

- generate a short explanation when evidence was straightforward, or
- return no explanation when evidence was noisy, sparse, social, image-based, or interpretive.

The new stack more often found a useful middle path:

- generate the requested 3 to 5 bullets,
- cite available sources,
- lower confidence when appropriate,
- keep warnings when the claim/source relationship is weaker,
- avoid low-confidence dead ends.

This behavior is especially important for the product because users are asking for context around social posts. Social posts are often partial, rhetorical, visual, or opinionated. A good explainer needs to provide context without pretending that every statement is externally confirmed.

The new stack also appears better at using retrieved context. It cited more sources on average despite receiving fewer search results. That is a positive signal for evidence use and synthesis.

A second controlled experiment then changed only the embedding model from `text-embedding-3-small` to `text-embedding-3-large` while keeping `gpt-5.1`, `gpt-5-mini`, `gpt-5.1` vision, and Tavily fixed. That experiment did not show a product-level gain from the larger embedding model. Both configurations completed all 23 URLs, but the large embedding run produced slightly fewer bullets on average, slightly fewer cited sources, slightly more warnings, and slightly higher runtime.

## Recommendation After Experiment 1

The OpenAI 5.1 stack should remain in the candidate set for P2 comparative analysis. Based on this experiment, it is stronger than the previous operational baseline for user-facing explanation reliability.

Recommended next steps:

1. Run a clean `baseline_4o_small` experiment with explicit metadata and Tavily-only search.
2. Run `baseline_4o_large_embedding` with Tavily-only search to isolate embedding impact.
3. Run `newer_mini` with Tavily-only search to evaluate cost/performance tradeoff.
4. Run the search-provider matrix separately: Tavily, Brave, and Composite.
5. Compare final candidates using the Analysis page, but keep Observability available for run-level trace review.

The immediate product candidate after this experiment is:

```text
Generation: gpt-5.1
Judge: gpt-5-mini
Embedding: text-embedding-3-small
Vision: gpt-5.1
Search provider: Tavily for this model test
```

However, a final architecture decision should wait until the `newer_mini` and clean `baseline_4o_small` runs are complete with explicit metadata.

## Experiment Registry

| Experiment id | Status | Purpose | Search provider | Generation | Judge | Embedding | Vision | URLs | Result summary |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `llm_5_1_eval` / `newer_full` | Completed | Evaluate newest full OpenAI stack against prior operational behavior | Tavily | `gpt-5.1` | `gpt-5-mini` | `text-embedding-3-small` | `gpt-5.1` | 23 | 100% completed, 4.48 avg bullets, 4.83 avg cited sources, 30.84s avg time |
| `llm_5_1_large_embedding_eval` / `newer_full_large_embedding` | Completed | Isolate embedding size impact within the OpenAI 5.1 stack | Tavily | `gpt-5.1` | `gpt-5-mini` | `text-embedding-3-large` | `gpt-5.1` | 23 | 100% completed, 4.30 avg bullets, 4.78 avg cited sources, 31.78s avg time |
| `search_brave_5_1_eval` / `newer_full` | Completed | Evaluate Brave-only retrieval with the selected OpenAI 5.1 stack | Brave | `gpt-5.1` | `gpt-5-mini` | `text-embedding-3-small` | `gpt-5.1` | 23 | 20/23 completed, 3.91 avg bullets across all runs, 5.60 avg cited sources on completed runs, 25.85s avg time |
| `llm_4o_tavily_baseline` / `baseline_4o_small` | Planned | Establish clean explicit metadata baseline | Tavily | `gpt-4o` | `gpt-4o-mini` | `text-embedding-3-small` | `gpt-4o` | 23 | Pending |
| `llm_4o_large_embedding` / `baseline_4o_large_embedding` | Planned | Isolate embedding model impact | Tavily | `gpt-4o` | `gpt-4o-mini` | `text-embedding-3-large` | `gpt-4o` | 23 | Pending |
| `llm_5_mini_eval` / `newer_mini` | Planned | Evaluate lower-cost new model stack | Tavily | `gpt-5-mini` | `gpt-5-mini` | `text-embedding-3-small` | `gpt-5.1` | 23 | Pending |
| `search_provider_eval` / `search_tavily` | Planned | Compare search provider behavior | Tavily | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | 23 | Pending |
| `search_provider_eval` / `search_brave` | Planned | Compare search provider behavior | Brave | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | 23 | Pending |
| `search_provider_eval` / `search_composite` | Planned | Compare combined retrieval behavior | Composite | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | fixed after LLM decision | 23 | Pending |

## Interim Conclusion After Experiment 1

The first OpenAI 5.1 experiment produced a clear improvement in explanation reliability. The most important result is that all 23 tested URLs produced valid explanations, while the previous baseline produced 5 no-explanation outcomes on the same URL set.

The new stack also increased average bullet count and cited source count, while keeping runtime roughly stable. It did introduce more warnings and more medium-confidence outcomes, but this is largely consistent with the project's quality goals: the system should be useful without overclaiming.

The current evidence supports continuing with `gpt-5.1` plus `gpt-5-mini` as a strong candidate stack, while still running the planned clean baseline and mini-model experiments before making the final P2 decision.

## Experiment 2: Embedding Size Test

### Purpose

The second experiment isolated the embedding model while keeping the rest of the OpenAI stack and the search provider fixed:

```text
SEARCH_PROVIDER=tavily
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_VISION_MODEL=gpt-5.1
```

The control used `text-embedding-3-small`. The treatment used `text-embedding-3-large`.

This test answers a narrower question than the first model experiment: does the larger embedding model improve ranking and final explanation quality enough to justify its extra cost and operational weight?

### Configuration

| Field | Control | Treatment |
| --- | --- | --- |
| Experiment id | `llm_5_1_eval` | `llm_5_1_large_embedding_eval` |
| Config id | `newer_full` | `newer_full_large_embedding` |
| Search provider | Tavily only | Tavily only |
| Generation model | `gpt-5.1` | `gpt-5.1` |
| Judge model | `gpt-5-mini` | `gpt-5-mini` |
| Embedding model | `text-embedding-3-small` | `text-embedding-3-large` |
| Vision model | `gpt-5.1` | `gpt-5.1` |
| URL count | 23 | 23 |
| Summary artifact | `backend/runs/comparisons/llm_5_1_eval.json` | `backend/runs/comparisons/llm_5_1_large_embedding_eval.json` |

### Aggregate Results

| Metric | 5.1 + small embedding | 5.1 + large embedding | Change |
| --- | ---: | ---: | ---: |
| Comparable URLs | 23 | 23 | 0 |
| Completed explanations | 23 | 23 | 0 |
| No-explanation outcomes | 0 | 0 | 0 |
| Success rate | 100.00% | 100.00% | 0.00 pp |
| Average bullets per completed run | 4.48 | 4.30 | -0.17 |
| Average cited sources per completed run | 4.83 | 4.78 | -0.04 |
| Average warnings per completed run | 0.61 | 0.65 | +0.04 |
| High-confidence runs | 13 | 15 | +2 |
| Medium-confidence runs | 10 | 8 | -2 |
| Average search results received | 20.78 | 20.70 | -0.09 |
| Average ranked sources retained | 5.78 | 6.39 | +0.61 |
| Average total execution time | 30.84s | 31.78s | +0.94s |
| Average search time | 6.93s | 6.72s | -0.21s |
| Average source fetch time | 10.17s | 10.47s | +0.30s |
| Average ranking time | 0.85s | 1.03s | +0.18s |
| Average generation time | 7.06s | 8.06s | +1.00s |

The larger embedding model did not improve the main product reliability metric because the control already reached 100% completion on this URL set. It also did not improve average bullet count or cited-source count.

The strongest positive signal for `text-embedding-3-large` is ranking breadth: the ranker retained 6.39 sources on average, compared with 5.78 for `text-embedding-3-small`. However, that broader ranked set did not translate into more cited sources or more complete explanations.

### Paired Behavior

| Change type | Count |
| --- | ---: |
| Bullet count improved with large embedding | 2 |
| Bullet count unchanged with large embedding | 16 |
| Bullet count decreased with large embedding | 5 |
| Warning count decreased with large embedding | 1 |
| Warning count unchanged with large embedding | 20 |
| Warning count increased with large embedding | 2 |

The paired results show that most URLs behaved the same, but the deviations were slightly unfavorable for the larger embedding model on output density.

### Notable URL-Level Differences

| URL | Small embedding | Large embedding | Interpretation |
| --- | --- | --- | --- |
| `marcelias.../3mlwh5smd322i` | 4 bullets, medium, 2 warnings | 5 bullets, high, 2 warnings | Improved output density and confidence without increasing warnings. |
| `sicilianrick.../3mlvwziwors2g` | 4 bullets, medium, 1 warning | 5 bullets, high, 1 warning | Improved output density and confidence. |
| `drrenemd.../3mlvobbwrpc2a` | 5 bullets, medium, 0 warnings | 4 bullets, high, 0 warnings | Fewer bullets but higher confidence. Needs manual review to determine whether this is better precision or lost context. |
| `lc1summit.../3mlvoqr367k25` | 4 bullets, medium, 1 warning | 3 bullets, medium, 1 warning | Weaker output density with no confidence gain. |
| `maddow.../3mlvxvwankc2p` | 5 bullets, medium, 1 warning | 4 bullets, medium, 1 warning | Weaker output density with no confidence gain. |
| `repstansbury.../3mlvgeagk2c2p` | 5 bullets, high, 0 warnings | 4 bullets, high, 0 warnings | Weaker output density with no confidence gain. |
| `santiagomayer.com.../3mlvdf35orc24` | 5 bullets, high, 0 warnings | 3 bullets, medium, 1 warning | Clear regression for this run. |

The most concerning treatment case is `santiagomayer.com.../3mlvdf35orc24`, where the larger embedding model reduced the explanation from 5 bullets to 3, lowered confidence from high to medium, and added a warning. That does not prove the larger embedding is worse in general, but it shows that the larger model is not a monotonic improvement for this pipeline.

### Ranking and Latency Interpretation

The larger embedding model increased average ranking time from 0.85s to 1.03s. This is a small absolute increase, but it is still a direct cost in the stage the experiment was meant to improve.

The larger embedding model also increased average total runtime by 0.94s. This change is not entirely attributable to embeddings because live source fetching and generation latency vary between runs. Still, the larger embedding configuration did not produce an observable end-to-end speed benefit.

The ranker retained more sources on average with the larger embedding model, but final cited-source count was slightly lower. This suggests that broader semantic retrieval at the ranking stage may be adding candidates without improving the final evidence set selected by generation and citation validation.

### Recommendation From Experiment 2

Keep `text-embedding-3-small` as the current preferred embedding model for the P2 candidate stack.

The larger embedding model should remain available as an experimental option, but this run does not justify adopting it as the default. The control already reached 100% completion, and the large embedding treatment did not improve average bullets, cited sources, warning rate, or latency.

The current candidate remains:

```text
Generation: gpt-5.1
Judge: gpt-5-mini
Embedding: text-embedding-3-small
Vision: gpt-5.1
Search provider: Tavily for isolated LLM/embedding tests
```

The next useful experiment is not another embedding-size run. The next useful experiment is the lower-cost model stack:

```text
Generation: gpt-5-mini
Judge: gpt-5-mini
Embedding: text-embedding-3-small
Vision: gpt-5.1
Search provider: Tavily
```

That test will show whether the project can keep most of the `gpt-5.1` reliability gain at a lower generation cost.

## Experiment 3: Search Provider Test - Tavily vs Brave

### Purpose

The third experiment evaluated Brave as a standalone live search provider while holding the selected model stack fixed:

```text
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-5.1
```

The control was the completed Tavily-only run from `llm_5_1_eval/newer_full`. The treatment was a Brave-only run:

```text
SEARCH_PROVIDER=brave
COMPARISON_GROUP_ID=search_brave_5_1_eval
COMPARISON_CONFIG_ID=newer_full
```

This test isolates the search provider. The model stack, prompt stack, ranking logic, citation validation, and URL set remained fixed.

### Aggregate Results

| Metric | Tavily only | Brave only | Change |
| --- | ---: | ---: | ---: |
| Comparable URLs | 23 | 23 | 0 |
| Completed explanations | 23 | 20 | -3 |
| No-explanation outcomes | 0 | 3 | +3 |
| Success rate | 100.00% | 86.96% | -13.04 pp |
| Average bullets across all runs | 4.48 | 3.91 | -0.57 |
| Average bullets per completed run | 4.48 | 4.50 | +0.02 |
| Average cited sources per completed run | 4.83 | 5.60 | +0.77 |
| Average warnings per completed run | 0.61 | 0.45 | -0.16 |
| Average warnings across all runs | 0.61 | 0.52 | -0.09 |
| Average total execution time | 30.84s | 25.85s | -4.98s |
| Average search time | 6.93s | 4.43s | -2.50s |
| Average source fetch time | 10.17s | 8.34s | -1.83s |
| Average ranking time | 0.85s | 0.74s | -0.11s |
| Average generation time | 7.06s | 7.42s | +0.36s |
| Average search results received | 20.78 | 17.04 | -3.74 |
| Average ranked sources retained | 5.78 | 6.17 | +0.39 |
| Average source fetch discards | 4.91 | 2.48 | -2.44 |

Brave was faster and less noisy in several operational metrics. It returned fewer search results, had fewer source-fetch discards, and completed the retrieval stages faster. When Brave produced an explanation, it cited more sources on average than Tavily.

However, the product-level reliability result is weaker: Brave failed to produce any explanation for 3 URLs that Tavily handled successfully.

### Confidence Distribution

| Confidence | Tavily only | Brave only |
| --- | ---: | ---: |
| High | 13 | 13 |
| Medium | 10 | 7 |
| Low | 0 | 3 |

The 3 low-confidence Brave runs correspond to the 3 no-explanation outcomes. This is the main reason Brave should not replace Tavily as the standalone default based on this run.

### Paired Behavior

| Change type | Count |
| --- | ---: |
| Brave status worse than Tavily | 3 |
| Brave status better than Tavily | 0 |
| Brave bullet count improved | 2 |
| Brave bullet count unchanged | 13 |
| Brave bullet count decreased | 8 |
| Brave warning count decreased | 5 |
| Brave warning count unchanged | 16 |
| Brave warning count increased | 2 |

The paired comparison is mixed. Brave improved some individual outputs and often reduced warnings, but it also reduced bullet count more often than it improved it.

### No-Explanation Regressions

| URL | Tavily result | Brave result | Interpretation |
| --- | --- | --- | --- |
| `intruder1500stevie.../3mluuntxous2a` | completed, 3 bullets, medium, 1 warning | no explanation, 0 bullets, low, 1 warning | Brave found many relevant solar-parking sources but the final evidence did not pass citation compatibility for the claims. |
| `kackbro.../3mlwdvdll7k2i` | completed, 4 bullets, medium, 1 warning | no explanation, 0 bullets, low, 1 warning | Brave retrieved official and historical library context, but the evidence was not sufficient for the rhetorical/interpretive parts of the post. |
| `raywoodson5.../3mlw2uzungc2g` | completed, 3 bullets, medium, 2 warnings | no explanation, 0 bullets, low, 1 warning | Brave found topical material around January 6 compensation, but the final source set did not support a safe explanation. |

These failures matter because the product promise is not just low-noise retrieval. It is reliable generation of 3 to 5 cited bullets when sufficient context exists. Tavily met that goal for all 23 URLs in the control run; Brave did not.

### Brave Strengths

Brave had several useful strengths:

- It was faster end-to-end by almost 5 seconds on average.
- It reduced average source-fetch discards from 4.91 to 2.48.
- It returned strong official or primary sources in some cases, including the Robert Reich DOJ/DC Bar post.
- It improved or matched several successful outputs while reducing warnings.
- On completed runs, it cited more sources on average than Tavily.

The Robert Reich post is a good example. Brave found an official DOJ source and produced 5 high-confidence bullets with no warnings, while Tavily also produced 5 high-confidence bullets but retained one warning.

### Brave Weaknesses

The main weakness is coverage reliability:

- It returned fewer search results on average.
- It produced 3 low-confidence no-explanation outcomes.
- It reduced bullet count on 8 URLs.
- Some exact-phrase queries returned zero results even when useful context existed through broader queries.

This suggests that Brave is not a drop-in standalone replacement for Tavily in this pipeline. It can produce excellent individual source sets, but its isolated recall is not stable enough across the full mixed URL set.

### Recommendation From Experiment 3

Keep Tavily as the preferred standalone search provider for the current candidate stack.

Brave should remain in the P2 architecture as an input to Composite search, not as the standalone default. The reason is practical:

- Tavily is more reliable across the full dataset.
- Brave is faster and sometimes finds useful complementary sources.
- Composite can benefit from Brave's lower-noise or primary-source hits while letting Tavily cover cases where Brave misses enough compatible evidence.

The next search-provider experiment should run the same selected model stack with:

```text
SEARCH_PROVIDER=composite
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-5.1
```

That will test whether Brave's useful hits improve the Tavily baseline after deduplication, ranking, and citation compatibility checks.

## Consolidated Conclusion

The current evidence supports the OpenAI 5.1 generation stack as the strongest model candidate tested so far, but it does not support moving the embedding layer from `text-embedding-3-small` to `text-embedding-3-large` as the default.

The first experiment showed a large reliability improvement over prior operational behavior: completion increased from 18 to 23 out of 23 URLs and no-explanation outcomes dropped from 5 to 0.

The second experiment showed that larger embeddings did not materially improve the product outcome once the 5.1 stack was already in place. The large embedding run retained more ranked sources, but final cited sources, bullet count, warning rate, and runtime did not improve.

The third experiment showed that Brave is useful but not reliable enough as the standalone default search provider. Brave was faster and cited more sources when completed, but it produced 3 no-explanation outcomes where Tavily completed all 23 URLs.

The recommended candidate after the two completed experiments is:

```text
Generation: gpt-5.1
Judge: gpt-5-mini
Embedding: text-embedding-3-small
Vision: gpt-5.1
Search provider: Tavily as the standalone default; Composite remains the next search-provider candidate
```

The next experiments should evaluate the cheaper `gpt-5-mini` generation stack and the Composite search strategy with the selected 5.1 stack. The Composite run is especially important because Brave showed useful complementary strengths even though it underperformed Tavily as an isolated provider.

## Addendum: Composite Search and Mini Generation Rounds

### Purpose

Two additional runs were executed after the Tavily, embedding-size, and Brave-only experiments.

The first new run tested whether Composite search improves the evidence set when both Tavily and Brave are available:

```text
SEARCH_PROVIDER=composite
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_VISION_MODEL=gpt-5.1
COMPARISON_GROUP_ID=composite_5_1_large_embedding_eval
COMPARISON_CONFIG_ID=newer_full_large_embedding
```

The second new run tested the lower-cost generation option requested for comparison:

```text
SEARCH_PROVIDER=composite
OPENAI_GENERATION_MODEL=gpt-5-mini
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_VISION_MODEL=gpt-5.1
COMPARISON_GROUP_ID=composite_5_mini_large_embedding_eval
COMPARISON_CONFIG_ID=newer_mini_large_embedding
```

Both runs used the same 23 URL set.

### Overall Comparative Matrix

| Stack | Completed | No explanation | Failed config | Success rate | Avg bullets | Avg cited | Avg warnings | Avg time | Search | Fetch | Generation | Search results | Provider overlap | Multi-provider cited |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tavily + `gpt-5.1` + small embedding | 23/23 | 0 | 0 | 100.0% | 4.48 | 4.83 | 0.61 | 30.8s | 6.9s | 10.2s | 7.1s | 20.8 | 0.0 | 0.0 |
| Tavily + `gpt-5.1` + large embedding | 23/23 | 0 | 0 | 100.0% | 4.30 | 4.78 | 0.65 | 31.8s | 6.7s | 10.5s | 8.1s | 20.7 | 0.0 | 0.0 |
| Brave + `gpt-5.1` + small embedding | 20/23 | 3 | 0 | 87.0% | 4.50 | 5.60 | 0.45 | 25.5s | 4.5s | 8.2s | 7.2s | 17.1 | 0.0 | 0.0 |
| Composite + `gpt-5.1` + large embedding | 21/23 | 2 | 0 | 91.3% | 4.52 | 5.67 | 0.48 | 30.5s | 7.4s | 9.6s | 8.0s | 39.1 | 3.6 | 1.0 |
| Composite + `gpt-5-mini` + large embedding | 1/23 | 0 | 22 | 4.3% | 3.00 | 3.00 | 0.00 | 41.6s | 4.1s | 6.7s | 21.2s | 25.0 | 2.0 | 0.0 |

Notes:

- The `gpt-5-mini` row should be interpreted as a failed compatibility experiment, not as a quality result. Only one URL reached a completed explanation.
- Exact dollar cost was not computed because the run artifacts do not yet store token counts or provider billing units. The cost discussion below uses operational proxies: model tier, embedding tier, number of search providers called, number of retrieved pages, and elapsed time.
- Composite search roughly doubled candidate retrieval volume, increasing average search results from about 20.8 in Tavily-only to 39.1 in Composite.

### Experiment 4: Composite Search With `gpt-5.1`

Composite search produced higher evidence density on completed runs, but did not beat the Tavily-only default on reliability.

| Metric | Tavily + `gpt-5.1` + small | Composite + `gpt-5.1` + large | Interpretation |
| --- | ---: | ---: | --- |
| Completed explanations | 23/23 | 21/23 | Composite regressed on reliability. |
| No-explanation outcomes | 0 | 2 | Two posts were filtered to zero bullets. |
| Avg bullets per completed run | 4.48 | 4.52 | Slightly higher when Composite succeeds. |
| Avg cited sources per completed run | 4.83 | 5.67 | Stronger evidence breadth. |
| Avg warnings per completed run | 0.61 | 0.48 | Slightly cleaner completed outputs. |
| Avg total time | 30.8s | 30.5s | Similar latency despite more retrieval. |
| Avg search results | 20.8 | 39.1 | Much broader retrieval surface. |
| Avg provider overlap | 0.0 | 3.6 | Composite found sources surfaced by both providers. |
| Avg multi-provider cited sources | 0.0 | 1.0 | Some final citations were independently found by both providers. |

The strongest benefit of Composite is not average bullet count. The benefit is source confidence: it can identify sources discovered by both providers and it often gives the generator a richer evidence set. On completed runs, Composite cited 5.67 sources on average compared with 4.83 for Tavily-only.

However, Composite also produced two no-explanation outcomes:

| URL | Outcome | Interpretation |
| --- | --- | --- |
| `lc1summit.../3mlvoqr367k25` | no explanation, low confidence, 1 warning | The validator removed bullets because author interpretation was not sufficiently tied back to the original post. Tavily and Brave standalone both generated usable explanations, so this is a Composite/pipeline regression. |
| `raywoodson5.../3mlw2uzungc2g` | no explanation, low confidence, 1 warning | The claim involved a screenshot about a Jan. 6 compensation fund. Composite remained conservative because selected evidence did not safely support the policy claim or author interpretation. Tavily produced a medium-confidence explanation with warnings. |

Composite is therefore useful as an analysis-mode or advanced retrieval option, but it should not replace Tavily as the default until the validator/prompt behavior is tuned to avoid over-filtering interpretive posts where the original post itself can safely support author-reaction bullets.

### Experiment 5: Composite Search With `gpt-5-mini`

The `gpt-5-mini` generation configuration is not production-ready in the current pipeline.

| Failure type | Count |
| --- | ---: |
| OpenAI returned an empty response | 19 |
| OpenAI returned invalid query decomposition output | 3 |
| Completed explanations | 1 |

This failure pattern happened before search quality could be meaningfully evaluated. Most failures occurred in structured-output steps, especially query decomposition and explanation generation. The model either returned no usable content or produced truncated/invalid JSON for the expected schema.

The one completed result was the NBC hantavirus post:

| URL | Result |
| --- | --- |
| `nbcnews.com.../3mlveype5b22m` | completed, high confidence, 3 bullets, 3 cited sources, 0 warnings, 41.6s |

The lower model price is not useful if the configuration only completes 4.3% of the URL set. In effective cost terms, this is the worst tested option: nearly all calls still consume time and provider work, but almost none produce a valid explanation.

Before retesting `gpt-5-mini` as the generation model, the backend should add model-specific hardening:

- Higher output budget for structured JSON tasks.
- Explicit structured-output retry when JSON is empty or truncated.
- Shorter prompt payloads for query decomposition.
- Separate mini-specific prompts for query planning and explanation generation.
- Token and cost telemetry so the lower unit price can be evaluated against valid outputs, not just attempted calls.

### Complex Post Quality Review

The table below manually reviews six high-complexity posts across the latest controlled runs, focusing on whether the generated bullets did the intended job: explain the context, distinguish facts from author interpretation, and avoid unsupported claims.

| Post | Best observed behavior | Composite `gpt-5.1` behavior | Quality assessment |
| --- | --- | --- | --- |
| Robert Reich / DOJ and D.C. Bar | Tavily and Composite both produced 5 high-confidence bullets. Brave also produced strong output with an official DOJ source. | 5 bullets, high confidence, 8 cited sources, 1 warning. | Strong. Composite explained the lawsuit, Clark discipline context, DOJ argument, Reich's interpretation, and D.C. Bar role. The warning is appropriate because one official-position claim relied on news reporting rather than only a primary document. |
| Solar parking lots / France law image | Composite was best: it moved from Tavily's 3 medium-confidence bullets to 5 high-confidence bullets. | 5 bullets, high confidence, 4 cited sources, 0 warnings. | Strong improvement. Composite used the image, original post, thread context, and a web source to separate the meme's simplified claim from the actual French area-threshold/coverage rules. This is the clearest Composite win. |
| Nathaniel Menday / Reform UK image | Tavily, Brave, and Composite all produced usable explanations. | 4 bullets, high confidence, 3 cited sources, 0 warnings. | Good, with a caveat. Composite correctly treated the screenshot and thread as the evidence for what the post says and what the author believes. It avoided turning the author's broad claims about Reform, Sweden, or Zionism into externally confirmed facts. |
| Trump/Xi image quote | Tavily and Brave generated usable explanations; Brave produced 5 high-confidence bullets. | No explanation, low confidence, 1 warning. | Regression. Composite over-filtered the result after citation compatibility checks. The safer desired behavior is a medium-confidence explanation grounded in the image text, original post, and news coverage of the interview, as Tavily produced. |
| Jan. 6 compensation claim screenshot | Tavily produced 3 medium-confidence bullets with explicit warnings; Brave and Composite returned no explanation. | No explanation, low confidence, 1 warning. | Mixed. Returning zero bullets is defensible if the policy claim cannot be confirmed, but it is less useful than Tavily's approach: explain that the post expresses outrage, describe the screenshoted allegation as unverified, and warn that the available sources do not confirm the $1.7B claim. |
| Hawaii / Citizens United / SB 2471 | All successful providers produced strong 5-bullet explanations. | 5 bullets, high confidence, 6 cited sources, 0 warnings. | Strong. Composite captured enactment, corporate/artificial-person mechanism, Citizens United context, legal model, and the advocacy framing. This is a good example of Composite's broad evidence set improving confidence without adding warnings. |

### Cost and Benefit Conclusion

| Option | Benefit | Cost / Risk | Recommendation |
| --- | --- | --- | --- |
| Tavily + `gpt-5.1` + `text-embedding-3-small` | Best reliability: 23/23 completed, no no-explanation outcomes, strong average bullet count. | Moderate model cost; Tavily-only recall can miss complementary official or low-noise Brave hits. | Keep as the default production candidate. |
| Tavily + `gpt-5.1` + `text-embedding-3-large` | Slightly broader ranked source pool. | Higher embedding cost, slightly worse average bullets/citations/warnings, slightly slower. | Do not adopt as default. |
| Brave + `gpt-5.1` + `text-embedding-3-small` | Faster and cites more sources when it completes. | 3 no-explanation outcomes; weaker coverage reliability. | Keep as secondary provider, not standalone default. |
| Composite + `gpt-5.1` + `text-embedding-3-large` | Highest cited-source density on completed runs; useful overlap signal across providers; strong on solar and Hawaii cases. | Uses two search providers, nearly doubles result volume, still produced 2 no-explanation regressions. | Use as an advanced/P2 analysis option; do not replace Tavily default yet. |
| Composite + `gpt-5-mini` + `text-embedding-3-large` | Intended lower generation cost. | 22/23 failed due empty output or invalid JSON; effective cost per valid result is poor. | Reject for now; retest only after mini-specific structured-output hardening. |

The best current default remains:

```text
SEARCH_PROVIDER=tavily
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-5.1
```

The best current P2 experimental mode is:

```text
SEARCH_PROVIDER=composite
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_JUDGE_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_VISION_MODEL=gpt-5.1
```

That Composite mode is valuable for deeper analysis, especially when the extra source breadth can be exposed in the Analysis page. It should not be the default explanation path until the two no-explanation regressions are addressed.

The `gpt-5-mini` generation stack should not be used in the application at this point. It may become viable later, but only with prompt compression, output-budget changes, retry logic, and token/cost observability.

### Updated Final Recommendation

For the final POC, use Tavily + `gpt-5.1` + `text-embedding-3-small` as the reliable default path and keep Composite + `gpt-5.1` + `text-embedding-3-large` as an explicit comparison/analysis path.

This gives the project a pragmatic split:

- Default user-facing explanation path: maximize successful cited explanations.
- Analysis page: show whether Composite retrieval adds better evidence, overlap, and source diversity.
- Future optimization path: revisit cheaper generation only after structured-output reliability is fixed and token-level cost telemetry is available.
