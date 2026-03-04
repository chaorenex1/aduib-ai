TOOL_PREDICTION_PROMPT = """\
You are an expert tool-call predictor. Given the user message and the available tool schemas, \
predict which tool calls the LLM will likely make next.

## Available Tools
{tool_schemas}

## Conversation Context
{conversation_context}

## Instructions
- Only predict read-only tools (side_effect=false).
- Output a JSON array of predicted calls, each with "tool_name" and "parameters".
- Maximum {max_predictions} predictions.
- Only predict tools you are >={confidence_threshold} confident about.
- If no confident prediction, output an empty array [].

## Output Format
```json
[
  {{"tool_name": "...", "parameters": {{...}}}}
]
```"""

SUFFICIENCY_EVALUATION_PROMPT = """\
You are evaluating whether cached tool results are sufficient to answer the user query \
without additional tool calls.

## User Message
{user_message}

## Cached Results
{cached_results}

## Instructions
- If the cached results fully answer the query, output {{"sufficient": true}}.
- If more tool calls are needed, output {{"sufficient": false, "reason": "..."}}.
- Be conservative: if uncertain, output false.

## Output Format
```json
{{"sufficient": true/false, "reason": "..."}}
```"""
