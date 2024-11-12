from typing import Any

from langfuse import Langfuse
from langfuse.api.resources.dataset_items.client import NotFoundError
from loguru import logger as LOG

class PromptService:
    def __init__(self, **params: Any) -> None:
        self.params: dict[str, Any] = params

    def get_prompt(self, prompt_name:str, **prompt_vars):
        langfuse = Langfuse()
        try:
            prompt = langfuse.get_prompt(prompt_name, **self.params)
            compiled_prompt = prompt.compile(**prompt_vars)
        except NotFoundError:
            LOG.error('{} prompt not found', prompt_name)
            raise RuntimeError('Prompt not found')

        return compiled_prompt, prompt
