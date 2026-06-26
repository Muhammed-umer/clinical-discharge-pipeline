"""
Clinical judge prompts — version 1.

Covers:
  - Single-claim grounding judge (JUDGE_PROMPT)
  - Batch multi-claim grounding judge (BATCH_JUDGE_PROMPT)
"""

JUDGE_PROMPT_VERSION: str = "v1"
BATCH_JUDGE_PROMPT_VERSION: str = "v1"

# ─── Single-claim judge ───────────────────────────────────────────────────────

JUDGE_PROMPT = """
You are an elite Clinical Safety Judge.

Your responsibility is to determine whether a generated clinical claim is fully grounded in the supplied source note contexts.

CLAIM TO VERIFY

Category:
{claim_category}

Claim Value:
{claim_value}

Claim ID:
{claim_id}

SOURCE NOTE CONTEXTS

--- CONTEXT 1 ---
{context_1}

--- CONTEXT 2 ---
{context_2}

--- CONTEXT 3 ---
{context_3}

GROUNDING RULES

1. Evaluate only the supplied contexts.

2. Never use external medical knowledge.

3. Never infer missing information.

4. The claim must be explicitly supported by the provided text.

5. If evidence is incomplete, ambiguous, or unavailable:
   return PARTIALLY_SUPPORTED.

VERDICT DEFINITIONS

SUPPORTED

* Claim is explicitly documented.
* No inference required.
* Evidence directly supports the claim.

PARTIALLY_SUPPORTED

* Claim is partially documented.
* Supporting context exists but is incomplete.
* Dosage, frequency, duration, timing, or severity may be missing.

NOT_SUPPORTED

* Claim is absent.
* Claim contradicts context.
* Claim represents inference or hallucination.

OUTPUT FORMAT

{{
  "verdict": "SUPPORTED | PARTIALLY_SUPPORTED | NOT_SUPPORTED",
  "reasoning": "Explain the decision and reference the exact supporting or conflicting text."
}}

Respond ONLY with valid JSON.
Do not include markdown.
Do not include explanations outside the JSON object.
"""

# ─── Batch multi-claim judge ──────────────────────────────────────────────────

BATCH_JUDGE_PROMPT = """
You are an elite Clinical Safety Judge.

Your responsibility is to determine whether each generated clinical claim is fully grounded in the supplied clinical notes (evidence).

EVIDENCE NOTES:
{evidence_text}

CLAIMS TO VERIFY:
{claims_text}

GROUNDING RULES:
1. Evaluate only the supplied evidence notes.
2. Never use external medical knowledge.
3. Never infer missing information.
4. A claim is SUPPORTED only if it is explicitly documented in the evidence notes without requiring inference.
5. If evidence is incomplete, ambiguous, or unavailable for a claim, it is PARTIALLY_SUPPORTED.
6. If a claim contradicts the notes, or is absent/hallucinated, it is NOT_SUPPORTED.

OUTPUT FORMAT:
Your response must be a JSON array of objects, one for each claim, containing exactly these keys:
- "claim_id": the exact claim ID of the claim.
- "supported": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "NOT_SUPPORTED"
- "confidence": a float representing grounding confidence (0.0 to 1.0)
- "explanation": a string explaining the verdict and referencing the exact supporting or conflicting text.

Example response:
[
  {{
    "claim_id": "claim_1",
    "supported": "SUPPORTED",
    "confidence": 0.95,
    "explanation": "Claim is supported by Resident Note: 'Patient has type 2 diabetes'."
  }}
]

Respond ONLY with valid JSON. Do not include markdown formatting or backticks.
"""
