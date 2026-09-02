# Validation guide

Run both checks from the skill directory or call them with absolute paths:

```text
python scripts/build_handbook.py path/to/handbook
python scripts/verify_handbook.py path/to/handbook
```

The builder is strict by default. It exits non-zero when a configured page is
missing, a slug is unsafe, a required field is absent, or a fragment contains
an executable script. Use `--draft` only for an explicitly labelled preview;
draft output is not a completed deliverable.

The verifier checks the generated `site/` as well as source fragments:

- every configured page exists and every internal link resolves;
- generated metadata is escaped and pages contain no scaffold placeholders;
- headings have unique IDs and page slugs are unique;
- local CSS/JS assets exist and no remote script/style is required;
- optional evidence facts occur in their claimed page.

Static checks do not prove browser behavior. Open `site/index.html` and test
search, keyboard navigation, theme switching, mobile navigation, code-copy,
and diagrams. If Mermaid is used, use the pinned local asset and record the
browser used for the smoke test.
