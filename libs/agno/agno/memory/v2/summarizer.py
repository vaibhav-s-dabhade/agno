from copy import deepcopy
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, List, Optional, cast

from pydantic import BaseModel, Field

from agno.models.base import Model
from agno.models.message import Message
from agno.utils.log import log_debug, log_error, log_info, log_warning
from agno.utils.prompts import get_json_output_prompt
from agno.utils.string import parse_response_model_str


class SessionSummaryResponse(BaseModel):
    """Model for Session Summary."""

    summary: str = Field(
        ...,
        description="Summary of the session. Be concise and focus on only important information. Do not make anything up.",
    )
    topics: Optional[List[str]] = Field(None, description="Topics discussed in the session.")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True, indent=2)


@dataclass
class SessionSummarizer:
    # Model used for summarization
    model: Optional[Model] = None

    # System prompt for the summarizer. If not provided, a default prompt will be used.
    system_prompt: Optional[str] = None

    # Whether the summarizer has created a summary
    summary_updated: bool = False

    def __init__(self, model: Optional[Model] = None, system_prompt: Optional[str] = None):
        self.model = model
        if self.model is not None and isinstance(self.model, str):
            raise ValueError("Model must be a Model object, not a string")
        self.system_prompt = system_prompt

    def update_model(self, model: Model) -> None:
        model = cast(Model, model)
        if model.supports_native_structured_outputs:
            model.response_format = SessionSummaryResponse
            model.structured_outputs = True

        elif model.supports_json_schema_outputs:
            model.response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": SessionSummaryResponse.__name__,
                    "schema": SessionSummaryResponse.model_json_schema(),
                },
            }
        else:
            model.response_format = {"type": "json_object"}

    def get_system_message(self, conversation: List[Message], model: Model) -> Message:
        if self.system_prompt is not None:
            return Message(role="system", content=self.system_prompt)

        # -*- Return a system message for summarization
        system_prompt = dedent("""\
        Analyze the following conversation between a user and an assistant, and extract the following details:
          - Summary (str): Provide a concise summary of the session, focusing on important information that would be helpful for future interactions.
          - Topics (Optional[List[str]]): List the topics discussed in the session.
        Please ignore any frivolous information.
        Conversation:
        """)
        conversation_messages = []
        for message in conversation:
            if message.role == "user":
                conversation_messages.append(f"User: {message.content}")
            elif message.role in ["assistant", "model"]:
                conversation_messages.append(f"Assistant: {message.content}")

        system_prompt += "\n".join(conversation_messages)

        if model.response_format == {"type": "json_object"}:
            system_prompt += "\n" + get_json_output_prompt(SessionSummaryResponse)  # type: ignore

        return Message(role="system", content=system_prompt)

    def run(
        self,
        conversation: List[Message],
    ) -> Optional[SessionSummaryResponse]:
        if self.model is None:
            log_error("No model provided for summary_manager")
            return None

        log_debug("SessionSummarizer Start", center=True)

        if conversation is None or len(conversation) == 0:
            log_info("No conversation provided for summarization.")
            return None

        model_copy = deepcopy(self.model)
        self.update_model(model_copy)

        # Prepare the List of messages to send to the Model
        messages_for_model: List[Message] = [
            self.get_system_message(conversation, model=model_copy),
            # For models that require a non-system message
            Message(role="user", content="Provide the summary of the conversation."),
        ]

        # Generate a response from the Model (includes running function calls)
        response = model_copy.response(messages=messages_for_model)

        if response.content is not None:
            self.summary_updated = True

        log_debug("SessionSummarizer End", center=True)

        # If the model natively supports structured outputs, the parsed value is already in the structured format
        if (
            model_copy.supports_native_structured_outputs
            and response.parsed is not None
            and isinstance(response.parsed, SessionSummaryResponse)
        ):
            return response.parsed

        # Otherwise convert the response to the structured format
        if isinstance(response.content, str):
            try:
                session_summary: Optional[SessionSummaryResponse] = parse_response_model_str(  # type: ignore
                    response.content, SessionSummaryResponse
                )

                # Update RunResponse
                if session_summary is not None:
                    return session_summary
                else:
                    log_warning("Failed to convert session_summary response to SessionSummaryResponse")
            except Exception as e:
                log_warning(f"Failed to convert session_summary response to SessionSummaryResponse: {e}")

        return None

    async def arun(
        self,
        conversation: List[Message],
    ) -> Optional[SessionSummaryResponse]:
        if self.model is None:
            log_error("No model provided for summary_manager")
            return None

        log_debug("SessionSummarizer Start", center=True)

        if conversation is None or len(conversation) == 0:
            log_info("No conversation provided for summarization.")
            return None

        model_copy = deepcopy(self.model)
        self.update_model(model_copy)

        # Prepare the List of messages to send to the Model
        messages_for_model: List[Message] = [
            self.get_system_message(conversation, model=model_copy),
            # For models that require a non-system message
            Message(role="user", content="Provide the summary of the conversation."),
        ]

        # Generate a response from the Model (includes running function calls)
        response = await model_copy.aresponse(messages=messages_for_model)

        if response.content is not None:
            self.summary_updated = True

        log_debug("SessionSummarizer End", center=True)

        # If the model natively supports structured outputs, the parsed value is already in the structured format
        if (
            model_copy.supports_native_structured_outputs
            and response.parsed is not None
            and isinstance(response.parsed, SessionSummaryResponse)
        ):
            return response.parsed

        # Otherwise convert the response to the structured format
        if isinstance(response.content, str):
            try:
                session_summary: Optional[SessionSummaryResponse] = parse_response_model_str(  # type: ignore
                    response.content, SessionSummaryResponse
                )

                # Update RunResponse
                if session_summary is not None:
                    return session_summary
                else:
                    log_warning("Failed to convert session_summary response to SessionSummaryResponse")
            except Exception as e:
                log_warning(f"Failed to convert session_summary response to SessionSummaryResponse: {e}")
        return None
