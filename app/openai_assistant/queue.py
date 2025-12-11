import asyncio
from collections import deque
from typing import NamedTuple

from openai import AsyncOpenAI
import os


class Request(NamedTuple):
    user_id: int
    thread_id: str
    message: str
    future: asyncio.Future


class OpenAIRequestQueue:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.queue = deque()
        self.lock = asyncio.Lock()

    async def send(self, user_id: int, thread_id: str, message: str) -> str:
        future = asyncio.get_running_loop().create_future()
        self.queue.append(Request(user_id, thread_id, message, future))
        # Убедимся, что только один воркер запускается на очередь
        async with self.lock:
            if not hasattr(self, "_worker_running") or not self._worker_running:
                self._worker_running = True
                asyncio.create_task(self._worker())
        return await future

    async def _worker(self):
        try:
            while self.queue:
                request = self.queue.popleft()
                try:
                    response = await self.client.beta.threads.messages.create(
                        thread_id=request.thread_id,
                        role="user",
                        content=request.message,
                    )
                    run = await self.client.beta.threads.runs.create_and_poll(
                        thread_id=request.thread_id,
                        assistant_id=os.getenv("ASSISTANT_ID"),
                        temperature = 0.7,
                        top_p = 1
                    )
                    messages = await self.client.beta.threads.messages.list(thread_id=request.thread_id)
                    answer = messages.data[0].content[0].text.value
                    request.future.set_result(answer)
                except Exception as e:
                    request.future.set_exception(e)
        finally:
            self._worker_running = False

openai_queue = OpenAIRequestQueue()
