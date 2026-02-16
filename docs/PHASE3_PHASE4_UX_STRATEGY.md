# ChatEPS_PROTO — Phase 3 (UX/UI) + Phase 4 (Strategic) Proposal

This document proposes **lightweight, local-first** UX and architecture improvements for EPS students, teachers, and researchers.

---

## Guiding principles (constraints respected)

- **100% local/offline capable** (Ollama + local DB + local files).
- **Lightweight stack** (incremental enhancements over current FastAPI + static UI / Next.js optional).
- **Data sovereignty first** (explicit provenance, export, local storage).
- Preserve existing core scope: **PDF ingestion, RAG, artifact versioning**.

---

## PHASE 3 — UX/UI Quality of Life

## 1) Cognitive clarity

### 1.1 Visual separation: AI answer vs retrieved sources

**Rationale**
- Reduces confusion between generated reasoning and retrieved evidence.
- Supports pedagogical trust and quick validation.

**Wireframe (chat message card)**
```text
┌──────────────── Assistant ────────────────┐
│ Answer text ... [doc:12 p.4] ...          │
│                                            │
│ Confidence: ████░ 0.78                     │
│ [Show retrieved context ▾]                 │
│  ├─ Doc 12 (practice) p.4 score 0.81       │
│  │  "... excerpt ..."                      │
│  └─ Doc 7 (theory) p.2 score 0.74          │
└────────────────────────────────────────────┘
```

**Component structure (React)**
- `ChatMessageCard`
  - `AssistantAnswer`
  - `ConfidenceChip`
  - `RetrievedContextDrawer`

**Example component code**
```tsx
type Citation = { doc_id:number; title:string; page:number; excerpt:string; score?:number; doc_type?:string };

export function AssistantMessageCard({
  answer,
  confidence,
  citations,
}: { answer:string; confidence:number; citations:Citation[] }) {
  const [open, setOpen] = React.useState(false);
  return (
    <article className="rounded-xl border p-3 bg-sky-50">
      <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: answer }} />
      <div className="mt-2 flex items-center gap-2 text-sm">
        <span className="px-2 py-1 rounded-full bg-white border">Confiance: {(confidence*100).toFixed(0)}%</span>
        <button onClick={() => setOpen(!open)} className="underline">Contexte récupéré {open ? '▴' : '▾'}</button>
      </div>
      {open && (
        <div className="mt-2 space-y-2 border-t pt-2">
          {citations.map((c) => (
            <div key={`${c.doc_id}-${c.page}`} className="rounded border bg-white p-2">
              <div className="text-xs text-slate-600">Doc {c.doc_id} · {c.title} · p.{c.page} · score {((c.score ?? 0)*100).toFixed(0)}%</div>
              <p className="text-sm">{c.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
```

---

### 1.2 Inline source highlighting

**Rationale**
- Makes citation grounding obvious where claims are made.

**Wireframe**
```text
L'enseignement différencié améliore l'engagement [doc:3 p.5].
```

**Component structure**
- `AnswerRenderer`
  - parses `[doc:X p.Y]`
  - turns refs into clickable badges opening source snippet.

**Example code**
```tsx
const refRegex = /\[doc:(\d+) p\.(\d+)\]/g;
export function renderWithSourceAnchors(text:string, onOpen:(docId:number,page:number)=>void) {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(refRegex)) {
    const idx = m.index ?? 0;
    nodes.push(text.slice(last, idx));
    const docId = Number(m[1]);
    const page = Number(m[2]);
    nodes.push(
      <button key={`${idx}-${docId}-${page}`} onClick={() => onOpen(docId, page)} className="mx-1 rounded bg-blue-100 px-1 text-xs">
        doc:{docId} p.{page}
      </button>
    );
    last = idx + m[0].length;
  }
  nodes.push(text.slice(last));
  return <>{nodes}</>;
}
```

---

### 1.3 Confidence indicators

**Rationale**
- Helps student self-regulation and teacher triage.

**Proposal**
- Compute confidence from retrieval signals:
  - top retrieval score,
  - citation count,
  - source diversity.
- Display as `low / medium / high` with numeric percentage.

---

## 2) Learning progression

### 2.1 Visible novice→expert tracker

**Rationale**
- Makes progression explicit and actionable for learners.

**Wireframe**
```text
[Novice]──●────●────○────○──[Expert]
  concepts   justification  transfer
```

**Component structure**
- `ProgressTracker`
  - `MilestoneNode`
  - `MetricDelta`

**Example code**
```tsx
export function ProgressTracker({steps}:{steps:{label:string; done:boolean}[]}) {
  return (
    <ol className="flex gap-3">
      {steps.map((s,i)=>(
        <li key={i} className="flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${s.done ? 'bg-green-500':'bg-slate-300'}`} />
          <span className="text-xs">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
```

---

### 2.2 Session progress indicator

**Rationale**
- Clarifies where user is in co-creation loop.

**States**
- `Question → Retrieval → Synthesis → Reflection`.

### 2.3 Reflection capture panel

**Rationale**
- Captures metacognition systematically for research traces.

**UI**
- Right panel with:
  - confidence slider 1–5,
  - “What changed in your reasoning?” textbox,
  - save as trace event.

---

## 3) RAG transparency

### 3.1 Expandable retrieved-context drawer

**Rationale**
- Full transparency of evidence used by model.

### 3.2 Show document usage map

**Rationale**
- Quickly identifies over-reliance on one source.

**UI**
- Tiny bar chart: `doc_id -> hit count` for current reply.

### 3.3 Retrieval confidence score

**Rationale**
- Supports "how sure is retrieval?" explanation.

**Lightweight formula**
```text
retrieval_confidence = 0.6 * normalized_top_score
                     + 0.3 * source_diversity
                     + 0.1 * citation_count_normalized
```

---

## 4) Interaction ergonomics

### 4.1 Keyboard-first interaction

**Improvements**
- `Ctrl/Cmd+Enter` send
- `Alt+N` new conversation
- `/` focus search/filter
- `Alt+R` toggle retrieved-context drawer

### 4.2 Undo/redo artifact edits

**Rationale**
- Supports iterative writing and experimentation.

**Component structure**
- `ArtifactEditor`
  - local history stack (undo/redo)
  - autosave timer

**Example snippet**
```tsx
const [history, setHistory] = useState<string[]>(['']);
const [cursor, setCursor] = useState(0);
function apply(next:string){
  const h = [...history.slice(0,cursor+1), next];
  setHistory(h); setCursor(h.length-1);
}
function undo(){ if(cursor>0) setCursor(cursor-1); }
function redo(){ if(cursor<history.length-1) setCursor(cursor+1); }
```

### 4.3 Version comparison view

**Rationale**
- Important for teacher review and progression evidence.

**UI**
- Side-by-side diff: `v3` vs `v4`, additions/deletions highlighted.

### 4.4 Auto-save + draft restore

**Rationale**
- Prevents data loss and supports long sessions.

**Implementation**
- Save local draft every 10s in `localStorage` or `drafts` table.
- On reopen: “Restore draft?” prompt.

---

## 5) Research traceability

### 5.1 Exportable traces (JSON/CSV)

**Rationale**
- Enables analysis without external cloud tooling.

**API endpoints**
- `GET /dashboard/traces/export?format=json|csv&anonymize=true`

### 5.2 Conversation tagging

**Rationale**
- Researchers/teachers can classify sessions (e.g., "didactique", "évaluation", "inclusion").

### 5.3 AI influence metrics dashboard

**Metrics**
- `% réponses avec citations`
- `source diversity index`
- `AI suggestion adoption rate` (artifact diffs vs assistant outputs)
- `reflection completion rate`

---

## Suggested UI information architecture

```text
┌──────────────────────────────────────────────┐
│ Header: session + model + status             │
├───────────────┬──────────────────────────────┤
│ Left rail     │ Main panel                   │
│ Conversations │ Chat + source drawer         │
│ + tags/filter │ + reflection panel toggle    │
├───────────────┴──────────────────────────────┤
│ Bottom tabs: Artifacts | Progress | Research │
└──────────────────────────────────────────────┘
```

---

## PHASE 4 — Strategic improvements

## 1) Modular agent architecture

### Target modules
- **Retriever**: evidence selection (lexical/vector/hybrid)
- **Reasoner**: builds candidate pedagogical response
- **Critic**: checks grounding/safety/coverage
- **Synthesizer**: final student-facing answer formatting

**Rationale**
- Better separability and testability.
- Easier ablation studies for research.

---

## 2) Optional multi-agent orchestration (local)

### Lightweight orchestration pattern
```text
User Query
 -> Retriever
 -> Reasoner draft
 -> Critic verdict (grounding/safety)
 -> Synthesizer final
```
- Keep all agents using local Ollama models.
- Enable/disable via feature flag.

---

## 3) Teacher override system

**Features**
- Teacher can lock:
  - required source set,
  - allowed prompt mode,
  - strict-grounding ON.
- Teacher comment injected as high-priority system context.

**Why**
- Preserves pedagogical control in assessed tasks.

---

## 4) Adaptive scaffolding engine

**Input signals**
- confidence trend,
- citation behavior,
- question complexity,
- teacher interventions.

**Adaptive outputs**
- novice: step-by-step + checks
- intermediate: compare alternatives
- expert: critique assumptions + transfer conditions

---

## 5) A/B testing for RAG prompts (offline)

**Local experiment design**
- Prompt A: concise grounding
- Prompt B: grounding + self-check questions
- Assign per conversation hash.
- Log metrics locally in `trace_events`.

**Outcome metrics**
- citation completeness,
- reflection quality,
- turn efficiency (turns to validated artifact).

---

## Implementation roadmap (incremental)

1. **UX transparency layer** (source drawer, confidence chip, inline refs).
2. **Progress + reflection panel** (student-facing + teacher review).
3. **Artifact ergonomics** (undo/redo, autosave, diff view).
4. **Trace export + tagging + influence dashboard**.
5. **Agent modularization & optional multi-agent pipeline**.
6. **A/B prompt framework and research dashboards**.

---

## Clean modular code boundaries (recommended)

```text
api/app/
  services/
    retrieval/
      coarse.py
      vector.py
      rerank.py
    agents/
      retriever.py
      reasoner.py
      critic.py
      synthesizer.py
    scaffolding/
      policy.py
      adapter.py
  routers/
    chat.py
    research.py
    teacher.py
web/
  components/
    chat/
    sources/
    progression/
    artifacts/
    research/
```

This keeps the platform lightweight and modular while preserving local sovereignty requirements.
