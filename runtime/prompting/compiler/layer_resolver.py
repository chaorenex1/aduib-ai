from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.profile import PromptProfile
from runtime.prompting.contracts.section import PromptSection
from runtime.prompting.layers.p0_platform.base import (
    build_actions_with_care_section,
    build_doing_tasks_section,
    build_intro_section,
    build_output_efficiency_section,
    build_system_section,
    build_tone_style_section,
    build_using_tools_section,
)
from runtime.prompting.layers.p1_modes.agent import build_agent_contract_section
from runtime.prompting.layers.p1_modes.chat import build_chat_contract_section
from runtime.prompting.layers.p1_modes.plan import build_plan_contract_section
from runtime.prompting.layers.p1_modes.registry import get_mode_definition
from runtime.prompting.layers.p1_modes.team import build_team_contract_section
from runtime.prompting.layers.p2_profiles.agent_profile import (
    build_profile_examples_section,
    build_profile_identity_section,
    build_profile_output_contract_section,
    build_profile_rules_section,
    build_workflow_charter_section,
)
from runtime.prompting.layers.p2_profiles.profile_registry import PromptProfileRegistry
from runtime.prompting.layers.p3_session.document_working_set import (
    build_active_focus_spans_section,
    build_applied_operations_section,
    build_artifact_refs_section,
    build_document_summaries_section,
    build_pending_operations_section,
    build_tracked_documents_section,
)
from runtime.prompting.layers.p3_session.session_overlay import (
    build_memory_state_section,
    build_permission_state_section,
    build_runtime_capabilities_section,
    build_workspace_rules_section,
)
from runtime.prompting.layers.p4_turn.attachments import (
    build_capability_delta_attachment,
    build_diagnostics_attachment,
    build_document_change_attachment,
    build_document_excerpt_attachments,
    build_invoked_skills_attachment,
    build_mcp_instructions_delta_attachment,
    build_memory_attachment,
    build_nested_memory_attachments,
    build_permission_delta_attachment,
    build_plan_reminder_attachment,
    build_queued_command_attachment,
    build_relevant_memories_attachment,
    build_skill_discovery_attachment,
    build_skill_listing_attachment,
    build_task_notification_attachment,
    build_team_mailbox_attachment,
)
from runtime.prompting.layers.p4_turn.turn_input_pack import (
    build_brief_section,
    build_current_date_section,
    build_env_info_section,
    build_frc_section,
    build_language_section,
    build_mcp_instructions_section,
    build_output_style_section,
    build_plan_state_section,
    build_recent_decisions_section,
    build_scratchpad_section,
    build_session_goal_section,
    build_session_guidance_section,
    build_summarize_tool_results_section,
    build_team_context_section,
    build_token_budget_section,
    build_turn_goal_section,
)


class LayerResolver:
    def __init__(self, profile_registry: PromptProfileRegistry | None = None) -> None:
        self.profile_registry = profile_registry or PromptProfileRegistry()

    def get_profile(self, context: PromptContext) -> PromptProfile:
        default_profile_id = f"default_{context.mode}"
        return self.profile_registry.get(context.profile_id or default_profile_id) or PromptProfile(
            profile_id=default_profile_id,
            title=default_profile_id.replace("_", " ").title(),
        )

    def resolve_p0_sections(self, context: PromptContext) -> list[PromptSection]:
        return [
            section
            for section in [
                build_intro_section(context),
                build_system_section(context),
                build_doing_tasks_section(context),
                build_actions_with_care_section(context),
                build_using_tools_section(context),
                build_tone_style_section(context),
                build_output_efficiency_section(context),
            ]
            if section is not None
        ]

    def resolve_p1_sections(self, context: PromptContext) -> list[PromptSection]:
        by_mode = {
            "chat": build_chat_contract_section,
            "plan": build_plan_contract_section,
            "agent": build_agent_contract_section,
            "team": build_team_contract_section,
        }
        return [by_mode[context.mode](context)]

    def resolve_p2_sections(self, context: PromptContext) -> list[PromptSection]:
        profile = self.get_profile(context)
        return [
            section
            for section in [
                build_profile_identity_section(context, profile),
                build_profile_rules_section(context, profile),
                build_workflow_charter_section(context, profile),
                build_profile_output_contract_section(context, profile),
                build_profile_examples_section(context, profile),
            ]
            if section is not None
        ]

    def resolve_p3_system_sections(self, context: PromptContext) -> list[PromptSection]:
        return [
            section
            for section in [
                build_workspace_rules_section(context),
                build_memory_state_section(context),
                build_runtime_capabilities_section(context),
                build_permission_state_section(context),
            ]
            if section is not None
        ]

    def resolve_p3_user_meta_sections(self, context: PromptContext) -> list[PromptSection]:
        return [
            section
            for section in [
                build_tracked_documents_section(context),
                build_document_summaries_section(context),
                build_active_focus_spans_section(context),
                build_pending_operations_section(context),
                build_applied_operations_section(context),
                build_artifact_refs_section(context),
            ]
            if section is not None
        ]

    def resolve_p4_system_sections(self, context: PromptContext) -> list[PromptSection]:
        return [
            section
            for section in [
                build_language_section(context),
                build_output_style_section(context),
                build_env_info_section(context),
                build_session_guidance_section(context),
                build_scratchpad_section(context),
                build_token_budget_section(context),
                build_brief_section(context),
                build_frc_section(context),
                build_summarize_tool_results_section(context),
                build_mcp_instructions_section(context),
            ]
            if section is not None
        ]

    def resolve_p4_user_meta_sections(self, context: PromptContext) -> list[PromptSection]:
        return [
            section
            for section in [
                build_current_date_section(context),
                build_session_goal_section(context),
                build_turn_goal_section(context),
                build_plan_state_section(context),
                build_team_context_section(context),
                build_recent_decisions_section(context),
            ]
            if section is not None
        ]

    def resolve_p4_attachments(self, context: PromptContext) -> list[PromptAttachment]:
        attachments: list[PromptAttachment] = []
        attachments.extend(
            attachment
            for attachment in [
                build_memory_attachment(context),
                build_relevant_memories_attachment(context),
                build_skill_listing_attachment(context),
                build_skill_discovery_attachment(context),
                build_invoked_skills_attachment(context),
                build_mcp_instructions_delta_attachment(context),
                build_diagnostics_attachment(context),
                build_document_change_attachment(context),
                build_queued_command_attachment(context),
                build_task_notification_attachment(context),
                build_plan_reminder_attachment(context),
                build_team_mailbox_attachment(context),
                build_permission_delta_attachment(context),
                build_capability_delta_attachment(context),
            ]
            if attachment is not None
        )
        attachments.extend(build_nested_memory_attachments(context))
        attachments.extend(build_document_excerpt_attachments(context))
        return attachments

    def allowed_system_section_ids(self, context: PromptContext) -> set[str]:
        return set(get_mode_definition(context.mode).system_section_ids)

    def allowed_user_meta_section_ids(self, context: PromptContext) -> set[str]:
        return set(get_mode_definition(context.mode).user_meta_section_ids)

    def allowed_attachment_types(self, context: PromptContext) -> set[str]:
        return set(get_mode_definition(context.mode).attachment_types)
