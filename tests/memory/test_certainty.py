"""Test decision certainty assessment."""

from __future__ import annotations

from runtime.memory.decision.certainty import (
    CertaintyAssessor,
    CertaintyFactor,
    CertaintyResult,
    DecisionContext,
)
from runtime.memory.decision.models import (
    Decision,
    DecisionCategory,
    DecisionCertainty,
    Evidence,
    EvidenceType,
)


class TestCertaintyAssessor:
    """Test CertaintyAssessor functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.assessor = CertaintyAssessor()

    def test_high_certainty_patterns_chinese(self):
        """Test HIGH_CERTAINTY_PATTERNS match correctly for Chinese."""
        high_certainty_texts = [
            "我们决定了使用Redis作为缓存",
            "团队已经确定采用微服务架构",
            "最终敲定使用PostgreSQL",
        ]

        for text in high_certainty_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.9, f"Expected high certainty (0.9) for: {text}"

    def test_high_certainty_patterns_english(self):
        """Test HIGH_CERTAINTY_PATTERNS match correctly for English."""
        high_certainty_texts = [
            "We have decided to use React for the frontend",
            "The team confirmed using Docker containers",
            "It has been approved and finalized",
        ]

        for text in high_certainty_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.9, f"Expected high certainty (0.9) for: {text}"

    def test_low_certainty_patterns_chinese(self):
        """Test LOW_CERTAINTY_PATTERNS match correctly for Chinese."""
        low_certainty_texts = [
            "我们考虑一下使用MongoDB",
            "可能会采用GraphQL",
            "如果性能不够，也许要用Redis",
            "还没决定使用哪个框架",
        ]

        for text in low_certainty_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.3, f"Expected low certainty (0.3) for: {text}"

    def test_low_certainty_patterns_english(self):
        """Test LOW_CERTAINTY_PATTERNS match correctly for English."""
        low_certainty_texts = [
            "We might use Kubernetes for deployment",
            "Perhaps we should consider using TypeScript",
            "We are still discussing the database choice",
            "Haven't decided on the testing framework yet",
        ]

        for text in low_certainty_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.3, f"Expected low certainty (0.3) for: {text}"

    def test_negation_patterns_chinese(self):
        """Test NEGATION_PATTERNS match correctly for Chinese."""
        negation_texts = [
            "我们没有决定使用这个方案",
            "不要采用这个技术栈",
            "取消了之前的决定",
            "放弃这个架构选择",
        ]

        for text in negation_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.1, f"Expected negation score (0.1) for: {text}"

    def test_negation_patterns_english(self):
        """Test NEGATION_PATTERNS match correctly for English."""
        negation_texts = [
            "We don't want to use this approach",
            "Won't be implementing this solution",
            "Not going to adopt this technology",
        ]

        for text in negation_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.1, f"Expected negation score (0.1) for: {text}"

    def test_neutral_text_default(self):
        """Test neutral text gets default score."""
        neutral_texts = [
            "这是一个技术方案",
            "We need to build a web application",
            "The system requires high performance",
            "",  # Empty text
        ]

        for text in neutral_texts:
            score = self.assessor.assess_linguistic(text)
            assert score == 0.5, f"Expected neutral score (0.5) for: {text}"

    def test_score_to_certainty_mapping(self):
        """Test score to certainty level mapping."""
        test_cases = [
            (0.95, DecisionCertainty.CONFIRMED),
            (0.85, DecisionCertainty.CONFIRMED),
            (0.84, DecisionCertainty.EVIDENCED),
            (0.7, DecisionCertainty.EVIDENCED),
            (0.69, DecisionCertainty.EXPLICIT),
            (0.55, DecisionCertainty.EXPLICIT),
            (0.54, DecisionCertainty.INFERRED),
            (0.4, DecisionCertainty.INFERRED),
            (0.39, DecisionCertainty.IMPLICIT),
            (0.3, DecisionCertainty.IMPLICIT),
            (0.29, DecisionCertainty.TENTATIVE),
            (0.2, DecisionCertainty.TENTATIVE),
            (0.19, DecisionCertainty.DISCUSSING),
            (0.1, DecisionCertainty.DISCUSSING),
            (0.09, DecisionCertainty.UNCERTAIN),
            (0.0, DecisionCertainty.UNCERTAIN),
        ]

        for score, expected_certainty in test_cases:
            result = self.assessor.score_to_certainty(score)
            assert result == expected_certainty, f"Score {score} should map to {expected_certainty}"

    def test_assess_high_certainty_decision(self):
        """Test full assess() with high certainty decision."""
        decision = Decision(
            title="Database Selection",
            summary="Choose PostgreSQL as primary database",
            context="Need reliable ACID compliance",
            decision="我们最终确定使用PostgreSQL",
            rationale="已经决定了PostgreSQL最适合我们的需求",
            category=DecisionCategory.TECHNOLOGY,
            user_confirmed=True,
        )

        # Add verified evidence
        evidence = Evidence(
            type=EvidenceType.CODE_COMMIT,
            description="Database migration scripts",
            reference="commit-123",
            verified=True,
        )
        decision.evidence.append(evidence)

        context = DecisionContext(
            subsequent_references=3,
            conflicting_decisions=[],
        )

        result = self.assessor.assess(decision, context)

        # Check result structure
        assert isinstance(result, CertaintyResult)
        assert result.score >= 0.7  # Should be high (adjusted for actual calculation)
        assert result.certainty in [DecisionCertainty.CONFIRMED, DecisionCertainty.EVIDENCED]
        assert len(result.factors) >= 4  # linguistic, evidence, user_confirmed, references

        # Check individual factors
        factor_names = [f.name for f in result.factors]
        assert "linguistic" in factor_names
        assert "evidence" in factor_names
        assert "user_confirmed" in factor_names
        assert "references" in factor_names

    def test_assess_low_certainty_decision(self):
        """Test full assess() with low certainty decision."""
        decision = Decision(
            title="Framework Discussion",
            summary="Considering React vs Vue",
            context="Frontend technology evaluation",
            decision="我们可能会考虑使用React",
            rationale="还在讨论中，也许React比较合适",
            category=DecisionCategory.TECHNOLOGY,
            user_confirmed=False,
        )

        context = DecisionContext(
            subsequent_references=0,
            conflicting_decisions=["decision-456"],
        )

        result = self.assessor.assess(decision, context)

        # Check result structure
        assert isinstance(result, CertaintyResult)
        assert result.score < 0.4  # Should be low
        assert result.certainty in [
            DecisionCertainty.UNCERTAIN,
            DecisionCertainty.DISCUSSING,
            DecisionCertainty.TENTATIVE,
        ]

        # Should have conflict penalty factor
        factor_names = [f.name for f in result.factors]
        assert "conflict_penalty" in factor_names

    def test_evidence_boosting_score(self):
        """Test assess() with evidence boosting score."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="Neutral decision text",
            rationale="No specific patterns",
            category=DecisionCategory.TECHNOLOGY,
        )

        # Add multiple verified evidence
        for i in range(3):
            evidence = Evidence(
                type=EvidenceType.CODE_COMMIT,
                description=f"Evidence {i}",
                reference=f"ref-{i}",
                verified=True,
            )
            decision.evidence.append(evidence)

        result = self.assessor.assess(decision)

        # Evidence should boost score significantly
        evidence_factor = next(f for f in result.factors if f.name == "evidence")
        assert evidence_factor.score > 0.5  # 3 * 0.3 = 0.9, but capped at 1.0

    def test_user_confirmed_boosting_score(self):
        """Test assess() with user_confirmed boosting score."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="Neutral decision text",
            rationale="No specific patterns",
            category=DecisionCategory.TECHNOLOGY,
            user_confirmed=True,
        )

        result = self.assessor.assess(decision)

        # User confirmation should boost score
        user_confirmed_factor = next(f for f in result.factors if f.name == "user_confirmed")
        assert user_confirmed_factor.score == 1.0

        # Overall score should be higher than base linguistic score
        # 0.5 * 0.3 (linguistic) + 0.0 * 0.3 (evidence) + 1.0 * 0.25 (user_confirmed) + 0.0 * 0.15 (references) = 0.4
        assert result.score >= 0.4

    def test_conflicting_decisions_penalty(self):
        """Test assess() with conflicting decisions penalty."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="我们确定使用这个方案",  # High certainty language
            rationale="已经决定了",
            category=DecisionCategory.TECHNOLOGY,
        )

        context_with_conflicts = DecisionContext(
            conflicting_decisions=["decision-1", "decision-2"],
        )

        context_without_conflicts = DecisionContext()

        result_with_conflicts = self.assessor.assess(decision, context_with_conflicts)
        result_without_conflicts = self.assessor.assess(decision, context_without_conflicts)

        # Score should be lower with conflicts
        assert result_with_conflicts.score < result_without_conflicts.score

        # Should have conflict penalty factor
        conflict_factors = [f for f in result_with_conflicts.factors if f.name == "conflict_penalty"]
        assert len(conflict_factors) == 1
        assert conflict_factors[0].score == -0.3

    def test_subsequent_references_boost(self):
        """Test assess() with subsequent references."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="Neutral decision text",
            rationale="No specific patterns",
            category=DecisionCategory.TECHNOLOGY,
        )

        context = DecisionContext(subsequent_references=5)

        result = self.assessor.assess(decision, context)

        # References should boost score
        references_factor = next(f for f in result.factors if f.name == "references")
        assert references_factor.score == 1.0  # 5 * 0.2 = 1.0 (capped)

    def test_certainty_result_structure(self):
        """Test CertaintyResult structure."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.TECHNOLOGY,
        )

        result = self.assessor.assess(decision)

        # Check result structure
        assert hasattr(result, "certainty")
        assert hasattr(result, "score")
        assert hasattr(result, "factors")

        assert isinstance(result.certainty, DecisionCertainty)
        assert isinstance(result.score, float)
        assert isinstance(result.factors, list)
        assert 0.0 <= result.score <= 1.0

        # Check factor structure
        for factor in result.factors:
            assert isinstance(factor, CertaintyFactor)
            assert hasattr(factor, "name")
            assert hasattr(factor, "score")
            assert hasattr(factor, "weight")
            assert hasattr(factor, "details")

    def test_decision_context_defaults(self):
        """Test DecisionContext defaults."""
        context = DecisionContext()

        assert context.subsequent_references == 0
        assert context.conflicting_decisions == []
        assert context.occurrence_count == 1

    def test_assess_with_none_context(self):
        """Test assess() with None context uses defaults."""
        decision = Decision(
            title="Test Decision",
            summary="Test",
            context="Test",
            decision="Test decision",
            rationale="Test rationale",
            category=DecisionCategory.TECHNOLOGY,
        )

        # Should not raise error with None context
        result = self.assessor.assess(decision, None)

        assert isinstance(result, CertaintyResult)
        assert len(result.factors) >= 4  # Should have all base factors

    def test_empty_text_linguistic_analysis(self):
        """Test linguistic analysis with empty text."""
        score = self.assessor.assess_linguistic("")
        assert score == 0.5

        score = self.assessor.assess_linguistic("   ")  # Whitespace only
        assert score == 0.5

    def test_evidence_score_calculation(self):
        """Test evidence score calculation logic."""
        # No evidence
        assert self.assessor._compute_evidence_score([]) == 0.0

        # Unverified evidence doesn't count
        unverified = Evidence(
            type=EvidenceType.CODE_COMMIT,
            description="Test",
            reference="test",
            verified=False,
        )
        assert self.assessor._compute_evidence_score([unverified]) == 0.0

        # Verified evidence counts
        verified = Evidence(
            type=EvidenceType.CODE_COMMIT,
            description="Test",
            reference="test",
            verified=True,
        )
        assert self.assessor._compute_evidence_score([verified]) == 0.3
        assert self.assessor._compute_evidence_score([verified, verified]) == 0.6

        # Score is capped at 1.0
        many_verified = [verified] * 10
        assert self.assessor._compute_evidence_score(many_verified) == 1.0

    def test_reference_score_calculation(self):
        """Test reference score calculation logic."""
        # No references
        assert self.assessor._compute_reference_score(0) == 0.0

        # Some references
        assert self.assessor._compute_reference_score(1) == 0.2
        assert self.assessor._compute_reference_score(3) == 0.6

        # Score is capped at 1.0
        assert self.assessor._compute_reference_score(10) == 1.0