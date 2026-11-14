import pytest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.memory.qa_vault import (
    extract_distinctive_keywords,
    questions_have_semantic_conflict,
    QAMemoryVault
)


def test_extract_distinctive_keywords_preserves_domain_terms():
    text = "What is your current notice period in days?"
    keywords = extract_distinctive_keywords(text)
    assert "current" in keywords
    assert "notice" in keywords
    assert "period" in keywords
    assert "days" in keywords
    # Stop words should be pruned
    assert "what" not in keywords
    assert "is" not in keywords
    assert "your" not in keywords


def test_semantic_conflict_detection():
    # Polarity conflict: current vs expected CTC
    q1 = "What is your current CTC in LPA?"
    q2 = "What is your expected CTC in LPA?"
    assert questions_have_semantic_conflict(q1, q2) is True

    # Same polarity should not conflict
    q3 = "Kindly mention your current fixed CTC"
    assert questions_have_semantic_conflict(q1, q3) is False

    # Skill modifier conflict: React Native vs React.js
    q_react = "How many years of experience do you have with React?"
    q_native = "How many years of experience do you have with React Native?"
    assert questions_have_semantic_conflict(q_react, q_native) is True


def test_memory_vault_store_and_retrieve():
    vault = QAMemoryVault()
    user_id = "test_user_unit_123"

    # Store candidate answers
    vault.learn(
        question="What is your total years of experience in Python?",
        answer="4.5 years",
        category="experience",
        user_id=user_id
    )

    # Query with identical question
    ans = vault.find_answer(
        question="What is your total years of experience in Python?",
        user_id=user_id
    )
    assert ans == "4.5 years"

    # Query with semantic paraphrase
    paraphrased = "Total years of Python experience?"
    ans_para = vault.find_answer(
        question=paraphrased,
        user_id=user_id
    )
    assert ans_para == "4.5 years"

    # Querying an unrelated question should return None
    ans_unrelated = vault.find_answer(
        question="Are you legally authorized to work in the United States?",
        user_id=user_id
    )
    assert ans_unrelated is None
