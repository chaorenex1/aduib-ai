from __future__ import annotations

from runtime.memory.scope import InheritanceMode, MemoryScopeLevel, ScopeFilter, ScopeInferrer, ScopeNode, ScopePath
from runtime.memory.types.base import MemoryScope


def _make_descendant(scope: ScopePath) -> ScopePath:
    return ScopePath(
        user_id=scope.user_id,
        nodes=[
            *scope.nodes,
            ScopeNode(level=MemoryScopeLevel.TASK, id="task-1", name="Task"),
        ],
    )


def _node_by_level(scope: ScopePath, level: MemoryScopeLevel) -> ScopeNode | None:
    return next((node for node in scope.nodes if node.level == level), None)


class TestScopePath:
    def test_personal_scope(self):
        user_id = "user-1"

        scope = ScopePath.personal(user_id)

        assert scope.level == MemoryScopeLevel.PERSONAL
        assert len(scope.nodes) == 1
        assert scope.project_id is None
        assert scope.module_id is None

    def test_work_scope(self):
        user_id = "user-1"

        scope = ScopePath.work(user_id)

        assert scope.level == MemoryScopeLevel.WORK
        assert len(scope.nodes) == 2
        assert scope.project_id is None
        assert scope.module_id is None

    def test_project_scope(self):
        user_id = "user-1"

        scope = ScopePath.project(user_id, "proj-1", "Project One")

        assert scope.level == MemoryScopeLevel.PROJECT
        assert scope.project_id == "proj-1"
        assert scope.module_id is None

    def test_module_scope(self):
        user_id = "user-1"

        scope = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")

        assert scope.level == MemoryScopeLevel.MODULE
        assert scope.project_id == "proj-1"
        assert scope.module_id == "mod-1"

    def test_level_property_empty(self):
        scope = ScopePath(user_id="user-1", nodes=[])

        assert scope.level == MemoryScopeLevel.PERSONAL

    def test_ancestors(self):
        user_id = "user-1"
        scope = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")

        ancestors = scope.ancestors()

        assert [ancestor.level for ancestor in ancestors] == [
            MemoryScopeLevel.PERSONAL,
            MemoryScopeLevel.WORK,
            MemoryScopeLevel.PROJECT,
            MemoryScopeLevel.MODULE,
        ]
        assert ancestors[-1].is_same_path(scope)

    def test_is_ancestor_of(self):
        user_id = "user-1"
        personal = ScopePath.personal(user_id)
        work = ScopePath.work(user_id)

        assert personal.is_ancestor_of(work) is True

    def test_is_descendant_of(self):
        user_id = "user-1"
        project = ScopePath.project(user_id, "proj-1", "Project One")
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")

        assert module.is_descendant_of(project) is True

    def test_is_same_path(self):
        user_id = "user-1"
        path_a = ScopePath.project(user_id, "proj-1", "Project One")
        path_b = ScopePath.project(user_id, "proj-1", "Project One")

        assert path_a.is_same_path(path_b) is True

    def test_distance_to_same(self):
        scope = ScopePath.work("user-1")

        assert scope.distance_to(scope) == 0

    def test_distance_to_ancestor(self):
        user_id = "user-1"
        ancestor = ScopePath.work(user_id)
        descendant = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")

        assert ancestor.distance_to(descendant) == 2

    def test_distance_to_descendant(self):
        user_id = "user-1"
        ancestor = ScopePath.work(user_id)
        descendant = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")

        assert descendant.distance_to(ancestor) == -2

    def test_distance_to_unrelated(self):
        user_id = "user-1"
        scope_a = ScopePath.project(user_id, "proj-1", "Project One")
        scope_b = ScopePath.project(user_id, "proj-2", "Project Two")

        assert scope_a.distance_to(scope_b) == 100

    def test_to_legacy_scope_personal(self):
        scope = ScopePath.personal("user-1")

        assert scope.to_legacy_scope() == MemoryScope.PERSONAL

    def test_to_legacy_scope_work(self):
        scope = ScopePath.work("user-1")

        assert scope.to_legacy_scope() == MemoryScope.WORK

    def test_to_legacy_scope_project(self):
        scope = ScopePath.project("user-1", "proj-1", "Project One")

        assert scope.to_legacy_scope() == MemoryScope.PROJECT

    def test_to_legacy_scope_module(self):
        scope = ScopePath.module("user-1", "proj-1", "Project One", "mod-1", "Module One")

        assert scope.to_legacy_scope() == MemoryScope.MODULE

    def test_from_legacy_scope(self):
        user_id = "user-1"

        work_scope = ScopePath.from_legacy_scope("work", user_id)
        project_scope = ScopePath.from_legacy_scope(MemoryScope.PROJECT, user_id)
        module_scope = ScopePath.from_legacy_scope("module", user_id)

        assert work_scope.is_same_path(ScopePath.work(user_id))
        assert project_scope.is_same_path(ScopePath.project(user_id, "default", "Project"))
        assert module_scope.is_same_path(ScopePath.module(user_id, "default", "Project", "default", "Module"))

    def test_cross_user_not_ancestor(self):
        work_user_a = ScopePath.work("user-1")
        project_user_b = ScopePath.project("user-2", "proj-1", "Project One")

        assert work_user_a.is_ancestor_of(project_user_b) is False


class TestScopeFilter:
    def test_exact_match(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        other_module = ScopePath.module(user_id, "proj-1", "Project One", "mod-2", "Module Two")
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.EXACT)

        assert scope_filter.matches(module) is True
        assert scope_filter.matches(other_module) is False

    def test_exact_no_match(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        ancestor = module.ancestors()[1]
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.EXACT)

        assert scope_filter.matches(ancestor) is False

    def test_ancestors_match(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.ANCESTORS)

        for ancestor in module.ancestors():
            assert scope_filter.matches(ancestor) is True

        descendant = _make_descendant(module)
        assert scope_filter.matches(descendant) is False

    def test_descendants_match(self):
        user_id = "user-1"
        project = ScopePath.project(user_id, "proj-1", "Project One")
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        scope_filter = ScopeFilter.from_scope(project, InheritanceMode.DESCENDANTS)

        assert scope_filter.matches(project) is True
        assert scope_filter.matches(module) is True
        assert scope_filter.matches(ScopePath.work(user_id)) is False

    def test_full_match_ancestor(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        ancestor = module.ancestors()[2]
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.FULL)

        assert scope_filter.matches(ancestor) is True

    def test_full_match_descendant(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        descendant = _make_descendant(module)
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.FULL)

        assert scope_filter.matches(descendant) is True

    def test_different_user_no_match(self):
        user_id = "user-1"
        module = ScopePath.module(user_id, "proj-1", "Project One", "mod-1", "Module One")
        other_user_scope = ScopePath.module("user-2", "proj-1", "Project One", "mod-1", "Module One")
        scope_filter = ScopeFilter.from_scope(module, InheritanceMode.FULL)

        assert scope_filter.matches(other_user_scope) is False


class TestScopeInferrer:
    def test_infer_personal(self):
        inferrer = ScopeInferrer()

        scope = inferrer.infer("just chatting", "user-1")

        assert scope.level == MemoryScopeLevel.PERSONAL

    def test_infer_work(self):
        inferrer = ScopeInferrer()

        scope = inferrer.infer("Fix API bug tonight", "user-1")

        assert scope.level == MemoryScopeLevel.WORK

    def test_infer_life(self):
        inferrer = ScopeInferrer()

        scope = inferrer.infer("家庭旅行计划", "user-1")

        assert scope.level == MemoryScopeLevel.LIFE

    def test_infer_project_keyword(self):
        inferrer = ScopeInferrer()
        inferrer.register_project("alpha", "proj-1", "Alpha")

        scope = inferrer.infer("alpha roadmap", "user-1")

        assert scope.level == MemoryScopeLevel.PROJECT
        assert scope.project_id == "proj-1"
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Alpha"

    def test_infer_module_keyword(self):
        inferrer = ScopeInferrer()
        inferrer.register_module("auth", "mod-1", "Auth", "proj-1", "Alpha")

        scope = inferrer.infer("auth module updates", "user-1")

        assert scope.level == MemoryScopeLevel.MODULE
        assert scope.module_id == "mod-1"
        assert scope.project_id == "proj-1"
        assert _node_by_level(scope, MemoryScopeLevel.MODULE).name == "Auth"
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Alpha"

    def test_infer_explicit_context_project(self):
        inferrer = ScopeInferrer()

        scope = inferrer.infer(
            "alpha roadmap",
            "user-1",
            context={"project_id": "proj-2", "project_name": "Project Two"},
        )

        assert scope.level == MemoryScopeLevel.PROJECT
        assert scope.project_id == "proj-2"
        assert scope.module_id is None
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Project Two"

    def test_infer_explicit_context_module(self):
        inferrer = ScopeInferrer()

        scope = inferrer.infer(
            "alpha roadmap",
            "user-1",
            context={
                "module_id": "mod-2",
                "module_name": "Billing",
                "project_id": "proj-9",
                "project_name": "Alpha",
            },
        )

        assert scope.level == MemoryScopeLevel.MODULE
        assert scope.module_id == "mod-2"
        assert scope.project_id == "proj-9"
        assert _node_by_level(scope, MemoryScopeLevel.MODULE).name == "Billing"
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Alpha"

    def test_register_project(self):
        inferrer = ScopeInferrer()

        inferrer.register_project("beta", "proj-3", "Beta")
        scope = inferrer.infer("beta meeting notes", "user-1")

        assert scope.level == MemoryScopeLevel.PROJECT
        assert scope.project_id == "proj-3"
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Beta"

    def test_register_module(self):
        inferrer = ScopeInferrer()

        inferrer.register_module("search", "mod-5", "Search", "proj-4", "Gamma")
        scope = inferrer.infer("search indexing issue", "user-1")

        assert scope.level == MemoryScopeLevel.MODULE
        assert scope.module_id == "mod-5"
        assert scope.project_id == "proj-4"
        assert _node_by_level(scope, MemoryScopeLevel.MODULE).name == "Search"
        assert _node_by_level(scope, MemoryScopeLevel.PROJECT).name == "Gamma"
