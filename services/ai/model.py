from langfuse.openai import AsyncOpenAI
from openai import AsyncOpenAI

async def send_once(messages: list) -> str:
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages
        )
        return str(response.choices[0].message.content)
