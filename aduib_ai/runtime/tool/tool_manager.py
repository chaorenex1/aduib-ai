import json
import logging

from models import ToolCallResult
from models.engine import get_db
from runtime.entities import AssistantPromptMessage
from runtime.tool.base.tool import Tool
from runtime.tool.base.tool_provider import ToolController
from runtime.tool.builtin_tool.tool_provider import BuiltinToolController
from runtime.tool.entities import ToolProviderType, ToolInvokeResult
from utils import jsonable_encoder

logger = logging.getLogger(__name__)

TOOL_CALL_RESULT_PROMPT = """
The following tools were called by the assistant:
<TOOL_CALL_RESULTS>
{tool_calls}
</TOOL_CALL_RESULTS>
"""

class ToolManager:
    """
    ToolManager is responsible for managing tool providers and their controllers.
    """
    providers: dict[str, ToolController] = {}

    def __init__(self):
        self.providers = {
            ToolProviderType.BUILTIN: BuiltinToolController()
        }

    def get_builtin_tool_controller(self):
        return self.providers[ToolProviderType.BUILTIN]

    def get_tool_controller(self, provider_type: ToolProviderType) -> ToolController:
        """
        Get tool controller by provider type

        :param provider_type: tool provider type
        :return: tool controller
        """
        if provider_type not in self.providers:
            raise ValueError(f"Tool provider {provider_type} not found")
        return self.providers[provider_type]

    def register_tool_controller(self, provider_type: ToolProviderType, controller: ToolController):
        """
        Register a tool controller for a specific provider type

        :param provider_type: tool provider type
        :param controller: tool controller instance
        """
        if provider_type in self.providers:
            raise ValueError(f"Tool provider {provider_type} already registered")
        self.providers[provider_type] = controller
        logger.info(f"Registered tool controller for provider {provider_type}")

    def unregister_tool_controller(self, provider_type: ToolProviderType):
        """
        Unregister a tool controller for a specific provider type
        :param provider_type: tool provider type
        """
        if provider_type not in self.providers:
            raise ValueError(f"Tool provider {provider_type} not registered")
        del self.providers[provider_type]
        logger.info(f"Unregistered tool controller for provider {provider_type}")

    def list_tool_providers(self) -> list[str]:
        """
        List all registered tool providers

        :return: list of tool provider types
        """
        return list(self.providers.keys())

    def invoke_tools(self, tool_calls:list[AssistantPromptMessage.ToolCall],message_id:str) -> ToolInvokeResult|None:
        """
        Invoke tools based on the provided tool calls

        :param tool_calls: list of tool calls to invoke
        :return: aggregated tool invoke result
        """
        with get_db() as session:
            tool_call_result:ToolCallResult=session.query(ToolCallResult).filter(ToolCallResult.message_id == message_id).first()
            if tool_call_result and tool_call_result.state == "success":
                logger.info(f"Tool calls for message {message_id} already completed successfully.")
                return None

        builtin_tool_controller:ToolController = self.get_builtin_tool_controller()
        tool_invoke_results:list[ToolInvokeResult]=[]
        tools:list[Tool]=[]
        tool_call_results:list[ToolCallResult]=[]
        for tool_call in tool_calls:
            tool = builtin_tool_controller.get_tool(tool_call.function.name)
            if not tool:
                logger.warning(f"Tool {tool_call.function.name} not found")
                continue
            tools.append(tool)

            call_result = ToolCallResult(message_id=message_id, tool_call_id=tool_call.id,
                                         tool_call=jsonable_encoder(obj=tool_call, exclude_none=True), state="failed")

            try:
                tool_parameters =json.loads(tool_call.function.arguments)
                result:ToolInvokeResult = next(tool.invoke(tool_parameters=tool_parameters, message_id=message_id))
                if result and result.success:
                    tool_invoke_results.append(result)
                    call_result.state = "success"
                    call_result.result = jsonable_encoder(result, exclude_none=True)
                    tool_call_results.append(call_result)

                    logger.info(f"Tool {tool_call.function.name} invoked successfully with result: {jsonable_encoder(result)}")
                else:
                    call_result.state = "failed"
                    tool_call_results.append(call_result)

                    logger.warning(f"Tool {tool_call.function.name} invoked but returned no result.")
            except Exception as ex:
                logger.exception(f"Error invoking tool {tool_call.function.name}: {ex}")

                tool_invoke_results.append(ToolInvokeResult(result=f"Error invoking tool {tool_call.function.name}: {ex}"))
                call_result.state = "failed"
                tool_call_results.append(call_result)

        if len(tool_invoke_results)!= len(tools):
            logger.warning(f"Some tools were not invoked successfully. Expected {len(tools)} results, got {len(tool_invoke_results)}.")


        tool_call_result_prompt = TOOL_CALL_RESULT_PROMPT.format(
            tool_calls="\n".join([f"Tool: {res.name}, Result: {res.data}" for res in tool_invoke_results])
        )
        aggregated_result = ToolInvokeResult(
            name="AggregatedToolResults",
            data=tool_call_result_prompt,
        )
        with get_db() as session:
            if tool_call_results:
                for call_result in tool_call_results:
                    existing_result = session.query(ToolCallResult).filter(
                        ToolCallResult.message_id == call_result.message_id,
                        ToolCallResult.tool_call_id == call_result.tool_call_id
                    ).first()
                    if existing_result:
                        existing_result.state = call_result.state
                        existing_result.result = call_result.result
                        session.add(existing_result)
                        session.commit()
                    else:
                        session.add(call_result)
                        session.commit()
        return aggregated_result

