# Source review and adaptation record (2026-10-02)

Reviewed all 11 Persona Studio pages (text and rendered pages) and all 67 NSona slides (rendered contact sheets; expanded key engineering/evaluation slides). NSona embedded font text extraction is corrupt; visual reading is authoritative. Cached prior conversation is advisory, not a substitute for these PDFs. Original attachments were retained unchanged in the original local Persona Studio workspace. The SOUL public integration branch does not redistribute them.

SHA256 Persona Studio: `1700ceb106c1a101f2cb41bfa31c457ba9d7817e83440866a14cced3ebc14b6d`. NSona: `c4f732afb11ff2d6b7d13a949b26c0ae870734ca954885a4d75cbb4a63ae5e91`.

The 2026-10-05 integration additionally reviewed all of the one-page `Soul_분석리포트.pdf` and all of `05-report.html`; the dynamic mapping and sample-data exclusions are in `18_SOUL_INTEGRATION.md`.

## NSona complete review map
| Pages | Reviewed content | Decision |
|---|---|---|
|1-5|title, agenda, designer/engineer collaboration, product origin|background|
|6-11|user understanding, persona research limitations, existing tools, live collaboration|adapt for founders without existing customer data|
|12-16|persona creation, selectable traits, 1:3 chat, image ideation, research process with calibration|retain generation/style/validation/calibration; omit image tasks|
|17-19|quality questions and nine UX criteria; five conceptual groups|retain service-specific evaluation principle; replace metrics with PSV-9|
|20|template + generation rules experiment|retain structured card + explicit generation constraints; do not inherit reported percentages|
|21|task/instruction and rubric-based instruction experiment|retain prompt/rubric contract; no performance claim transferred|
|22-23|researcher feedback and AI UX hub|retain real user feedback loop; exclude hub expansion|
|24-28|engineering/user perspectives, three challenges|retain agent service + evaluation separation|
|29-33|multi-party speaker identification, discourse and per-agent knowledge|retain independent states and explicit speaker IDs|
|34-35|Who demographic info / What product experience / How chat style|adapt to startup constraints; UNKNOWN and no stereotypes|
|36-37|turn-taking + adjacency; theory and model-based speaker prediction|retain scheduling/reply relations; explicit heuristic controller for MVP|
|38-39|summary buffer and growing inter-turn complexity|retain bounded context; omit image caption/search hooks|
|40-41|LLM selects node order/edges, dynamic graph + microservices|exclude from MVP; state machine and modular functions instead|
|42-46|collaboration quality, UX-specific benchmark, VLOps feedback loop|retain evaluation feedback; defer event-driven infrastructure|
|47-50|evaluation collaboration, research review, limitations of persona imitation|retain human-aware evaluation; no invented lived experience|
|51|nine rubrics and baseline persona, five-point example|retain scored rubrics; baseline schema is not real participant data|
|52-53|human-annotated Gold responses|retain human Gold field and expert rationale; demo Gold remains null|
|54|three independent judges, majority winner, A/B order swap|implement optional three judges and remapped order swap|
|55-58|six commercial + six compact models, different strengths, self-refinement weaknesses|record as NSona-only results; no names recoverable (masked); no Qwen equivalence assumed|
|59-60|quantitative/qualitative feedback and future fine-tuning|retain later evidence-based tuning gate|
|61-67|cross-role collaboration and closing/Q&A|retain design-first then implementation role sequence|

## Persona Studio complete review map
| Pages | Product source | MVP decision |
|---|---|---|
|1-2|founder problem, seven reported stakeholder interviews, actual interviews complemented|retain positioning; reported interview summary is L2, not available L3 transcripts|
|3|mentoring, generic LLM, synthetic research alternatives|retain problem hypotheses; competitive claims require later verification|
|4-5|idea-first target suggestion/edit/add, multi-persona chat, comparative summary|implemented with human selection step|
|6-7|quality/calibration, institutions pay first, later individual subscription/enterprise|retain business roadmap; no pricing fabrication or billing MVP|
|8|PoC metrics and prototype; fine-tuned API; default opposition persona|replace early tuning with prompts; replace forced opposition with grounded conditional views|
|9|architecture graphic; procurement/participant/PoC mentoring needs|retain three modules; procurement remains UNKNOWN|
|10|real validation/positioning risk and team capability|retain real interview next steps and measurement gate|
|11|IT category, team/application details and video link|context only; video not required as implementation source|

## Freeze
Nine numbered design documents are implementation source of truth. User's requested private/group/private protocol, eight blocks, PSV-9, evidence levels and hardware targets take priority over different original plans. Acceptance evidence lives in STATUS and REQUIREMENTS_MATRIX. All additions above are our design decisions, not NSona's claims.

Full 2026-10-03 re-review, bibliography corrections and all67-page mappings: [docs/14_NSONA_RESEARCH_AUDIT.md](14_NSONA_RESEARCH_AUDIT.md). [docs/13_PERSONA_LOUNGE_DESIGN.md](13_PERSONA_LOUNGE_DESIGN.md) supersedes older product dialogue defaults.
