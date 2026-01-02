
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple, cast

from configs import config
from runtime.generator.generator import LLMGenerator
logger=logging.getLogger(__name__)


class TaskGrader:
    """
    任务分级 Router 封装：
    - 调用 LLM 输出 JSON（任务等级 + 模型建议）
    - 保持温度足够低，保证可回归
    - 做 JSON 解析保护
    - 预留日志回流入口
    """

    @classmethod
    def grade_task(cls, prompt: str) -> Dict[str, Any]:
        """
        调用 Router LLM，对任务进行分级并返回结构化结果。

        返回结构建议：
        {
          "task_level": "L0" | "L1" | "L2" | "L3",
          "recommended_model": "gpt-5-mini",
          "router_confidence": 0.0-1.0,
          "raw_json": {...},                  # LLM 的原始 JSON 结果
          "raw_text": "<llm原文>",            # 调试用
        }
        """
        try:
            answer_text = LLMGenerator.grade_task(
                prompt=prompt)

            parsed, parsed_ok = cls._safe_parse_json(answer_text)

            if not parsed_ok:
                # 解析失败时，可以：
                # - 抛异常
                # - 或者返回一个降级结果（比如默认 L1 + 默认模型）
                # 这里示例：抛出明确错误，外层可以接住做 fallback
                raise ValueError(f"Router LLM 返回非 JSON 格式: {answer_text!r}")

            task_level = parsed.get("task_level", "L1")
            reason = parsed.get("reason")
            recommended_model = parsed.get("recommended_model")
            recommended_model_model_provider = parsed.get("recommended_model_provider")
            confidence = float(parsed.get("confidence"))
            temperature = float(parsed.get("temperature"))
            top_p = float(parsed.get("top_p"))
            weight = float(parsed.get("weight"))

            result: Dict[str, Any] = {
                "task_level": task_level,
                "recommended_model": recommended_model,
                "recommended_model_provider": recommended_model_model_provider,
                "confidence": confidence,
                "temperature": temperature,
                "top_p": top_p,
                "weight": weight,
                "raw_json": parsed,
                "raw_text": answer_text,
                "done": True,
            }
            with config.db_session() as session:
                from models import TaskGradeRecord

                record = TaskGradeRecord(
                    prompt=prompt,
                    prompt_hash=hashlib.sha512(prompt.encode("utf-8")).hexdigest(),
                    task_level=task_level,
                    reason=reason,
                    recommended_model=recommended_model,
                    recommended_model_provider=recommended_model_model_provider,
                    confidence=confidence,
                    temperature=temperature,
                    top_p=top_p,
                    weight=weight,
                    raw_json=parsed,
                    raw_text=answer_text,
                )
                session.add(record)
                session.commit()

            return result
        except Exception as e:
            logger.error(f"TaskGrader.grade_task error: {e}", exc_info=True)
            return {"done": False, "error": str(e)}

    # ---------------- 内部工具方法 ----------------

    @staticmethod
    def _safe_parse_json(text: str) -> Tuple[Dict[str, Any], bool]:
        """
        尝试从 LLM 返回中解析 JSON：
        - 直接 json.loads
        - 如包含 ```json ... ``` 包裹，则先裁剪
        """
        text = text.strip()

        # 兼容 ```json ... ``` / ``` 包裹
        if text.startswith("```"):
            # 去掉前三个 `，以及可选的语言标记
            lines = text.splitlines()
            if len(lines) >= 2:
                # 去掉首尾 ``` 块
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj, True
            else:
                return {"_raw": obj}, True
        except Exception:
            return {}, False
