# Authoring guide

Write content as HTML fragments. The builder supplies the document shell,
navigation, metadata, and search index.

## Page contract

Each page should answer one reader question and stand alone. The default
handbook answers one pinned question; extra pages wait until asked. Use this
order when it fits:

1. What the component is responsible for.
2. How data or control enters and leaves it.
3. The important decisions, states, and failure modes.
4. A concrete command, example, or next page.

Use `h2` for sections and `h3` for subsections. The builder creates stable
heading IDs from the heading text; supply an explicit `id` only when a link
must survive a wording change.

## Safe fragment patterns

```html
<p>事实陈述，保留源代码中的名称、端口和字段。</p>
<div class="callout note"><strong>证据</strong><p>src/app.py</p></div>
<pre><code>python -m app --check</code></pre>
```

Use `<a href="../pages/architecture.html">` for internal navigation from a
page under `site/pages/`; the verifier resolves links relative to their page.
External links are allowed in prose but must use `https://` and should be
limited to authoritative sources.

## Tone and truth

Describe the current system, not an unimplemented plan. Separate verified
facts from inferences. When a document and the runtime disagree, state both
versions and link the drift page. Do not “polish” exact identifiers, commands,
numbers, or configuration values.
