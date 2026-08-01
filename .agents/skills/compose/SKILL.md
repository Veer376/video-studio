---
name: compose
description: Script-generation skill. Writes the pure narration prose to script.md based on the brief and research findings. Integrates specific rules of professional Hindi narration, dynamic registers, and template-driven hook strategies.
---

# Compose Skill

This skill is a **screenwriter and storyteller**. Its only job is to translate raw research findings into an elegant, emotionally resonant narration script. It focuses entirely on creative flow, voice rhythm, and high-impact hooks.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "research_complete"`
- `research.md` is written and available
- `script.md` does not yet exist, or the user wants to rewrite/regenerate the script

---

## Narrative Writing Rules (The Hindi Voice Guide)

When writing narration in Hindi (`hi-IN`), you must write for the **ear**, not the eye. Avoid literal translations from English. Follow these rules to make the script sound natural, powerful, and native:

### 1. Register Calibration (Dynamic Vocabulary)
Do not use uniform vocabulary throughout. Shift the registers based on the scene's emotional tone:
- **Spiritual/Philosophical Beats:** Use heavy, Sanskrit-derived words (*Tatsama*) to create gravity and sacredness.
  * *Example:* "यह संघर्ष केवल बाहरी नहीं है... यह आपके **धर्म**, आपके **कर्तव्य** और आपके **अस्तित्व** की लड़ाई है।"
- **Human/Emotional Beats:** Use warm, conversational Urdu-Hindustani words to make the listener feel connected.
  * *Example:* "जब **जिंदगी** के इस रास्ते पर चलते हुए **दिल** बैठ जाता है, और सारे **ख्वाब** अधूरे लगते हैं..."
- **Direct Address Beats:** Use simple, everyday words. Avoid textbook Hindi.
  * *Example:* "सोचिए... क्या सचमुच आप हार रहे हैं, या सिर्फ डर रहे हैं?"

### 2. Sentence Rhythm (The Long-Short Rule)
Vary your sentence lengths intentionally. Build pressure with descriptive lists, then release it with short, punchy statements.
- *Poor:* कुरुक्षेत्र में दोनों तरफ सेनाएं खड़ी थीं और अर्जुन का धनुष गिर गया था और वह दुखी हो गए थे।
- *Excellent:* चारों तरफ सेनाएं खड़ी थीं। शंखों की गूंज थी। हवा में धूल उड़ रही थी। और उस शोर के बीच... सबसे बड़ा धनुर्धर खड़ा था। निहत्था। कांपता हुआ।

### 3. The Fourth-Wall Turn (Direct Address)
Great storytelling transitions from telling a story to directly addressing the listener at key turning points. Move from the third person (*वे/उन्होंने*) to the second person (*आप/तुम*):
- *Example:* "अर्जुन रथ पर गिर पड़े। लेकिन सोचिए... क्या आपकी कहानी में भी ऐसा ही मोड़ नहीं आता? जब आपके सामने आपका कुरुक्षेत्र खड़ा होता है?"

### 4. Shloka & Quote Embedding
Never drop a quote or a Sanskrit shloka without preparation. Use a three-step pattern:
1. **The Warm-Up:** Set the stage, building curiosity.
2. **The Delivery:** Write the quote or shloka on its own line.
3. **The Unpack:** Translate it immediately in warm, simple Hindustani.
- *Example:*
  "तभी भगवान कृष्ण ने अर्जुन के कानों में वह अमर सत्य फूंका, जिसने इतिहास बदल दिया..."
  > "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन..."
  "यानी, पार्थ... तुम्हारा अधिकार सिर्फ अपने काम पर है, उस काम से क्या मिलेगा, उस पर कभी नहीं।"

---

## The 80/20 Truth/Fiction Blend

- **80% Verified Truth:** Ground the core message in historical, scriptural, and real-world facts provided in `research.md`.
- **20% Plausible Fiction:** Use your imagination to describe the sensory environment or inner emotions. Describe what the air felt like, the sweat on the palms, the heavy silence between words. This adds cinematic texture.

---

## Two-Round Process

### Round 1: Blueprint Presentation

Before writing the script, present **3 Titles, 1 Description, and 3 distinct Template Blueprints** to the user for feedback.

#### 1. Title Strategies:
Generate 3 distinct titles matching these hook strategies:
1. **Curiosity Gap:** Intrigues the user to know something hidden.
2. **Emotional Conflict:** Focuses on the core human struggle.
3. **Direct Challenge:** Speaks directly to the viewer's current situation.

#### 2. YouTube/Reels Description:
Write a 2-paragraph description:
- *Paragraph 1 (The Hook):* Creates tension and asks a compelling question.
- *Paragraph 2 (The Promise):* Tells the viewer what life-changing wisdom this video reveals.

#### 3. Template Blueprints:
Generate 3 distinct templates using the following structure:
```
TEMPLATE <N> — <Name>
Opening hook:   <The first 8 seconds of audio — one sentence>
Middle arc:     <How the story builds and connects to modern life — two sentences>
Turn:           <The emotional pivot or revelation — one sentence>
Closing:        <The final call to action or resolution — one sentence>
Tone signature: <e.g., Rising inspiration, quiet contemplation, dramatic epic>
```

**Wait for the user's explicit selection before proceeding to Round 2.**

---

### Round 2: Script Writing

Once the user approves a title and template, write the full script to:
```
library/<project_slug>/script.md
```

### Script Format:
Write the script as **one continuous, flowing narrative in pure prose**.
- **No** scene numbers.
- **No** image prompts.
- **No** voice directions.
- Keep it clean, structured only by paragraph breaks. This ensures the story flows naturally for audio synthesis.

```markdown
# Script: <Approved Title>
Template Used: <Approved Template Name>
Generated: <Date>
Description: <Approved Description>

---

[Write the full narration script here in pure, flowing Hindi paragraphs]
```

---

## Hard Rules

- **Wait for Blueprint Approval:** Never write the full script before the user picks a title and blueprint.
- **Pure Prose in script.md:** Do not include scene splits, image prompts, or metadata brackets in `script.md`. It must contain only read-aloud text.
- **Update status:** Once the script is written, update `session.json` status to `"compose_complete"`.
