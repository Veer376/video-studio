# Proposed Enhancements for omni-flash-prompt-writer

## Unmanned Vehicle / Ride-On Prop Ghost Occupancy (Mitigation for FM #19 & FM #17)

### Problem
When a scene features both active humanoid characters and an unoccupied vehicle (e.g. tractor, cart, boat, bicycle) with visible seating or controls (steering wheel, saddle, handlebars), the model's cross-attention frequently binds a character's reference embedding to the empty seat, generating a duplicate clone driving or riding the vehicle while the true character is elsewhere in the shot.

### Proposed SKILL.md Addition (under Production Guardrails)
```markdown
### Unmanned Vehicle & Apparatus Occupancy

When an unoccupied vehicle, machine, or seat is present in a scene with human/character references:
1. Explicitly declare global singular human counts (e.g., `Exactly two human characters in the entire scene: exactly one @chhotu and exactly one @motu`).
2. Explicitly state in the vehicle description and each timed bracket that the driver's seat, steering wheel, and cabin are completely empty, vacant, and unmanned (e.g., `The driver seat and steering wheel of @tractor are completely empty and unoccupied; no person or child is on the vehicle`).
```

## Kinematic Choreography Budget & Pre-Staging (Mitigation for Complex Contact Motion)

### Problem
When a 10-second continuous shot attempts to combine multi-phase locomotion (e.g., ground running or climbing across multiple vehicle surfaces) with a high-precision contact leap and mid-air docking/mounting, the model suffers kinematic collapse, character splitting (cloning mid-leap), and landing failure (falling back to ground/hood).

### Proposed SKILL.md Addition (under Production Guardrails)
```markdown
### Kinematic Pre-Staging for High-Action Contact

For complex contact transitions (mounting a moving mount, catching a flying vehicle, boarding a craft):
1. **Pre-stage the actor**: Start the clip with the character already positioned at the optimal launch point (e.g. standing balanced on top of the vehicle hood at 00:00) rather than requiring a multi-step climbing sequence prior to the leap.
2. **Allocate a 4-second contact window**: Give the leap and physical docking a dedicated 3–4 second window (e.g., [3-7s]) with explicit body contact and locking cues (e.g., arms wrapping around the front rider's waist) to ensure physical attachment resolves before vehicle acceleration.
```

