from dataclasses import dataclass
import json
from typing import Callable

from services.ai.modelService import send_once
from services.prompts import PromptService

async def tool_addition(a: int, b: int):
    return a + b

@dataclass
class Tool:
    parameters: dict[str,str]
    function: Callable


class ContextService:
    def __init__(self) -> None:
        self.iteration_contexts: list[str] = []

    @property
    def whole_context(self) -> str:
        return '\n'.join(self.iteration_contexts)

    def add_to_context(self, context_data: str) -> None:
        self.iteration_contexts.append(context_data)

    async def summarize_context(self) -> None:
        prompt_service = PromptService(label='general')
        system_prompt, langfuse_prompt = prompt_service.get_prompt(
            'SUMMARIZE',
            input_text='\n\n'.join(self.iteration_contexts),
        )
        self.iteration_contexts.clear()
        summarization_response = await send_once([
                {'role': 'system', 'content': system_prompt}
            ], lanfuse_prompt=langfuse_prompt)
        self.iteration_contexts.append(summarization_response)


class AsyncAgent:
    '''
    # Plan
    # Act
    # Respond || Review
    '''
    def __init__(self, user_problem: str, process_loops: int = 2) -> None:
        self.current_context = ContextService()
        self.user_problem = user_problem
        self._iteration_limit = process_loops
        self._iteration = 0
        self._ready_to_respond = False
        self.tools: dict[str, Tool] = {
                'calculate_addition': Tool(function=tool_addition, parameters={'a':'int','b':'int'})
        }
        self.system_prompt = ''
        self.langfuse_prompt = None

    def ensure_system_prompt(self, prompt_name, **kwargs):
        prompt_service = PromptService(label='agents')
        self.system_prompt, self.langfuse_prompt = prompt_service.get_prompt(
            prompt_name,
            **kwargs
        )

    async def use_tool(self, tool_id: str, **parameters) -> str:
        result = await self.tools[tool_id].function(**parameters)
        return result

    async def plan(self):
        self.ensure_system_prompt('AGENTS_PLAN_OUT', user_problem=self.user_problem, tools_list=json.dumps(self.tools))
        response = send_once([
            {'role': 'system', 'content': self.system_prompt},
        ])
        return response

    async def act(self, plan: str) -> str:
        self.ensure_system_prompt('AGENTS_ACT', detailed_plan=plan, step_number=self._iteration, tools_list=json.dumps(self.tools))
        return ''

    async def review(self, action_result: str):
        response = send_once([
            {'role': 'system', 'content': self.system_prompt}
            {'role': 'system', 'content': action_result}
        ])

    async def respond(self):
        ...

    async def process(self):
        ...

    async def summarize(self):
        await self.current_context.summarize_context()

    # Main running loop
    async def deploy(self):
        while True:
            await self.plan()

            action_result = await self.act()

            await self.review(action_result)

            if (self.iteration > self._iteration_limit) or self._ready_to_respond:
                return await self.respond()

            await self.summarize()

            self._iteration = self._iteration + 1
