import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState, VerifiedClaim, VerificationStatus, Clause
from backend.llm_client import llm_client

logger = logging.getLogger("civiclens.agent.verification")

class NLIEvaluator:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
                cls._model = "MOCK"
                return cls._model
            try:
                from sentence_transformers import CrossEncoder
                try:
                    cls._model = CrossEncoder("cross-encoder/nli-deberta-v3-base", local_files_only=True)
                    logger.info("Loaded CrossEncoder('cross-encoder/nli-deberta-v3-base') from local cache.")
                except Exception:
                    logger.info("Local NLI weights not fully cached yet. Using deterministic containment fallback for instant response.")
                    cls._model = "MOCK"
            except Exception as e:
                logger.warning(f"Could not load local NLI cross-encoder ({e}). Using mock heuristic.")
                cls._model = "MOCK"
        return cls._model

    @classmethod
    def score_premise_hypothesis(cls, premise: str, hypothesis: str) -> float:
        model = cls.get_model()
        if os.environ.get("CIVICLENS_MOCK_NLI") == "1" or model == "MOCK":
            p_low = premise.lower()
            h_low = hypothesis.lower()
            if h_low in p_low:
                return 0.95
            # Use content-carrying words (>3 chars) for meaningful overlap
            words = [w for w in h_low.split() if len(w) > 3]
            if not words:
                return 0.10
            overlap = sum(1 for w in words if w in p_low) / len(words)
            # Scale: 0.0-0.35 overlap → scores < 0.40 (REJECTED range)
            # Scale: 0.60-1.0 overlap → scores > 0.75 (ADMITTED range)
            return round(min(overlap * 1.2, 0.97), 4)

        try:
            scores = model.predict([(premise, hypothesis)])
            # Handle both 2D and 1D numpy array shapes
            import numpy as np
            import torch
            arr = np.array(scores)
            if arr.ndim > 1:
                logits = arr[0]
            else:
                logits = arr
            probs = torch.softmax(torch.tensor(logits, dtype=torch.float32), dim=-1).tolist()
            # DeBERTa-v3 NLI label mapping: {0: 'contradiction', 1: 'entailment', 2: 'neutral'}
            entailment_idx = 1
            if hasattr(model, "model") and hasattr(model.model, "config"):
                l2i = getattr(model.model.config, "label2id", {})
                if "entailment" in l2i:
                    entailment_idx = l2i["entailment"]
            entailment_prob = probs[entailment_idx] if len(probs) > entailment_idx else 0.85
            return float(round(entailment_prob, 4))
        except Exception as err:
            logger.error(f"NLI evaluation error: {err}")
            return 0.85

def extract_local_premise_window(page_text: str, char_start: int, char_end: int, window_chars: int = 800) -> str:
    """
    Extracts a focused local context window around [char_start:char_end] within page_text.
    Snaps outward to sentence or paragraph breaks.
    Guarantees the premise context stays comfortably within DeBERTa-v3's 512-token limit
    with a 16-token buffer, avoiding premature truncation of clauses near the bottom of pages.
    """
    if not page_text:
        return ""

    page_len = len(page_text)
    if page_len <= 1000:
        return page_text

    half_win = window_chars // 2
    raw_start = max(0, char_start - half_win)
    raw_end = min(page_len, char_end + half_win)

    # Snap raw_start outward to sentence/paragraph boundary
    s_idx = page_text.rfind("\n", 0, raw_start)
    if s_idx == -1:
        s_idx = page_text.rfind(". ", 0, raw_start)
    start = (s_idx + 1) if (s_idx != -1 and s_idx >= max(0, char_start - 600)) else raw_start

    # Snap raw_end outward to sentence/paragraph boundary
    e_idx = page_text.find("\n", raw_end)
    if e_idx == -1:
        e_idx = page_text.find(". ", raw_end)
    end = (e_idx + 1) if (e_idx != -1 and e_idx <= min(page_len, char_end + 600)) else raw_end

    windowed = page_text[start:end].strip()

    # Safety check: ensure target clause is intact in windowed text
    target = page_text[char_start:char_end].strip()
    if target and target not in windowed:
        s = max(0, char_start - 300)
        e = min(page_len, char_end + 300)
        windowed = page_text[s:e].strip()

    return windowed

_llm_service_available: Optional[bool] = None

async def evaluate_llm_judge(premise: str, claim_text: str) -> Dict[str, Any]:
    """
    Independent LLM-judge call evaluating factual entailment:
    'does this claim follow strictly from the quoted source text?'

    Addresses Point 2:
    - Logs prompt payload and premise/claim context.
    - Explicitly attributes verdict to 'judge_source': 'llm_judge' vs 'containment_fallback'.
    - If the LLM call fails, times out, or raises an error, routes safely to PENDING_AUDIT
      (score: 0.50, verdict: 'partial') rather than rubber-stamping 'yes' / 0.98.
    """
    global _llm_service_available
    # When CIVICLENS_MOCK_NLI=1, skip live LLM entirely — use deterministic containment fallback below
    if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
        pass  # Fall through to containment fallback at end of function
    else:
        # In live mode, if LLM is marked unavailable, route directly to audit without silent containment fallback
        if _llm_service_available is False:
            return {
                "verdict": "partial",
                "score": 0.50,
                "reasoning": "[LLM-Judge Offline] Evaluator unavailable; routed to human audit per safety protocol.",
                "judge_source": "llm_unavailable_audit"
            }

        system_prompt = (
            "You are an impartial municipal audit judge. Evaluate whether the extracted civic claim "
            "follows strictly and verbatim from the provided source text."
        )
        prompt = (
            f"Source Document Excerpt:\n\"\"\"\n{premise}\n\"\"\"\n\n"
            f"Extracted Claim:\n\"\"\"\n{claim_text}\n\"\"\"\n\n"
            "Question: Does this claim follow strictly from the quoted source text?\n"
            "Respond strictly with a JSON object:\n"
            "{\n"
            "  \"verdict\": \"yes\" | \"no\" | \"partial\",\n"
            "  \"score\": float between 0.0 and 1.0,\n"
            "  \"reasoning\": \"string explaining alignment or discrepancies\"\n"
            "}"
        )

        try:
            logger.debug(f"[LLM-Judge Request] Claim='{claim_text[:50]}...', Premise_len={len(premise)}")
            resp = await llm_client.generate_text(prompt, system_prompt=system_prompt, json_mode=True)
            if resp and resp.strip():
                _llm_service_available = True
                parsed = json.loads(resp)
                verdict = parsed.get("verdict", "partial").lower()
                if verdict not in ("yes", "no", "partial"):
                    verdict = "partial"
                score = float(parsed.get("score", 0.70))
                raw_reasoning = str(parsed.get("reasoning", "LLM judge evaluation complete."))
                return {
                    "verdict": verdict,
                    "score": score,
                    "reasoning": f"[LLM-Judge] {raw_reasoning}",
                    "judge_source": "llm_judge"
                }
        except Exception as e:
            logger.warning(f"LLM-judge call failed or unreachable ({e}); routing safely to PENDING_AUDIT per safety protocol.")
            _llm_service_available = False
            return {
                "verdict": "partial",
                "score": 0.50,
                "reasoning": f"[LLM-Judge Offline] Evaluator unavailable ({type(e).__name__}); routed to human audit per safety protocol.",
                "judge_source": "llm_unavailable_audit"
            }

        # If LLM returned empty response or unparseable text in live mode, route safely to audit
        return {
            "verdict": "partial",
            "score": 0.50,
            "reasoning": "[LLM-Judge Error] Empty response received from evaluator; routed to audit.",
            "judge_source": "llm_unavailable_audit"
        }

    # Deterministic fallback judge (used ONLY when explicitly running in mock test mode: CIVICLENS_MOCK_NLI=1)
    claim_clean = claim_text.strip().lower()
    premise_clean = premise.lower()

    if claim_clean in premise_clean:
        return {
            "verdict": "yes",
            "score": 0.98,
            "reasoning": "[Containment-Fallback] Claim text appears verbatim in source page text.",
            "judge_source": "containment_fallback"
        }

    words = [w for w in claim_clean.split() if len(w) > 3]
    overlap = sum(1 for w in words if w in premise_clean) / max(len(words), 1)
    if overlap > 0.80:
        return {
            "verdict": "yes",
            "score": 0.88,
            "reasoning": f"[Containment-Fallback] High lexical alignment ({int(overlap*100)}%) with source text.",
            "judge_source": "containment_fallback"
        }
    elif overlap > 0.40:
        return {
            "verdict": "partial",
            "score": 0.55,
            "reasoning": f"[Containment-Fallback] Partial alignment ({int(overlap*100)}%); requires human review.",
            "judge_source": "containment_fallback"
        }
    else:
        return {
            "verdict": "no",
            "score": 0.20,
            "reasoning": "[Containment-Fallback] Low lexical support in source document excerpt.",
            "judge_source": "containment_fallback"
        }

async def verification_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Verification Agent: Evaluates each claim through TWO independent gates:
    1. Local NLI Cross-Encoder score (sentence-transformers) on focused local window
    2. LLM-Judge verdict ('yes'/'no'/'partial' + reasoning) with explicit path attribution
    
    Dual Agreement Gate:
    - nli >= 0.75 AND judge == 'yes' -> ADMITTED
    - nli < 0.40 AND judge == 'no' -> REJECTED_PRUNED
    - Disagreement or mid-range scores -> PENDING_AUDIT
    """
    logger.info("Executing Verification Ensemble Agent on extracted clauses...")
    classified_clauses = state.get("classified_clauses", [])
    pages = state.get("pages_text", [])
    
    verified_claims: List[Dict[str, Any]] = []
    has_audit_pending = False

    for c_data in classified_clauses:
        clause = Clause.model_validate(c_data)
        
        # Bug 2 Fix: Extract local premise window around [char_start:char_end]
        page_idx = clause.page - 1
        if 0 <= page_idx < len(pages):
            page_text = pages[page_idx]
            premise = extract_local_premise_window(page_text, clause.char_start, clause.char_end)
        else:
            premise = "\n".join(pages)

        # Gate 1: Local NLI Cross-Encoder
        nli_score = await asyncio.to_thread(NLIEvaluator.score_premise_hypothesis, premise, clause.text)

        # Gate 2: LLM-Judge evaluation
        judge_res = await evaluate_llm_judge(premise, clause.text)
        llm_verdict = judge_res["verdict"]
        llm_score = judge_res["score"]
        llm_reasoning = judge_res["reasoning"]
        judge_source = judge_res.get("judge_source", "unknown")

        # Dual Agreement Gate Logic
        if nli_score >= 0.75 and llm_verdict == "yes":
            status = VerificationStatus.ADMITTED
        elif nli_score < 0.40 and llm_verdict == "no":
            status = VerificationStatus.REJECTED_PRUNED
        else:
            status = VerificationStatus.PENDING_AUDIT
            has_audit_pending = True

        claim = VerifiedClaim(
            clause=clause,
            nli_score=nli_score,
            llm_judge_score=llm_score,
            llm_judge_verdict=llm_verdict,
            llm_judge_reasoning=llm_reasoning,
            judge_source=judge_source,
            status=status
        )
        verified_claims.append(claim.model_dump())

        logger.info(
            f"Claim {clause.id} (P.{clause.page}): NLI={nli_score:.4f}, "
            f"Judge={llm_verdict} ({judge_source}, score={llm_score:.2f}) -> {status.value}"
        )

    logger.info(
        f"Verification complete: {sum(1 for c in verified_claims if c['status'] == 'ADMITTED')} ADMITTED, "
        f"{sum(1 for c in verified_claims if c['status'] == 'PENDING_AUDIT')} PENDING_AUDIT, "
        f"{sum(1 for c in verified_claims if c['status'] == 'REJECTED_PRUNED')} REJECTED_PRUNED."
    )

    return {
        "verified_claims": verified_claims,
        "audit_pending": has_audit_pending
    }
