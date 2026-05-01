from typing import Literal, TypeAlias

PromptMode: TypeAlias = Literal["chat", "plan", "agent", "team"]
PromptChannel: TypeAlias = Literal["system", "user_meta", "attachment"]
PromptCachePolicy: TypeAlias = Literal["static", "session", "volatile"]
PromptPhase: TypeAlias = Literal["first_turn", "continued_turn"]
RequestFamily: TypeAlias = Literal["openai_chat", "anthropic_messages", "openai_responses"]
