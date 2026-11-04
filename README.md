# ScholarGuide — Scholarship Discovery Agent

ScholarGuide helps underserved students in South India find scholarships they qualify for. It answers questions in English or Tamil through an AI agent built with the [Strands Agents SDK](https://strandsagents.com) on Amazon Bedrock, with code-owned facts and a safety escalation hook.

## Who it is for

Students in **Tamil Nadu, Kerala, and Karnataka** pursuing school, diploma, undergraduate, or postgraduate education — especially first-generation learners, rural students, and low-income families who can't navigate English-only scholarship portals.

## What it does

- Takes a student's natural-language question about scholarships
- Looks up curated, verified scholarship guidance from a knowledge base
- Drafts an answer (planner) and checks it (critic) in a multi-agent graph
- Escalates to a human when a query is safety-critical (red-flag hook)
- Responds in English or Tamil

## Architecture

1. **Code owns the facts** — scholarship eligibility criteria, amounts, and deadlines live in `agent/data/guidance.json`. The model reads them but cannot change them.
2. **Planner–critic graph** — a Strands `GraphBuilder` where a planner drafts an answer and a critic rejects it if it cites unverified guidance, answers outside scope, or uses the wrong language. Max 2 revision passes.
3. **Red-flag safety hook** — a Strands `HookProvider` cancels both agents and returns fixed hand-off text when a query contains medical, legal, or safety-critical phrases. No model writes that answer.
4. **Bilingual** — English and Tamil (script) with language detection.
5. **Amazon Bedrock** — Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`) in us-east-1.

## How to run

```bash
pip install -r requirements.txt

# Set up AWS credentials in your own terminal
aws configure          # or: aws sso login
# us-east-1, enable Amazon Nova in Bedrock Model access

# Run the agent from the command line
python -m agent.app "I'm a 2nd year BSc student in Tamil Nadu, income under 1 lakh, what scholarships can I get?"

# Run the Streamlit web interface
streamlit run app.py
```

## Results

Evaluation compares the ScholarGuide agent against a one-prompt baseline on human-labelled cases using `ss measure`. Results are written to `results/MEASURE.md` and `results/FACTS.md`.

> Run `ss measure` to populate the results table. The metrics: emergency recall, unsafe answers, threshold accuracy, citation faithfulness, completeness, goal success, and latency.

## Strands blocks

| Block | Role |
|-------|------|
| Agent (planner) | Drafts scholarship answer with structured output |
| Agent (critic) | Validates answer against guidance, language, citations |
| GraphBuilder | Wires planner → critic → planner (retry on critique failure) |
| HookProvider (RedFlagGate) | Cancels agents on safety-critical queries |
| BedrockModel | Amazon Nova 2 Lite, temperature 0.2 |
| Structured output | Pydantic models force machine-checkable fields |

## Honest limits

- Guidance data covers a sample of scholarships, not every scheme in India
- Cases are labelled by the builder, not yet independently reviewed
- Tamil coverage depends on source translation quality
- The agent answers from curated guidance only — it cannot browse live portals or check real-time deadlines

## Project structure

```
app.py              Streamlit web interface
agent/              Strands agent (planner-critic graph + hook)
  app.py            Graph definition and run loop
  plan.py           Pydantic structured output models
  tools.py          lookup_guidance tool (curated sources only)
  score.py          Deterministic case scoring
  baseline.py       One-prompt baseline for comparison
  data/guidance.json  Curated scholarship guidance (EDIT ME)
cases.jsonl         Human-labelled test cases (EDIT ME)
ship_kit/           Apache-2.0 toolkit (cases, measure, submit, video)
article/            Builder Center article (fields.md, body.md, cover.svg)
```

## License

Apache-2.0 — see [LICENSE](LICENSE). The `ship_kit/` directory is Apache-2.0 and ships in this repo.
