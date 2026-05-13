# ADR-002: Environmental impact estimation methodology

**Status:** Accepted

## Context

Users want to see energy, water, and carbon estimates alongside token usage. Anthropic does
not publish per-token energy or emissions metrics. Estimates must be derived from third-party
research and clearly labelled as approximations.

Three quantities are estimated: energy (kWh), water (litres), and carbon (kg CO2).

## Decision

### Energy per token (Joules)

Source: **TokenPowerBench** (arxiv 2512.03024) and **Luccioni et al. 2023** ("Power Hungry
Processing"). Modern H100-class hardware, batch inference.

| Token type | Joules | Rationale |
|---|---|---|
| Output (decode) | 0.39 | One full forward pass per token — autoregressive |
| Input (prefill) | 0.13 | Single forward pass over all tokens at once |
| Cache write | 0.13 | Same compute as prefill; KV values computed and stored |
| Cache read | 0.02 | KV retrieval from memory — negligible compute |

Output tokens dominate because each requires an independent forward pass.

### Water per kWh

Source: **Li et al. 2023** ("Making AI Less Thirsty", arxiv 2304.03271).

**1.8 L/kWh** — industry-average data-center WUE. AWS's own figure (0.15 L/kWh) is an
outlier achieved through aggressive water recycling at specific facilities; using the
industry average is more conservative and appropriate given uncertainty about Anthropic's
exact infrastructure mix.

### Carbon per kWh

Source: **US EPA / Ember, 2024 grid data**.

**0.384 kg CO2/kWh** — US grid average. Anthropic primarily operates in US data centers.
AWS has renewable energy commitments that would lower this; the US average is the
conservative, publicly verifiable choice.

### Real-world analogs

To make the energy figure legible:

| Analog | Constant | Source |
|---|---|---|
| LED house lighting | 72W (8 × 9W bulbs, 800 sq ft / 2 rooms) | Standard residential lighting design |
| Household water pumping | 0.15 kWh/day (300 L/day at 0.5 kWh/m³) | US EPA municipal pumping efficiency |
| Cooking a meal | 0.5 kWh (30 min, 1 kW electric burner) | Standard electric hob rating |
| Driving | 0.21 kg CO2/km | EU average petrol car |

## Consequences

- All estimates are approximations. Actual values vary significantly by hardware generation,
  batch size, data-center location, and grid mix.
- The output clearly labels the section "estimated" and the `--help` text links to this ADR.
- Constants are grouped at the top of `claudia` and annotated with sources for easy updating.
- When Anthropic publishes official per-token figures, replace the TokenPowerBench values.
