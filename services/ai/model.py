from langfuse.openai import AsyncOpenAI
from openai import AsyncOpenAI

async def send_once(messages: list, **kwargs) -> str:
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                **kwargs
        )
        return str(response.choices[0].message.content)
