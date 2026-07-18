# Chapter 4 — Build a step with no code (Designer) (2–3 min)

*Hardest to film. Record last, edit hard. Pre-build the canvas so the
camera only sees a clean assembly. NEVER film the SQL box or the
untick-duplicate-keys step.*

**Scene 1 — cold open — 10s.**
[SCREEN] a desktop ETL canvas (or a still). "This lives on one laptop."

**Scene 2 — build it, montage — 40s. [★]**
[SCREEN] Lakeflow Designer canvas.
[DO] drop the three sources; use the Genie-Code one-liner to build the
join + aggregate; name the boxes as they land.
[CUT] fast montage of the boxes assembling. Show the **no-code path only** —
hide the SQL operator and the duplicate-key fiddle entirely.

**Scene 3 — result + proof — 20s.**
[SCREEN] the output table; then `02_parity` all ✓ — "same numbers as the
coded pipeline."

**Scene 4 — it's real code, governed — 15s.**
[DO] right-click canvas → Open code pane (real code); then Catalog Explorer
→ Lineage.

**Scene 5 — close — 5s.**
[CUT] app tile.

**Bad / hide:** the 7-step manual build, the SQL box, the untick step — off
camera or heavily edited. **If time is tight, drop this as a standalone and
fold Scenes 2–4 into Chapter 5 as a 20s "and steps can be built no-code too."**
