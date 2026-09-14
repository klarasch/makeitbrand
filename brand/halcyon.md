# Halcyon — voice and adaptation

Halcyon is a fictional security research company used to demonstrate makeitbrand's dark, art-directed
style.

## Voice

- Headlines state a finding in Title Case, ≤ 16 words: "Attackers Target Vendor Ecosystems, Not Single Bugs".
- Numbers carry their approximation and unit: "~143 days", "7,800+ environments".
- Leads come in pairs of short contrasting sentences, set side by side in a `.row[data-divide]`.
- Never an exclamation mark. Banned: game-changing, revolutionary, cutting-edge, leverage.
- Section eyebrows are nouns with a definite article: "The asymmetry gap", "The overlap paradox".
- Quotes are attributed as `<strong>Name</strong>, Role, Company`.

## Adaptation

- `infographic` and `social-*` boards use `data-ground="art"`; cards on it are `data-tone="glass"`.
- The accent (lime) is for figures, eyebrows and the one highlighted mark per chart; never for body text.
- Charts on art grounds: the threat or problem row takes `--chart-1` (pink), the reference row recedes.
- A co-brand always uses `.lockup`; partner marks must be supplied white.
- `footer.band` carries the partnership line or the source, never a call to action.

Icons (`.icon[data-icon]`): alert-triangle, arrow-right, arrow-up-right, award, bar-chart, box,
calendar, check, clock, cloud, code, database, eye, file-text, flag, globe, heart, key, layers,
lightbulb, link, lock, mail, map-pin, message-circle, pie-chart, plus, refresh, rocket, search,
shield, sliders, sparkles, star, target, trending-down, trending-up, user, users, x, zap.

## Illustration

Line first: shapes are `currentColor` outlines (`stroke`, `fill="none"`), never flat colour fields.
Exactly one mark per illustration is filled or stroked in `--illo-1` (lime) to carry the emphasis —
the node that matters, the tallest step, the check inside the shield — the same "one accent" rule
as a chart's `data-highlight`. `--illo-2`/`--illo-3` (violet, blue) are for a second layer of
structure only (an inner outline, a faint connective line), never for emphasis, and are used
sparingly, if at all — most of Halcyon's illustrations use only `--illo-1` and `currentColor`.
Corners are soft (`stroke-linejoin="round"`), matching the brand's rounded cards. Low-emphasis lines
(connective lines, an inner echo of the main shape) carry `stroke-opacity`, never a separate muted
colour. At most 5–7 shapes; a Halcyon illustration reads at a glance, like its charts. Never: gradients,
photographic or textured fills, drop shadows, more than one filled shape, decorative clutter around
the subject.

Library (`figure.illo[data-illo]`): `network-nodes` (a hub with four connected satellites — vendor
and partner ecosystems), `growth-steps` (ascending steps with a trend line — improvement,
automation, progress), `shield-check` (a layered shield with a check mark — security posture,
protection). Reach for one of these before drawing an authored illustration.
