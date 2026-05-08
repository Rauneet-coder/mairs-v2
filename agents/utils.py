class ModelRouter:
    def __init__(self, finetuned_client, fast_client):
        self.finetuned = finetuned_client
        self.fast = fast_client
        self.FINETUNED_AGENTS = ["rca", "resolver", "capacity_planner"]

    def get_client(self, agent_name: str):
        return self.finetuned if agent_name in self.FINETUNED_AGENTS else self.fast

    async def call_with_fallback(self, agent_name: str, messages: list, **kwargs):
        try:
            return await self.get_client(agent_name).chat.completions.create(messages=messages, **kwargs)
        except Exception:
            if self.get_client(agent_name) == self.finetuned:
                return await self.fast.chat.completions.create(messages=messages, **kwargs)
            raise
