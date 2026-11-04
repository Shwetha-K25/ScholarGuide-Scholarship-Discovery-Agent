# ScholarGuide: An AI-Powered Bilingual Scholarship Discovery Agent for South Indian Students

Thousands of scholarships go unclaimed every year in India — not because students don't qualify, but because the information is scattered across dozens of websites, written only in English, and buried under dense eligibility text. The students who lose out most are the ones who need it most: first-generation learners, rural students, and families who don't speak English at home.

ScholarGuide is an AI agent built with the Strands Agents SDK on Amazon Bedrock that helps these students discover scholarships they qualify for and answers their questions in their own language — English or Tamil.

---

## Social Impact

### Who it is for

ScholarGuide serves students in Tamil Nadu, Kerala, and Karnataka pursuing school, diploma, undergraduate, or postgraduate education. The web interface collects a student profile — state, education level, course, year of study, and family income — and the agent behind it answers questions about which scholarships match, what the eligibility criteria are, and how to apply.

The students who benefit most are the ones currently excluded from scholarship discovery:

- **First-generation learners** whose parents cannot navigate English-only portals
- **Rural students** with limited internet access who need a single, trusted source
- **Low-income families** (below ₹1 lakh / ₹1–2.5 lakh annually) who may not even know scholarships exist for their income bracket
- **Tamil-speaking students** who need answers in Tamil, not English

### The problem

India has hundreds of central and state scholarships — post-matric, pre-matric, merit-cum-means, minority, SC/ST/OBC, disability, and more. Each has its own portal, its own eligibility text, and its own deadlines. A student from a village in Tamil Nadu has to visit 10+ websites, all in English, to find what they qualify for. Most give up.

### What ScholarGuide does

The agent takes a student's natural-language question — "I'm a second-year BSc student in Tamil Nadu, family income under 1 lakh, what scholarships can I get?" — and returns a plain-language answer citing only curated, verified scholarship guidance. It works in English and Tamil script. When a question is outside its scope (medical advice, legal guarantees, deadline-guaranteed answers), it escalates to a human rather than guessing.

### Measured results

> **Note:** The evaluation harness (`ss measure`) compares the ScholarGuide agent against a one-prompt baseline on human-labelled cases. Measured numbers will be published in `results/FACTS.md` and updated here. The methodology and metrics:

- **Cases**: Human-labelled scholarship questions in English and Tamil, including escalation cases
- **Metrics**: emergency recall (did the agent hand off when it should?), unsafe answers (did it answer a case it should have escalated?), threshold accuracy (key facts present), citation faithfulness (only citing verified guidance), completeness, goal success, and latency

Results table from `results/MEASURE.md` will be inserted here once the evaluation is run.

---

## Technical Execution

### Architecture in five lines

1. **Code owns the facts**: Scholarship eligibility criteria, amounts, and deadlines live in a curated JSON knowledge base (`agent/data/guidance.json`) — the model reads them but cannot change them.
2. **Planner–critic graph**: A Strands multi-agent graph where a planner drafts an answer and a critic checks it against the guidance for accuracy, language, and citation validity.
3. **Red-flag safety hook**: A Strands hook intercepts queries involving medical, legal, or safety-critical topics and cancels the agents, returning fixed hand-off text — no model writes that answer.
4. **Bilingual**: English and Tamil (script) with language detection; Amazon Translate backs cross-language support.
5. **Amazon Bedrock**: The model is Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`), running in us-east-1.

### Strands blocks used

| Block | What it does |
|-------|-------------|
| **Agent** (planner) | Drafts a scholarship answer calling `lookup_guidance`, structured output with answer, steps, escalation, and citations |
| **Agent** (critic) | Reviews the draft — rejects if it cites an unverified id, answers outside the guidance, or uses the wrong language |
| **GraphBuilder** | Wires planner → critic → planner (with a retry condition: revise if the critic says `ok=false`, max 2 passes) |
| **HookProvider** (RedFlagGate) | Cancels both agents before they run if the query contains a red-flag phrase; returns fixed hand-off text |
| **BedrockModel** | Amazon Nova 2 Lite at temperature 0.2 for consistent, low-hallucination answers |
| **Structured output** | Pydantic models (`Answer`, `Critique`) force the planner and critic to return machine-checkable fields |

### The baseline comparison

The baseline is a single Strands agent with one prompt and the same guidance — no graph, no hook, no critic. `ss measure` runs both on the same signed cases and scores them identically. The agent should beat the baseline on:

- **Emergency recall**: the hook guarantees hand-off; the baseline relies on the model noticing
- **Citation faithfulness**: the critic rejects unverified citations; the baseline has no check
- **Language consistency**: the critic rejects wrong-language answers; the baseline does not

### How to run it

```bash
pip install -r requirements.txt
# Set up AWS credentials in your own terminal (aws configure or env vars)
python -m agent.app "I'm a 2nd year BSc student in Tamil Nadu, income under 1 lakh, what scholarships can I get?"
```

The Streamlit web interface:
```bash
streamlit run app.py
```

### Safety design

The red-flag hook is the hard stop. When a query contains phrases indicating medical emergencies, self-harm, or situations where wrong information could cause harm (e.g., "double the dose", "stop taking", "suicide", "chest pain"), the hook cancels both agents and returns fixed hand-off text directing the student to a qualified person. The model never writes this answer — code does.

---

## What We Learned

### Failure: The critic accepted answers in the wrong language

**What broke:** In early testing, the critic sometimes passed answers that mixed English and Tamil when the user asked in Tamil, because the language check was too lenient — it only checked whether Tamil characters were *present*, not whether English was *absent*.

**How we found it:** A Tamil test case (`example-2`) was answered with a mix of Tamil script and English loanwords. The critic said `ok=true`.

**What we changed:** The critic's system prompt was tightened to reject any answer that contains the wrong language's script. The score function (`agent/score.py`) now checks `lang_ok` — Tamil answers must contain Tamil script and not be empty; English answers must not contain Tamil script. A wrong-language answer scores 0 on completeness regardless of other fields.

**Re-measured:** [Before/after numbers from `ss measure` will be inserted here.]

### What surprised us

The hardest part wasn't the agent — it was curating the guidance data. Scholarship portals often contradict themselves, have outdated pages, and list eligibility in dense legal text. Every item in `guidance.json` needs a source URL and a date someone verified it. Code-owning the facts means the facts have to actually be correct.

### Honest limits

- The guidance data covers a sample of scholarships, not every scheme in India
- Cases are labelled by the builder, not yet reviewed by independent educators
- Tamil coverage depends on the quality of the source translations
- The agent answers based on curated guidance only — it cannot browse live portals or check real-time deadlines

---

## Originality

### Beyond the workshop

The Builder Center workshop teaches the Strands SDK from simple loops to multi-agent swarms. ScholarGuide extends beyond those lessons in three ways:

1. **Bilingual safety escalation**: The red-flag hook and hand-off text work in both English and Tamil — the workshop examples are English-only. The hook checks for Tamil red-flag phrases (இரட்டிப்பு, அதிக மாத்திரை) alongside English ones.

2. **Code-owns-the-facts for a knowledge domain**: The workshop's worked example (HeatSafe) uses code-owned facts for safety thresholds. ScholarGuide applies the same pattern to eligibility criteria — a domain where getting a number wrong (income threshold, age limit, deadline) could cost a student a scholarship. The planner cannot cite anything not in the curated JSON, and the critic enforces this.

3. **Student-profile-aware matching**: The Streamlit interface collects structured profile data (state, education, course, year, income) that contextualizes the agent's responses — going beyond a single-prompt chatbot toward a profile-aware advisor.

### AWS services used

| Service | Role |
|---------|------|
| Amazon Bedrock (Nova 2 Lite) | The LLM for both planner and critic agents |
| Amazon Translate | Cross-language support and verification |
| AWS (us-east-1) | Inference region |

### What makes it different

Most scholarship tools are either static databases (no Q&A) or generic chatbots (no verified facts, no safety). ScholarGuide sits in between: a conversational agent that can only say what the curated guidance supports, with a graph that self-corrects and a hook that escalates when the stakes are too high.

---

## Links

- **Repository**: https://github.com/Shwetha-K25/ScholarGuide-Scholarship-Discovery-Agent
- **Demo video**: [Add public link after `ss video`]
- **License**: Apache-2.0

---

*Built for the AWS Builder Center "Strands SDK: Workshop to Ship" hackathon.*
