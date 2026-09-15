# Visual knowledge handbooks

Legacy diagram mode: one reader question, one diagram. For newcomer or vague-question tasks, use the default layered learning mode in [learning.md](learning.md). Use this mode when the reader asks how a flow or rule works and needs a checkable HTML walkthrough. A whole-project atlas is optional after that question is answered.

## Authoring contract

Pin one question first. Write `knowledge.json` after inspecting only the evidence needed to answer it. The renderer does not infer business semantics. Directory import is only a candidate evidence map, never the completed explanation.

A useful delivery contains that question, one primary flow, the nodes required by the flow, conditions/branches, source links, and explicit gaps. Do not add sibling systems for completeness. Use explicit ID references to establish relationships; same names or neighboring IDs alone are insufficient. Distinguish a reading route from a proven call/configuration relationship. The home page is a vertical flowchart for this question: switchable exclusive lanes when there are two or more entry paths, then a shared tail. Lane titles come from the manifest. The architecture map is optional thickening, not the default home. The 15/30/60-minute route stays on the reading-guide page. Source pages stay linked from nodes or flow steps, offer a return link to the originating context, and are omitted from the first-level sidebar. Directory import remains an evidence draft; it does not invent an architecture map. Content fragments must not include `<script>`, `on*=` handlers, or `javascript:` URLs; lane switching uses `data-flow-lane` plus `atlas.js`.

Separate source claims into configuration declarations, client descriptions, checked references and unknown runtime behavior. When server code is absent, do not borrow a reference website's formulas as project truth. Record stale dates or document/code differences next to affected nodes.

For spreadsheet evidence, read actual sheet/range values, preserve grouped continuation rows, bound columns even if formatting extends to XFD, and record path, sheet/range and SHA256. Never execute repository scripts to inspect data. Only copy bounded excerpts into a private output outside the portfolio repository.

## Manifest

```json
{
  "title": "Sample system handbook",
  "book_id": "unique-project-id",
  "summary": "Map, behavior and evidence",
  "sources": [
    {"id":"rule","title":"Unlock rule","path":"config/rules.txt","locator":"L1","excerpt":"Unlock at level 10","sha256":"snapshot hash"}
  ],
  "project": {
    "purpose": "What a newcomer should understand first",
    "audience": "Who this system map is for",
    "status": "partial",
    "layers": [{"id":"client","title":"Client","summary":"...","status":"verified","sources":[]}],
    "entrypoints": [{"title":"Main entry","path":"src/main.ts","summary":"...","status":"declared","sources":[]}],
    "runtime": [{"title":"Local run","command":"...","summary":"...","status":"open","sources":[]}]
  },
  "flows": [{
     "id":"primary-flow",
     "title":"The first end-to-end task",
     "goal":"What the reader should be able to explain",
     "status":"partial",
     "lanes":[
       {"id":"path-a","title":"Path A","tone":"a","handoff":"join shared","steps":[
         {"kind":"start","label":"Entry A","action":"...","status":"declared","tone":"a"}
       ]}
     ],
     "shared":{"title":"Shared tail","banner":"Shared tail","steps":[
       {"kind":"formula","label":"Common result","action":"...","systems":["growth"],"sources":[],"status":"partial","tone":"shared"}
     ]}
   }],
  "risks": [{"title":"Missing runtime evidence","impact":"high","status":"open","detail":"...","next":"...","sources":[]}],
  "systems": [
      {"id":"growth","title":"Growth","summary":"When progression opens","question":"When does progression open?","nodes":[
      {"id":"unlock","title":"Unlock condition","body":"The configuration declares level 10.","kind":"配置声明","sources":["rule"],"related":[],"branches":[
        {"title":"Meets condition","body":"The declared prerequisite is satisfied; runtime enforcement still requires verification."},
        {"title":"Does not meet condition","body":"The declared prerequisite is not satisfied."}
      ]}
    ]}
  ],
  "relations": []
}
```

IDs use lowercase letters, digits and hyphens, begin with a letter and have at most 45 characters. System/source IDs are unique; `index`, `reading-guide`, `architecture`, `flows`, `risks` and `source-` prefixes are reserved for generated pages. Nodes are unique within each system. Strings are plain text, escaped by the renderer. `question` is the secondary topic prompt; if omitted, `summary` is used. `details` is optional expandable prose; topic `branches` is an optional list of title/body pairs. Status values are `verified`, `declared`, `partial`, or `open`; the renderer displays them instead of hiding uncertainty.

The first `flows[]` item is the home diagram. Prefer `lanes[]` plus optional `shared` over a flat `steps` list. Each lane needs `id` and `title`; optional `tone` is `a|b|c|d|shared`, used only for color. Optional `start` and `handoff` are labels. `groups[]` nest phase blocks. Step `kind` is `start|check|formula|end|exit|note`. Step `lines[]` may include `text`, optional `tag` (`att|def|cond|both|base`), `label`, and `note`. Flow-step `branches[]` may contain nested `steps`. If `lanes` is omitted, existing `steps` render as a single lane. Toggle controls appear only when there are two or more lanes. Treat the vertical flowchart as the first-screen artifact: give it the full reading column, keep formula lines readable without shrinking type, and mark the shared tail as a distinct stage with a separator and banner. Parallel `branches[]` sit side by side; do not invent topology, motion, or runtime impact beyond authored steps.

Relations use `from`, `to`, `label`, `status` referring to system IDs. Mark unverified relationships as reading associations. Every source can be reached from its business nodes and links back to them.

## Build and run

```text
python scripts/build_knowledge.py knowledge.json new-handbook-directory
python scripts/verify_handbook.py new-handbook-directory
python scripts/chat_server.py new-handbook-directory --port 8765
```

Output must be new; the renderer never recursively replaces an existing directory. To update a generated handbook's styling, copy the changed bundled assets to its `assets/` and run `build_handbook.py`. To revise manifest content, render to a new sibling version and retain the previous one until checked.

## Reader acceptance

Check vertical flowchart → lane switch → shared tail → topic → evidence → back to node; branch switching; asking from a node; source links from answers; draft and conversation after a page change/refresh; unrelated question; missing model/key; browser storage denied; narrow layout; keyboard navigation and theme. On a desktop reading column the diagram should not sit in a squeezed text measure; formula lines may scroll horizontally rather than wrap into a stacked column.

Q&A starts in evidence-only mode. This returns excerpts, not an AI-generated answer, and works without a provider. Model mode is explicit and has a per-page transmission confirmation. Keys stay in relay environment or direct-mode page memory. Conversation persistence is tab session storage, not durable cloud storage. Closing the browser session may remove it.

A static page cannot inherit agent billing or credentials. Offer copying the question plus evidence back into the agent. Report external-provider testing separately from mock-provider tests, and never send private data just to prove a connection works.

## Delivery boundaries

Report the pinned question, actual topic/node/source counts, deepest verified chain, uncovered systems, source freshness and missing runtime evidence. Do not equate page count with completeness, and do not treat an unanswered neighboring topic as part of this delivery. Keep reusable code and synthetic examples in the public-ready skill, private manifests and generated pages elsewhere. Do not publish without user authorization.
