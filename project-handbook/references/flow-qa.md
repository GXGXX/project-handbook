# In-Page Follow-Ups

Use after building and reviewing a flow handbook. Start the connection yourself;
the reader should not need to run commands or paste credentials into a page.

## Launch

Run with the installed Python runtime, quoting paths as appropriate:

```text
python scripts/flow_server.py NEW_OUTPUT --source-root CLIENT --source-root SERVER --source-root DOCS --background
```

The command above assumes the installed `project-handbook` skill directory is
the working directory. In a user's project, resolve the script from the loaded
skill's absolute location and use absolute output/source paths; do not look for
`scripts/flow_server.py` inside the user's client repository.

Pass only existing directories supplied or authorized by the user. Omit missing
roots; do not add the home directory, drive root, credentials directory or an
unrelated project for convenience. The port defaults to an available loopback
port. The script prints the reading URL and writes safe startup information
(`url`, `pid`) to `NEW_OUTPUT/.flow-server.json` without a connection token.

Use `--background` so the helper survives the calling terminal and task cleanup.
The launcher waits for a matching process and live page before returning the URL.
On Windows it uses a hidden local WMI process: `Start-Process` and plain detached
children can still inherit an outer kill-on-close job. On other systems it starts
a separate process session. Logs stay inside the generated output directory.
Read the startup file, verify the page responds, and open its URL. Do not start a second helper for
the same output; reuse the running address. To stop, terminate only the helper
PID you verified belongs to this output, not every Python or Codex process.

The backend discovers `CODEX_BIN`, PATH or the Windows Codex bundled executable.
Optional `--codex-bin` points to an installed executable; `--model` explicitly
selects a model. Otherwise it uses the local Codex configuration. Authentication
remains server-side with Codex. Do not read or copy auth files into artifacts.
This is a dedicated ephemeral Codex context, not the active desktop task.

## Answer, Then Compile

- A node's **追问这个节点** button opens the Q&A panel with that node selected.
  The general Q&A button also accepts questions about the entire flow.
- Enter sends; Shift+Enter inserts a newline, and IME composition must not send.
  Clear the composer immediately and retain the question in its transcript entry.
  Failed or cancelled questions keep the reason and next step in the transcript
  card, not only in the status line; retry the same card instead of adding a
  duplicate. Preserve any new draft. Connection recovery checks state only,
  never blindly resends model requests.
  A renewed token must belong to the same book, using the same-origin session
  endpoint; Host/Origin and cross-site checks remain enforced.
  The panel resizes from its left edge/corner, or its top edge on narrow screens.
  Keep user questions distinct from AI answers and retain formatted Markdown in
  offline exports without executing answer HTML or loading external content.
- The model answers from authored details and recent completed answers first.
  Missing evidence can trigger one bounded host-side keyword lookup within
  authorized text/code directories, followed by an answer with relative source
  citations. No project code runs, no source files change, and the model has no
  external-action tools. This is not exhaustive semantic code search; missing
  results are an evidence gap, not proof that a behavior does not exist.
- Answer in the reader's language with a direct conclusion and short steps or
  one numeric example. Explain technical terms before naming code fields and
  place source citations at the end; do not bury the answer under jargon.
- HTML stays unchanged during Q&A. Completed, failed and cancelled entries are
  saved locally in `.flow-session.json`; only completed answers can be selected.
  Browser refresh restores history. Drafts and partial answers are not compiled.
- Newly completed answers are included by default. The compile control stays
  disabled until at least one completed answer is turned on. Put a trailing
  include switch after the answer so a long reply does not hide the action.
  Keep a short on-screen hint at the switch, composer, and footer; do not rely
  on README text for first-time use. Offline copies must say they cannot ask.
- **整理新版本** asks the model to update affected node details, flow and examples.
  Validate the generated manifest before writing `versions/ID/handbook.html`.
  Do not replace the original. Structural validation does not independently
  prove the new explanation: inspect changed high-risk claims before sharing.
- **离线 HTML** exports the current authored flow plus selected completed answers
  without a model call. PNG exports the diagram, not hidden detail content or
  every Q&A. A static copy cannot use Codex when moved to another computer.

## Verify and Share

Verify one real answer on non-sensitive or authorized data; do not call mock
responses a working Codex connection. Check node context, streaming, cancellation,
saved history, unavailable backend, explicit answer selection, new-version
preservation, offline HTML with no network calls, and nonblank PNGs with complete
nodes and arrows. Test narrow layout and keyboard focus.

The helper binds only `127.0.0.1`, validates Host/Origin and requires an ephemeral
token for API requests. Never expose it to the LAN or disable those checks to
make sharing work. Never embed runtime state in saved HTML or commit the output
folder, local history, logs, startup information, private source excerpts, or
credentials. Keep generated outputs outside public source or in ignored paths.

Default exports remove raw excerpts and recognizable secrets, URLs and absolute
paths, but cannot determine which business facts the user considers confidential.
Use synthetic or explicitly approved facts and inspect public screenshots.
When the local Codex version or configuration cannot establish a safe connection,
show the real limitation; do not silently enable tools, write permissions, an
external relay, a different provider, or paid API credentials.
