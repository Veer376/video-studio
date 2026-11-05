# Character Reference Standard & Visual Guidelines

This directory contains the canonical visual reference assets for the **Kahani Ka Chakkar** universe. Every recurring character asset must strictly adhere to the standards defined below.

---

## 1. The Core Visual Aesthetic: "The Sweet Spot"

All characters follow the **Stylized 3D Vinyl / Modern Toy / Smooth Cartoon** aesthetic (exemplified by `@chhotu` and `@aloo`).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    THE "SWEET SPOT" VISUAL STANDARD                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Clean, smooth geometric volumes (friendly, rounded, tactile clay/vinyl)   │
│ • Soft, warm studio three-point lighting with subtle golden rim highlights  │
│ • Bold, vibrant, saturated child-friendly color palettes                    │
│ • Large, highly expressive cartoon eyes with dual specular catchlights      │
│ • Distinct, instantly readable silhouettes (passes the 50px thumbnail test)│
├─────────────────────────────────────────────────────────────────────────────┤
│ ❌ PROHIBITIONS:                                                            │
│ • No photorealistic human skin pores, wrinkles, or hyper-realistic textures │
│ • No individual realistic hair strand fuzz or chaotic grooming              │
│ • No gritty live-action noise, harsh shadows, or flat 2D Flash artwork      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Sweet Spot is Mandatory:
1. **Zero AI Video Drift:** Clean, smooth shapes give Gemini Omni Flash clear geometric boundaries. The model animates motion and character interactions without texture flickering, face-morphing, or limb deformation.
2. **Unified World Harmony:** Ensures human characters (like `@motu`) and anthropomorphic produce characters (like `@chhotu` and `@aloo`) look like they belong to the exact same high-quality toy/animation universe.
3. **High Production Velocity:** Streamlines prompt generation and eliminates costly regeneration retries.

---

## 2. Character Reference Sheet Contract (Model: `@aloo` / `@chhotu`)

Every canonical character reference image must be generated as a **4-Panel Multi-Angle Turnaround Sheet** matching `aloo.jpeg` and `chhotu.jpeg`.

### Layout & Composition Requirements:
* **Aspect Ratio:** 16:9 Landscape (e.g. 1360×768, 1280×720, or 1024×576).
* **The 4 Canonical Views (Left to Right):**
  1. **Full-Body Front View:** Standing neutral/heroic pose, entire body head-to-toe visible.
  2. **Full-Body Side Profile View:** 90° side profile showing depth, posture, and back accessories.
  3. **Full-Body Back View:** 180° rear view showing spine, garments, and rear tool attachments.
  4. **Close-Up Portrait View:** High-detail front/three-quarter facial expression showing eye catchlights, smile, and head accessories.
* **Background:** Clean, neutral, seamless warm-grey or off-white studio backdrop. Zero scenic elements or clutter.
* **Lighting:** Soft, even, studio reference lighting with balanced fill and subtle rim highlights.

---

## 3. Character Anatomy & Consistency Rules

1. **Produce / Vegetable Characters (`@chhotu`, `@aloo`, `@gajar`):**
   - Natural human child/adult body proportions with normal arms, hands, legs, and feet.
   - ONLY the head and face carry the distinct vegetable identity (potato, sweet potato, carrot, tomato).
   - Naturally formed cartoon facial features on the vegetable surface.
2. **Human Characters (`@motu`):**
   - Lovable, chubby 10-year-old kid proportions (3.0 heads tall, round rosy cheeks, stylized hair chunk).
   - Stylized smooth skin finish matching the same tactile vinyl/toy shading as the vegetable cast.
3. **Creature Companions (`@dragon` - Angaar):**
   - Chibi 2.0 heads tall, smooth pear-shaped body, oversized glossy eyes, floppy ear-frills.
4. **Signature Garments & Fixed Props:**
   - Every character must have fixed, unchanging signature clothing with explicit resting anchors (e.g. brass goggles pushed up on forehead, cartoon wrench resting in bib pocket, red bandana around neck).

---

## 4. Registry Integration

Once a character sheet is created and validated:
1. Follow `.agents/skills/produce-story/references/character-readiness.md` to choose project-level or story-level ownership.
2. Register the approved canonical image and complete character entry in the owning registry.

---

## 5. Character Profiles

This file owns the visual reference-sheet standard. Character registry semantics are owned by `.agents/skills/produce-story/references/character-readiness.md` so visual guidance and model-facing profile guidance do not diverge.
