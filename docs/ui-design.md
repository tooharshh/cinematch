# CineMatch interface design

The interface uses a streaming-style discovery pattern: cinematic artwork, a clear primary action, horizontal poster shelves, focused movie pages, and searchable collections. The existing Streamlit/FastAPI/DuckDB architecture and TF-IDF/cosine ranking remain in place.

## Color and typography

- Near-black surfaces keep the interface quiet while real movie artwork supplies most of the color.
- A red primary action establishes emphasis; quieter secondary actions and navigation preserve hierarchy.
- Light text and a dark artwork scrim support legibility. Gold denotes catalog ratings, not a predicted preference score.
- **Funnel Display** is used for headings, movie titles and the wordmark. **DM Sans** handles descriptions, navigation and native controls.
- Font files are bundled in `frontend/assets/fonts/` with their SIL Open Font licences. They are embedded through `@font-face` data URLs, so font loading does not depend on Google Fonts at runtime. The installed Streamlit version restricts font MIME types in its static-file handler.

Font sources: [Funnel Display](https://github.com/google/fonts/tree/main/ofl/funneldisplay), [DM Sans](https://github.com/google/fonts/tree/main/ofl/dmsans).

## Discovery flow

The homepage presents six catalog shelves. Poster links open a real movie page and its five recommendations; each recommendation can start another discovery. Indian-cinema and genre collections have real filters, pagination and browser Back behavior. Search accepts a title and displays poster results, with the query retained in the URL.

The featured artwork uses a real TMDB backdrop. `python -m etl.enrich_backdrops` optionally adds backdrop metadata for up to ten selected movie IDs to an existing catalog, with the backend stopped. Fresh catalog preparation preserves available backdrop paths automatically. Ordinary movie pages fall back to posters when a backdrop is absent.

The app discovers films rather than streaming video. Home shelves reflect catalog popularity, language, genre or ratings; they are not represented as learned viewing-history personalization. Highly rated collections require at least 500 votes.

## Attention-priority sketch

[View the attention map](ui-attention-map.png).

**This is a design hypothesis, not an eye-tracking or click heatmap.** The image overlays Gaussian regions on a real screenshot using manually assigned priorities: primary action 1.0; feature title 0.8; search 0.75; artwork 0.65; first poster row 0.6. These numbers are neither gaze probabilities nor measured engagement scores. No behavioral tracking was added.

The goal is to make the next action discoverable and the artwork informative. A higher score in this sketch does not establish that users will notice or use an element.

Reproduce with a screenshot and the corresponding DOM rectangles:

```bash
MPLCONFIGDIR=/tmp/cinematch-matplotlib .venv/bin/python scripts/render_attention_map.py \
  --screenshot /tmp/cinematch-streaming-home.png \
  --regions docs/ui-attention-regions.json --output docs/ui-attention-map.png
```

To evaluate engagement, compare the previous and new interfaces with real participants completing the same tasks: find a named film, discover an Indian film, inspect five recommendations, and return to browsing. Record completion, time to a useful recommendation, navigation errors and participant comments. Report the sample and uncertainty; no engagement uplift has yet been measured.

## Verification and references

The automated suite has 62 passing tests. Browser checks cover native keyboard actions, poster discovery chains, search URLs, empty results, malformed links, Indian-language filtering, pagination, browser Back, multiple viewport sizes, 200% text and reduced motion. Both font faces were verified loaded. This is scoped verification, not a WCAG conformance certification.

The emphasis on informative artwork is informed by [Netflix's artwork research](https://netflixtechblog.com/artwork-personalization-c589f074ad76). The distinction between a sketch and measured attention follows [NN/G's visual-design testing guidance](https://www.nngroup.com/articles/testing-visual-design/) and [eyetracking study guidance](https://www.nngroup.com/articles/eyetracking-setup/).
