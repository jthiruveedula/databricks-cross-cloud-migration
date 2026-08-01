Closes #<!-- issue number — required, see CONTRIBUTING.md#issue-tracking. Use "Relates to #N" instead of "Closes" if this only partially addresses it. -->

## Summary

<!-- What changed and why. -->

## Evidence

<!--
Reviews are based on evidence, not opinion. For a content change: link the official
docs page, changelog, or GA announcement backing the claim. For a bug fix: the error
message or repro steps. For a tool/dependency bump: what you checked to confirm it's
safe (changelog, build output, manual test).
-->

## Test plan

- [ ] `npm test` passes
- [ ] `npm run build` passes
- [ ] For a new/edited page: registered in `src/data/navigation.json`, follows the
      Validation/Rollback/Automation-opportunity shape, uses root-relative markdown
      links (not raw `<a href>`)
- [ ] For a UI/component change: checked in a real browser (dev server), including
      the browser console for hydration errors
