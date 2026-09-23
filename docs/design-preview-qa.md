# JLPT Listening Studio · Design QA

**Final result: passed**

## Reference direction

The supplied YupVox screenshot uses a bright, low-contrast canvas, white work surfaces, violet controls, compact status labels, and a multi-panel creative workspace. The preview carries over the light/violet palette and clear tool hierarchy while keeping the product focused on Japanese listening practice. It does not reuse YupVox branding, illustration, dubbing workflow, or exact panel arrangement.

## Visual review

Reviewed the rendered library screen at 1363 × 936 and compared its visual direction with the 1280 × 800 reference. The library has a persistent left navigation, a clear “continue learning” area, progress summary cards, and searchable lesson cards. Contrast, spacing, labels, and primary actions remain consistent across the preview. The study workspace separates the segment list, listening controls, and exercise area; the transcript editor, bilingual view, review queue, import flow, and settings use the same surface and accent system.

Responsive CSS includes breakpoints at 1180 px, 900 px, and 680 px, plus reduced-motion handling. Mobile viewport interaction was not part of this browser pass.

## Interaction review

Verified in the browser:

- Library navigation, lesson opening, segment selection, and the full-phrase / missing-word practice modes.
- Answer entry, grading feedback, reveal/retry controls, bilingual transcript, transcript editor, and progress view.
- Review list, sample lesson creation flow, and settings tabs.
- Clean sample data restored after testing.

The preview labels mock AI processing and grading clearly. It does not upload media or call an AI service.

## Build and checks

- `npm run build` — passed; Sites output files were generated.
- `npm run test:sites` — 4 tests passed.
- Browser console — no application errors observed; one unrelated browser-extension metadata error was present.
- Standalone HTML and embedded preview copies match.
