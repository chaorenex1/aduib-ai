from aduib_rpc.server.rpc_execution.service_call import service

from runtime.generator.generator import LLMGenerator


@service(service_name="CompletionService")
class CompletionService:

    async def generate_completion(self, prompt,temperature=0.0) -> str:
        """
        # Simulate a call to a language model to generate text completion
        """
        return LLMGenerator.generate_content(prompt,temperature)