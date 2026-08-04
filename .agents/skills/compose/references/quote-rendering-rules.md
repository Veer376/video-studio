---
name: quote-rendering-rules
type: reference
used_by: compose
description: Rules for embedding shlokas, quotes, and attributed wisdom in scripts.
---

# Quote Rendering Rules

## Scaling

| Duration | Max Quotes |
|---|---|
| < 2 min | 0–1 |
| 2–5 min | 1–2 |
| 5–10 min | 2–3 |
| > 10 min | 3–4 |

Never place a quote in the first 30 seconds unless it IS the hook.

## Three-Step Pattern

1. **Warm-Up** — Narrator builds curiosity (spoken aloud).
2. **Delivery** — Quote/shloka in `>` blockquote (NOT spoken — rendered visually).
3. **Unpack** — Narrator explains in warm Hindustani (spoken aloud).

## Example

तभी भगवान कृष्ण ने वह अमर सत्य फूंका जिसने इतिहास बदल दिया...
> कर्मण्येवाधिकारस्ते मा फलेषु कदाचन...
यानी, पार्थ... तुम्हारा अधिकार सिर्फ अपने काम पर है, उस काम से क्या मिलेगा, उस पर कभी नहीं।

## Production Behavior

- `>` blockquote lines are **excluded** from voice synthesis.
- Pipeline detects them and renders as bold styled text on a visual background.
- Warm-up and unpack lines surrounding them are narrated normally.
