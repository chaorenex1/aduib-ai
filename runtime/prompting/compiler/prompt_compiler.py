from uuid import uuid4

from runtime.prompting.compiler.cache_policy import CachePolicyPlanner
from runtime.prompting.compiler.layer_resolver import LayerResolver
from runtime.prompting.compiler.precedence import PrecedenceResolver
from runtime.prompting.compiler.validators import PromptCompilerValidator
from runtime.prompting.contracts.compiled import CompiledPrompt
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.trace import PromptTrace
from runtime.prompting.renderers.attachment_renderer import AttachmentRenderer
from runtime.prompting.renderers.system_renderer import SystemRenderer
from runtime.prompting.renderers.user_meta_renderer import UserMetaRenderer
from runtime.prompting.runtime.prompt_trace_store import PromptTraceStore


class PromptCompiler:
    def __init__(
        self,
        *,
        layer_resolver: LayerResolver | None = None,
        precedence_resolver: PrecedenceResolver | None = None,
        cache_policy_planner: CachePolicyPlanner | None = None,
        validator: PromptCompilerValidator | None = None,
        system_renderer: SystemRenderer | None = None,
        user_meta_renderer: UserMetaRenderer | None = None,
        attachment_renderer: AttachmentRenderer | None = None,
        trace_store: PromptTraceStore | None = None,
    ) -> None:
        self.layer_resolver = layer_resolver or LayerResolver()
        self.precedence_resolver = precedence_resolver or PrecedenceResolver()
        self.cache_policy_planner = cache_policy_planner or CachePolicyPlanner()
        self.validator = validator or PromptCompilerValidator()
        self.system_renderer = system_renderer or SystemRenderer()
        self.user_meta_renderer = user_meta_renderer or UserMetaRenderer()
        self.attachment_renderer = attachment_renderer or AttachmentRenderer()
        self.trace_store = trace_store or PromptTraceStore()

    def compile(self, context: PromptContext) -> tuple[CompiledPrompt, PromptTrace]:
        self.validator.validate_context(context)

        p0_sections = self.layer_resolver.resolve_p0_sections(context)
        p1_sections = self.layer_resolver.resolve_p1_sections(context)
        p2_sections = self.layer_resolver.resolve_p2_sections(context)
        p3_system_sections = self.layer_resolver.resolve_p3_system_sections(context)
        p3_user_meta_sections = self.layer_resolver.resolve_p3_user_meta_sections(context)
        p4_system_sections = self.layer_resolver.resolve_p4_system_sections(context)
        p4_user_meta_sections = self.layer_resolver.resolve_p4_user_meta_sections(context)
        attachments = self.layer_resolver.resolve_p4_attachments(context)

        allowed_system = self.layer_resolver.allowed_system_section_ids(context)
        allowed_user_meta = self.layer_resolver.allowed_user_meta_section_ids(context)
        allowed_attachment_types = self.layer_resolver.allowed_attachment_types(context)

        system_sections = [
            section
            for section in self.precedence_resolver.merge_system_sections(
                p0_sections,
                p1_sections,
                p2_sections,
                p3_system_sections,
                p4_system_sections,
            )
            if section.section_id in allowed_system
        ]
        user_meta_sections = [
            section
            for section in self.precedence_resolver.merge_user_meta_sections(
                p3_user_meta_sections,
                p4_user_meta_sections,
            )
            if section.section_id in allowed_user_meta
        ]
        attachments = [
            attachment for attachment in attachments if attachment.attachment_type in allowed_attachment_types
        ]

        self.validator.validate_sections(system_sections)
        self.validator.validate_sections(user_meta_sections)
        self.validator.validate_attachments(attachments)

        trace = PromptTrace(
            trace_id=str(uuid4()),
            mode=context.mode,
            phase=context.phase,
            section_ids=[section.section_id for section in [*system_sections, *user_meta_sections]],
            attachment_ids=[attachment.attachment_id for attachment in attachments],
            cache_misses=[section.section_id for section in system_sections if section.cache_policy == "volatile"],
            cache_hits=[section.section_id for section in system_sections if section.cache_policy != "volatile"],
        )

        compiled = CompiledPrompt(
            system_sections=system_sections,
            user_meta_sections=user_meta_sections,
            attachments=attachments,
            system_text=self.system_renderer.render(system_sections),
            user_meta_messages=self.user_meta_renderer.render(user_meta_sections),
            attachment_messages=self.attachment_renderer.render(attachments),
            cache_segments=self.cache_policy_planner.split(system_sections),
            trace_id=trace.trace_id,
        )
        self.trace_store.save(trace)
        return compiled, trace
