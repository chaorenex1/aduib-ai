import logging

logger = logging.getLogger(__name__)

MEMORY_PROCESS_WORKFLOW = {
    "name": "memory_creation_workflow",
    "description": "创建记忆的工作流",
    "nodes": [
        {
            "name": "create_memory_node",
            "description": "创建记忆节点",
            "type": "agent_call",
            "agent_id": "memory_creation_agent",
            "route_rule": {
                "condition_key": "memory_id",
                "operator": "ne",
                "value": "",
            },
            "next_step": [{
                "name": "assign_memory_topic_node",
                "description": "分配记忆话题节点",
                "type": "agent_call",
            },{
                "name": "assign_memory_domain_node",
                "description": "分配记忆领域节点",
                "type": "agent_call",
            },
            {
                "name": "assign_memory_tags_node",
                "description": "分配记忆标签节点",
                "type": "agent_call",
            }]
        },
        {
            "name": "assign_memory_topic_node",
            "description": "分配记忆话题节点",
            "type": "agent_call",
            "agent_id": "memory_topic_agent",
            "next_step": [
                {
                    "name": "assign_memory_domain_node",
                    "description": "分配记忆领域节点",
                    "type": "agent_call",
                }
            ]
        },
        {
            "name": "assign_memory_domain_node",
            "description": "分配记忆领域节点",
            "type": "agent_call",
            "agent_id": "memory_domain_agent",
            "next_step": [
                {
                    "name": "assign_memory_tags_node",
                    "description": "分配记忆标签节点",
                    "type": "agent_call",
                }
            ]
        },
        {
            "name": "assign_memory_tags_node",
            "description": "分配记忆标签节点",
            "type": "agent_call",
            "agent_id": "memory_tags_agent",
            "next_step": [
                {
                    "name": "update_memory_graph_node",
                    "description": "更新记忆图谱节点",
                    "type": "agent_call",
                }
            ]
        },
        {
            "name": "update_memory_graph_node",
            "description": "更新记忆图谱节点",
            "type": "agent_call",
            "agent_id": "memory_graph_update_agent",
        }
    ],
}

BUILD_MEMORY_WORKFLOWS: list[dict] = [MEMORY_PROCESS_WORKFLOW]

def register_builtin_workflows():
    """register builtin workflows to the database"""
    try:
        from models import Workflow,WorkflowNode,Agent, get_db

        with get_db() as session:
            for workflow_def in BUILD_MEMORY_WORKFLOWS:
                existing = session.query(Workflow).filter(
                    Workflow.name == workflow_def["name"],
                    Workflow.builtin == 1,
                ).first()

                if existing:
                    logger.debug("Builtin workflow '%s' already exists (id=%s)", existing.name, existing.id)
                    continue

                workflow = Workflow(
                    name=workflow_def["name"],
                    description=workflow_def["description"],
                    builtin=1,    
                )
                session.add(workflow)
                session.commit()
                logger.info("Registered builtin workflow '%s' (id=%s)", workflow.name, workflow.id)
                
                nodes = workflow_def["nodes"]
                for node_def in nodes:
                    node = WorkflowNode(
                        name=node_def["name"],
                        description=node_def["description"],
                        type=node_def["type"],
                        workflow_id=workflow.id,
                        route_rule=node_def.get("route_rule"),
                        next_step=node_def.get("next_step"),
                    )
                    if node_def.get("agent_id"):
                        agent = session.query(Agent).filter(
                            Agent.name == node_def["agent_id"],
                            Agent.builtin == 1,
                        ).first()
                        if not agent:
                            logger.warning("Agent '%s' not found for workflow node '%s'", node_def["agent_id"], node.name)
                        else:
                            node.agent_id = agent.id
                    
                    session.add(node)
                session.commit()
    except Exception as e:
        logger.warning("Failed to register builtin workflow: %s", e)
