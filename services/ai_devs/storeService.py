from typing import Any
from os import environ
import yaml

from loguru import logger as LOG

try:
    API_TASK_KEY = environ['AI_DEVS_TASK_KEY']
except KeyError:
    raise EnvironmentError('AI_DEVS_TASK_KEY not found, have you provided a key?')


class AIDevsStore:
    def __init__(self) -> None:
        self.secrets: dict[str, Any] = self.initStore()

    def initStore(self) -> dict[str, Any]:
        try:
            with open('.secrets.yml') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            LOG.error('Unable to find .secrets.yaml file, tasks from AI_Devs will not work')
            return {}

    def read_task_secrets(self, task_name: str) -> dict[str, Any]:
        task_secrets = self.secrets.get(task_name)
        if task_secrets:
            return task_secrets
        return {}

