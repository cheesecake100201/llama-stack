# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import warnings
from typing import AsyncIterator, List, Optional, Union

import groq
from groq import Groq

from llama_stack.apis.inference import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseStreamChunk,
    CompletionResponse,
    CompletionResponseStreamChunk,
    EmbeddingsResponse,
    EmbeddingTaskType,
    Inference,
    InterleavedContent,
    InterleavedContentItem,
    LogProbConfig,
    Message,
    ResponseFormat,
    TextTruncation,
    ToolChoice,
    ToolConfig,
)
from llama_stack.distribution.request_headers import NeedsRequestProviderData
from llama_stack.models.llama.datatypes import SamplingParams, ToolDefinition, ToolPromptFormat
from llama_stack.providers.remote.inference.groq.config import GroqConfig
from llama_stack.providers.utils.inference.model_registry import (
    ModelRegistryHelper,
)

from .groq_utils import (
    convert_chat_completion_request,
    convert_chat_completion_response,
    convert_chat_completion_response_stream,
)
from .models import _MODEL_ENTRIES


class GroqInferenceAdapter(Inference, ModelRegistryHelper, NeedsRequestProviderData):
    _config: GroqConfig

    def __init__(self, config: GroqConfig):
        ModelRegistryHelper.__init__(self, model_entries=_MODEL_ENTRIES)
        self._config = config

    def completion(
        self,
        model_id: str,
        content: InterleavedContent,
        sampling_params: Optional[SamplingParams] = SamplingParams(),
        response_format: Optional[ResponseFormat] = None,
        stream: Optional[bool] = False,
        logprobs: Optional[LogProbConfig] = None,
    ) -> Union[CompletionResponse, AsyncIterator[CompletionResponseStreamChunk]]:
        # Groq doesn't support non-chat completion as of time of writing
        raise NotImplementedError()

    async def chat_completion(
        self,
        model_id: str,
        messages: List[Message],
        sampling_params: Optional[SamplingParams] = SamplingParams(),
        response_format: Optional[ResponseFormat] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = ToolChoice.auto,
        tool_prompt_format: Optional[ToolPromptFormat] = None,
        stream: Optional[bool] = False,
        logprobs: Optional[LogProbConfig] = None,
        tool_config: Optional[ToolConfig] = None,
    ) -> Union[ChatCompletionResponse, AsyncIterator[ChatCompletionResponseStreamChunk]]:
        model_id = self.get_provider_model_id(model_id)
        if model_id == "llama-3.2-3b-preview":
            warnings.warn(
                "Groq only contains a preview version for llama-3.2-3b-instruct. "
                "Preview models aren't recommended for production use. "
                "They can be discontinued on short notice."
                "More details: https://console.groq.com/docs/models"
            )

        request = convert_chat_completion_request(
            request=ChatCompletionRequest(
                model=model_id,
                messages=messages,
                sampling_params=sampling_params,
                response_format=response_format,
                tools=tools,
                stream=stream,
                logprobs=logprobs,
                tool_config=tool_config,
            )
        )

        try:
            response = self._get_client().chat.completions.create(**request)
        except groq.BadRequestError as e:
            if e.body.get("error", {}).get("code") == "tool_use_failed":
                # For smaller models, Groq may fail to call a tool even when the request is well formed
                raise ValueError("Groq failed to call a tool", e.body.get("error", {})) from e
            else:
                raise e

        if stream:
            return convert_chat_completion_response_stream(response)
        else:
            return convert_chat_completion_response(response)

    async def embeddings(
        self,
        model_id: str,
        contents: List[str] | List[InterleavedContentItem],
        text_truncation: Optional[TextTruncation] = TextTruncation.none,
        output_dimension: Optional[int] = None,
        task_type: Optional[EmbeddingTaskType] = None,
    ) -> EmbeddingsResponse:
        raise NotImplementedError()

    def _get_client(self) -> Groq:
        if self._config.api_key is not None:
            return Groq(api_key=self._config.api_key)
        else:
            provider_data = self.get_request_provider_data()
            if provider_data is None or not provider_data.groq_api_key:
                raise ValueError(
                    'Pass Groq API Key in the header X-LlamaStack-Provider-Data as { "groq_api_key": "<your api key>" }'
                )
            return Groq(api_key=provider_data.groq_api_key)
