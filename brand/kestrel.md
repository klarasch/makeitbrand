# Kestrel — voice and adaptation

Kestrel is a fictional reporting tool used to demonstrate makeitbrand.

## Voice

- Headlines are claims, not labels. "Reports that write themselves", not "Automated reporting".
- Sentence case everywhere. ALL CAPS only via `.eyebrow`.
- Never an exclamation mark.
- Banned: leverage, unlock, seamless, robust, revolutionary, game-changer, excited to.
- Numbers keep their unit and baseline: "3.2 h → 40 min", not "80% faster". The → arrow is
  allowed between two numbers, nowhere else.
- Say "teams", never "users". The product is "Kestrel", never "the platform".
- One `<strong>` per board, on the words that carry the claim.

## Adaptation

- On `accent` grounds, `.logo` is `mono` (the runtime default); on `inverse`, also `mono`.
- `social-*`, `infographic` and `nametag` boards use `data-ground="art"`; cards on it are `data-tone="glass"`.
  Charts, dashboards and slide insets stay on plain grounds.
- On `social-*` media, the logo never goes `tl` (the platform avatar sits there). Default `br`.
- On `chat-header`, no logo: Confluence and Slack already show who posted it.
- On boards narrower than 1200 px (all `social-*` media, `nametag`), an eyebrow is ≤ 3 words.
- At most one `accent` card, tile or node per board. Never `accent` ground on `dashboard`.
- Kestrel slides are light (`--inset-ground: light`). A `slide-inset` board carries no heading.
- Charts never use `--accent-2`, and a `data-highlight` series is always the current period.
