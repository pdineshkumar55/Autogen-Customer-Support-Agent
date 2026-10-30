import asyncio, os
from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()

async def main():
    client = OpenAIChatCompletionClient(model=os.getenv("MODEL_NAME", "gpt-4o-mini"))
    agent = AssistantAgent("tester", model_client=client,
                           system_message="You are a helpful assistant.")
    result = await agent.run(task="Say hello in one short line.")
    print(result.messages[-1].content)
    await client.close()

asyncio.run(main())