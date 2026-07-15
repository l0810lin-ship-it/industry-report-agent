# Output Format Contract

## Selection

Before configuration or estimation, ask the user to select one or more formats: Markdown (`md`), Word (`docx`) or PowerPoint (`pptx`). Do not ask again if the user already specified them. If the user explicitly delegates the choice, select the format and disclose the choice. Silence is not delegation: never apply a default format merely because the user has not answered.

Record the selection in `config.json` under `output.formats` and record its provenance under `intake.format_selection`. The formats share one approved evidence base and one analytical source of truth; they are not separately researched reports. Estimation, plan validation and collection must remain blocked while the selection is pending.

## Markdown

- Produce the canonical full report or decision brief.
- Use `report_YYYYMMDD_HHMM.md` or `decision_brief_YYYYMMDD_HHMM.md`.
- Keep evidence IDs and direct URLs visible.

## Word

- Use the `documents:documents` skill.
- Derive the document from the approved analytical source, using the `standard_business_brief` preset by default; use `decision_memo` when the user explicitly wants a shorter memo.
- Produce an editable `.docx`, render it, inspect every page, and fix clipping, bad page breaks, unreadable tables and orphaned headings before completion.
- Do not treat a file-extension rename or a blind converter output as a finished Word deliverable.

## PowerPoint

- Use `knowledge-cat-ppt-skill` together with `presentations:Presentations`.
- Default visual system: Knowledge Cat `kc-25 Minimal Data Story` — editorial minimalism, Swiss grid, restrained palette, one insight per slide and editable native charts. If that style is unavailable, use `kc-01 Minimal Business`. A user-provided brand or template overrides these defaults.
- Use action titles and management logic; do not paste report paragraphs onto slides.
- Recommended length: Flash 5–7 slides, Standard 10–14 slides, Deep 14–20 slides plus a source appendix when needed.
- Keep charts, tables and text editable. Cite sources on the relevant slide.
- Render and inspect every slide, run content and editability QA, and fix overflow, overlap, weak hierarchy and unsupported decorative visuals.

The selected GitHub design dependency is `gnipbao/knowledge-cat-ppt-skill`, MIT licensed: https://github.com/gnipbao/knowledge-cat-ppt-skill

## Multiple formats

Generate all selected formats from the same approved content and use one timestamp stem where practical. Report the absolute path for every requested artifact. A failure in one renderer must not be hidden; report the successful artifacts and the exact blocked format.

## No-export tasks

When the user asks only to configure or improve the Agent, update the Agent contracts and stop. Do not generate sample reports, Word files or slide decks unless the user separately asks to run a topic.
