# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

import pytest
from pydantic import BaseModel

from llama_stack.providers.tests.test_cases.test_case import TestCase

PROVIDER_TOOL_PROMPT_FORMAT = {
    "remote::ollama": "json",
    "remote::together": "json",
    "remote::fireworks": "json",
    "remote::vllm": "json",
}

PROVIDER_LOGPROBS_TOP_K = {"remote::together", "remote::fireworks", "remote::vllm"}


def skip_if_model_doesnt_support_completion(client_with_models, model_id):
    models = {m.identifier: m for m in client_with_models.models.list()}
    provider_id = models[model_id].provider_id
    providers = {p.provider_id: p for p in client_with_models.providers.list()}
    provider = providers[provider_id]
    print(f"Provider: {provider.provider_type} for model {model_id}")
    if provider.provider_type in ("remote::openai", "remote::anthropic", "remote::gemini"):
        pytest.skip(f"Model {model_id} hosted by {provider.provider_type} doesn't support completion")


@pytest.fixture(scope="session")
def provider_tool_format(inference_provider_type):
    return (
        PROVIDER_TOOL_PROMPT_FORMAT[inference_provider_type]
        if inference_provider_type in PROVIDER_TOOL_PROMPT_FORMAT
        else None
    )


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:completion:sanity",
    ],
)
def test_text_completion_non_streaming(client_with_models, text_model_id, test_case):
    skip_if_model_doesnt_support_completion(client_with_models, text_model_id)
    tc = TestCase(test_case)

    response = client_with_models.inference.completion(
        content=tc["content"],
        stream=False,
        model_id=text_model_id,
        sampling_params={
            "max_tokens": 50,
        },
    )
    assert len(response.content) > 10
    # assert "blue" in response.content.lower().strip()


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:completion:sanity",
    ],
)
def test_text_completion_streaming(client_with_models, text_model_id, test_case):
    skip_if_model_doesnt_support_completion(client_with_models, text_model_id)
    tc = TestCase(test_case)

    response = client_with_models.inference.completion(
        content=tc["content"],
        stream=True,
        model_id=text_model_id,
        sampling_params={
            "max_tokens": 50,
        },
    )
    streamed_content = [chunk.delta for chunk in response]
    content_str = "".join(streamed_content).lower().strip()
    # assert "blue" in content_str
    assert len(content_str) > 10


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:completion:log_probs",
    ],
)
def test_text_completion_log_probs_non_streaming(client_with_models, text_model_id, inference_provider_type, test_case):
    skip_if_model_doesnt_support_completion(client_with_models, text_model_id)
    if inference_provider_type not in PROVIDER_LOGPROBS_TOP_K:
        pytest.xfail(f"{inference_provider_type} doesn't support log probs yet")

    tc = TestCase(test_case)

    response = client_with_models.inference.completion(
        content=tc["content"],
        stream=False,
        model_id=text_model_id,
        sampling_params={
            "max_tokens": 5,
        },
        logprobs={
            "top_k": 1,
        },
    )
    assert response.logprobs, "Logprobs should not be empty"
    assert 1 <= len(response.logprobs) <= 5  # each token has 1 logprob and here max_tokens=5
    assert all(len(logprob.logprobs_by_token) == 1 for logprob in response.logprobs)


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:completion:log_probs",
    ],
)
def test_text_completion_log_probs_streaming(client_with_models, text_model_id, inference_provider_type, test_case):
    skip_if_model_doesnt_support_completion(client_with_models, text_model_id)
    if inference_provider_type not in PROVIDER_LOGPROBS_TOP_K:
        pytest.xfail(f"{inference_provider_type} doesn't support log probs yet")

    tc = TestCase(test_case)

    response = client_with_models.inference.completion(
        content=tc["content"],
        stream=True,
        model_id=text_model_id,
        sampling_params={
            "max_tokens": 5,
        },
        logprobs={
            "top_k": 1,
        },
    )
    streamed_content = [chunk for chunk in response]
    for chunk in streamed_content:
        if chunk.delta:  # if there's a token, we expect logprobs
            assert chunk.logprobs, "Logprobs should not be empty"
            assert all(len(logprob.logprobs_by_token) == 1 for logprob in chunk.logprobs)
        else:  # no token, no logprobs
            assert not chunk.logprobs, "Logprobs should be empty"


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:completion:structured_output",
    ],
)
def test_text_completion_structured_output(client_with_models, text_model_id, test_case):
    skip_if_model_doesnt_support_completion(client_with_models, text_model_id)

    class AnswerFormat(BaseModel):
        name: str
        year_born: str
        year_retired: str

    tc = TestCase(test_case)

    user_input = tc["user_input"]
    response = client_with_models.inference.completion(
        model_id=text_model_id,
        content=user_input,
        stream=False,
        sampling_params={
            "max_tokens": 50,
        },
        response_format={
            "type": "json_schema",
            "json_schema": AnswerFormat.model_json_schema(),
        },
    )
    answer = AnswerFormat.model_validate_json(response.content)
    expected = tc["expected"]
    assert answer.name == expected["name"]
    assert answer.year_born == expected["year_born"]
    assert answer.year_retired == expected["year_retired"]


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:non_streaming_01",
        "inference:chat_completion:non_streaming_02",
    ],
)
def test_text_chat_completion_non_streaming(client_with_models, text_model_id, test_case):
    tc = TestCase(test_case)
    question = tc["question"]
    expected = tc["expected"]

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=[
            {
                "role": "user",
                "content": question,
            }
        ],
        stream=False,
    )
    message_content = response.completion_message.content.lower().strip()
    assert len(message_content) > 0
    assert expected.lower() in message_content


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:streaming_01",
        "inference:chat_completion:streaming_02",
    ],
)
def test_text_chat_completion_streaming(client_with_models, text_model_id, test_case):
    tc = TestCase(test_case)
    question = tc["question"]
    expected = tc["expected"]

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=[{"role": "user", "content": question}],
        stream=True,
    )
    streamed_content = [str(chunk.event.delta.text.lower().strip()) for chunk in response]
    assert len(streamed_content) > 0
    assert expected.lower() in "".join(streamed_content)


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:tool_calling",
    ],
)
def test_text_chat_completion_with_tool_calling_and_non_streaming(
    client_with_models, text_model_id, provider_tool_format, test_case
):
    # TODO: more dynamic lookup on tool_prompt_format for model family
    tool_prompt_format = "json" if "3.1" in text_model_id else "python_list"

    tc = TestCase(test_case)

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=tc["messages"],
        tools=tc["tools"],
        tool_choice="auto",
        tool_prompt_format=tool_prompt_format,
        stream=False,
    )
    # some models can return content for the response in addition to the tool call
    assert response.completion_message.role == "assistant"

    assert len(response.completion_message.tool_calls) == 1
    assert response.completion_message.tool_calls[0].tool_name == tc["tools"][0]["tool_name"]
    assert response.completion_message.tool_calls[0].arguments == tc["expected"]


# Will extract streamed text and separate it from tool invocation content
# The returned tool inovcation content will be a string so it's easy to comapare with expected value
# e.g. "[get_weather, {'location': 'San Francisco, CA'}]"
def extract_tool_invocation_content(response):
    tool_invocation_content: str = ""
    for chunk in response:
        delta = chunk.event.delta
        if delta.type == "tool_call" and delta.parse_status == "succeeded":
            call = delta.tool_call
            tool_invocation_content += f"[{call.tool_name}, {call.arguments}]"
    return tool_invocation_content


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:tool_calling",
    ],
)
def test_text_chat_completion_with_tool_calling_and_streaming(
    client_with_models, text_model_id, provider_tool_format, test_case
):
    # TODO: more dynamic lookup on tool_prompt_format for model family
    tool_prompt_format = "json" if "3.1" in text_model_id else "python_list"

    tc = TestCase(test_case)

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=tc["messages"],
        tools=tc["tools"],
        tool_choice="auto",
        tool_prompt_format=tool_prompt_format,
        stream=True,
    )
    tool_invocation_content = extract_tool_invocation_content(response)
    expected_tool_name = tc["tools"][0]["tool_name"]
    expected_argument = tc["expected"]
    assert tool_invocation_content == f"[{expected_tool_name}, {expected_argument}]"


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:tool_calling",
    ],
)
def test_text_chat_completion_with_tool_choice_required(
    client_with_models,
    text_model_id,
    provider_tool_format,
    test_case,
):
    # TODO: more dynamic lookup on tool_prompt_format for model family
    tool_prompt_format = "json" if "3.1" in text_model_id else "python_list"

    tc = TestCase(test_case)

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=tc["messages"],
        tools=tc["tools"],
        tool_config={
            "tool_choice": "required",
            "tool_prompt_format": tool_prompt_format,
        },
        stream=True,
    )
    tool_invocation_content = extract_tool_invocation_content(response)
    expected_tool_name = tc["tools"][0]["tool_name"]
    expected_argument = tc["expected"]
    assert tool_invocation_content == f"[{expected_tool_name}, {expected_argument}]"


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:tool_calling",
    ],
)
def test_text_chat_completion_with_tool_choice_none(client_with_models, text_model_id, provider_tool_format, test_case):
    tc = TestCase(test_case)

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=tc["messages"],
        tools=tc["tools"],
        tool_config={"tool_choice": "none", "tool_prompt_format": provider_tool_format},
        stream=True,
    )
    tool_invocation_content = extract_tool_invocation_content(response)
    assert tool_invocation_content == ""


@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:structured_output",
    ],
)
def test_text_chat_completion_structured_output(client_with_models, text_model_id, test_case):
    class AnswerFormat(BaseModel):
        first_name: str
        last_name: str
        year_of_birth: int
        num_seasons_in_nba: int

    tc = TestCase(test_case)

    response = client_with_models.inference.chat_completion(
        model_id=text_model_id,
        messages=tc["messages"],
        response_format={
            "type": "json_schema",
            "json_schema": AnswerFormat.model_json_schema(),
        },
        stream=False,
    )
    answer = AnswerFormat.model_validate_json(response.completion_message.content)
    expected = tc["expected"]
    assert answer.first_name == expected["first_name"]
    assert answer.last_name == expected["last_name"]
    assert answer.year_of_birth == expected["year_of_birth"]
    assert answer.num_seasons_in_nba == expected["num_seasons_in_nba"]


@pytest.mark.parametrize("streaming", [True, False])
@pytest.mark.parametrize(
    "test_case",
    [
        "inference:chat_completion:tool_calling_tools_absent",
    ],
)
def test_text_chat_completion_tool_calling_tools_not_in_request(
    client_with_models, text_model_id, test_case, streaming
):
    tc = TestCase(test_case)

    # TODO: more dynamic lookup on tool_prompt_format for model family
    tool_prompt_format = "json" if "3.1" in text_model_id else "python_list"
    request = {
        "model_id": text_model_id,
        "messages": tc["messages"],
        "tools": tc["tools"],
        "tool_choice": "auto",
        "tool_prompt_format": tool_prompt_format,
        "stream": streaming,
    }

    response = client_with_models.inference.chat_completion(**request)

    if streaming:
        for chunk in response:
            delta = chunk.event.delta
            if delta.type == "tool_call" and delta.parse_status == "succeeded":
                assert delta.tool_call.tool_name == "get_object_namespace_list"
            if delta.type == "tool_call" and delta.parse_status == "failed":
                # expect raw message that failed to parse in tool_call
                assert type(delta.tool_call) == str
                assert len(delta.tool_call) > 0
    else:
        for tc in response.completion_message.tool_calls:
            assert tc.tool_name == "get_object_namespace_list"
