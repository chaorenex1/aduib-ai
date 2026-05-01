from runtime.prompting.contracts.profile import PromptProfile


class PromptProfileRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, PromptProfile] = {
            "default_chat": PromptProfile(
                profile_id="default_chat",
                title="Chat Profile",
                description="Answer clearly, stay grounded, and avoid pretending to execute work.",
            ),
            "default_plan": PromptProfile(
                profile_id="default_plan",
                title="Planning Profile",
                description="Clarify scope, produce a plan, and keep implementation separate from planning decisions.",
                workflow_charter=(
                    "Produce a plan that is concrete enough to execute and verify, but do not skip open questions."
                ),
                output_contract_name="plan_summary",
            ),
            "default_agent": PromptProfile(
                profile_id="default_agent",
                title="Execution Profile",
                description=(
                    "Drive work forward with local evidence, explicit verification, and minimal unnecessary motion."
                ),
            ),
            "default_team": PromptProfile(
                profile_id="default_team",
                title="Coordinator Profile",
                description="Coordinate worker lanes, merge outputs, and retain final ownership of correctness.",
                workflow_charter=(
                    "Keep tasks bounded, gather evidence from workers, and synthesize a verified final result."
                ),
            ),
        }

    def get(self, profile_id: str | None) -> PromptProfile | None:
        if not profile_id:
            return None
        profile = self._profiles.get(profile_id)
        return profile.model_copy(deep=True) if profile is not None else None

    def list(self) -> list[PromptProfile]:
        return [profile.model_copy(deep=True) for profile in self._profiles.values()]
