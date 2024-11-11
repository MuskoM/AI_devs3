from typing import Any, Literal
from langfuse import Langfuse

_PARAM_LIST = Literal['version', 'label', 'max_retries', 'cache_ttl_seconds']


class PromptService:
    def __init__(self, opt_params: dict[_PARAM_LIST, Any]) -> None:
        self.params = opt_params

    def get_prompt(self, prompt_name:str, **prompt_vars):
        langfuse = Langfuse()
        prompt = langfuse.get_prompt(prompt_name, **self.params)
        compiled_prompt = prompt.compile(**prompt_vars)
        return compiled_prompt
