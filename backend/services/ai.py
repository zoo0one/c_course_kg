"""
AI 服务（支持本地 Ollama / 在线 OpenAI 兼容接口）
"""
import json
import logging
import os
import requests  # type: ignore[reportMissingModuleSource]
from typing import Optional, Generator, Dict, Any, Union

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个 C 语言编程教学助手，专门帮助学生学习 C 语言知识。

你的职责：
1. 解释 C 语言的概念和知识点
2. 提供代码示例和最佳实践
3. 帮助学生理解程序执行流程
4. 推荐学习路径和先修知识
5. 回答关于 C 语言的问题

回答时：
- 使用简洁清晰的语言
- 提供代码示例时用 ```c ... ``` 格式
- 如果涉及多个知识点，按逻辑顺序组织
- 鼓励学生动手实践
- 如果问题超出 C 语言范围，礼貌地说明"""

StrOrStream = Union[str, Generator[str, None, None]]

AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip().lower()
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

# 兼容旧代码（ai_router 仍在 import OLLAMA_MODEL）
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
        self.session = requests.Session()

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, stream: bool = False) -> StrOrStream:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": stream,
            "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 512},
        }
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=AI_TIMEOUT,
                stream=stream,
            )
            response.raise_for_status()
            if stream:
                return self._stream_response(response)
            return str(response.json().get("response", ""))
        except requests.Timeout:
            raise Exception("AI 响应超时，请稍后重试")
        except requests.RequestException as e:
            raise Exception(f"AI 服务错误: {str(e)}")

    def _stream_response(self, response: requests.Response) -> Generator[str, None, None]:
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    yield data["response"]


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        fallback = os.getenv("OPENAI_FALLBACK_MODELS", "")
        self.fallback_models = [m.strip() for m in fallback.split(",") if m.strip()]
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            r = self.session.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=8,
            )
            return r.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, stream: bool = False) -> StrOrStream:
        candidate_models = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_err: Optional[str] = None

        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": stream,
            }
            try:
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=AI_TIMEOUT,
                    stream=stream,
                )
                response.raise_for_status()
                self.model = model
                if stream:
                    return self._stream_response(response)
                data = response.json()
                choices = data.get("choices")
                if not isinstance(choices, list) or len(choices) == 0:
                    raise Exception(f"在线 AI 服务错误: 返回结构异常，缺少 choices。响应: {str(data)[:400]}")

                first = choices[0] if isinstance(choices[0], dict) else {}
                message = first.get("message") if isinstance(first, dict) else None
                if isinstance(message, dict):
                    content = message.get("content", "")
                    if isinstance(content, str):
                        return content

                # 兼容部分供应商把文本放在 text 字段
                text_content = first.get("text", "") if isinstance(first, dict) else ""
                if isinstance(text_content, str) and text_content:
                    return text_content

                raise Exception(f"在线 AI 服务错误: 返回结构异常，缺少 message.content。响应: {str(data)[:400]}")
            except requests.Timeout:
                last_err = "AI 响应超时，请稍后重试"
            except requests.RequestException as e:
                detail = ""
                try:
                    detail = response.text[:400]
                except Exception:
                    detail = str(e)
                last_err = detail

                unsupported = (
                    "has no provider supported" in detail
                    or "model_not_found" in detail
                    or "No such model" in detail
                    or "invalid model" in detail.lower()
                )
                if unsupported:
                    continue
                raise Exception(f"在线 AI 服务错误: {detail}")

        raise Exception(f"在线 AI 服务错误: {last_err or '未知错误'}")

    def _stream_response(self, response: requests.Response) -> Generator[str, None, None]:
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue


class AIService:
    def __init__(self) -> None:
        self.provider = AI_PROVIDER
        self.client = self._build_client(self.provider)

    def _build_client(self, provider: str):
        if provider == "openai":
            return OpenAICompatibleClient()
        return OllamaClient()

    def is_ready(self) -> bool:
        return self.client.is_available()

    @property
    def model_name(self) -> str:
        return getattr(self.client, "model", OLLAMA_MODEL)

    @property
    def provider_name(self) -> str:
        return self.provider

    def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> StrOrStream:
        return self.client.generate(self._build_prompt(message, context), stream=stream)

    def explain_kp(self, kp_name: str, kp_data: Dict[str, Any]) -> str:
        source_book = kp_data.get('source_book') or kp_data.get('source') or '未记录'
        source_page = kp_data.get('source_pages') or (f"第 {kp_data.get('source_page')} 页" if kp_data.get('source_page') else '未记录')
        prompt = f"""请详细解释 C 语言中的"{kp_name}"这个知识点。

信息：
- 章节: {kp_data.get('chapter_id', '未知')}
- 小节: {kp_data.get('section', '未知')}
- 别名: {kp_data.get('aliases', '无')}
- 来源: {source_book} {source_page}

请包括：
1. 基本概念
2. 实际应用
3. 常见错误
4. 代码示例

要求：
- 解释内容要通俗易懂
- 单独列出“来源”
- 不要虚构来源，只能基于已给出的信息整理"""
        return self.generate_text(prompt)

    def recommend_path(self, kp_name: str) -> str:
        prompt = f"""我已经学过"{kp_name}"，接下来应该学什么？

请推荐：
1. 3-5 个相关的后续知识点
2. 学习顺序
3. 为什么这样安排
4. 每个知识点的学习重点"""
        return self.generate_text(prompt)

    def code_review(self, code: str) -> str:
        prompt = f"""请审查以下 C 语言代码：

```c
{code}
```

请分析：
1. 代码的功能
2. 是否有问题或改进空间
3. 涉及的知识点"""
        return self.generate_text(prompt)

    def generate_text(self, prompt: str) -> str:
        result = self.client.generate(prompt, stream=False)
        return result if isinstance(result, str) else ""

    def _build_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        prompt = message
        if context:
            if context.get("related_kps"):
                prompt += f"\n\n相关知识点: {', '.join(context['related_kps'])}"
            if context.get("chapter"):
                prompt += f"\n当前章节: {context['chapter']}"
        return prompt


ai_service = AIService()
