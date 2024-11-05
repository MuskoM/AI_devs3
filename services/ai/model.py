from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

async def send_once(messages: list[ChatCompletionMessageParam]):
    async with AsyncOpenAI() as ai:
        response = await ai.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages
        )
        return response.choices[0].message.content
