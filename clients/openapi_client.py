from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

import httpx

from .base import BizyAirBaseClient, BizyAirImageResult, BizyAirOpenApiOutput


class BizyAirOpenApiError(Exception):
    """BizyAir OpenAPI 调用异常"""


class BizyAirOpenApiProtocolError(BizyAirOpenApiError):
    """BizyAir OpenAPI 返回结果与预期不符"""


@dataclass(frozen=True)
class BizyAirOpenApiParameterBinding:
    field: str
    value_template: Any


@dataclass
class BizyAirOpenApiResponse:
    type: str
    status: str
    request_id: str
    outputs: list[BizyAirOpenApiOutput]
    raw_data: dict[str, Any]

    @property
    def primary_image_url(self) -> str:
        if not self.outputs:
            raise BizyAirOpenApiProtocolError("outputs 为空，无法获取图片 URL")
        return self.outputs[0].object_url

    def to_image_result(self) -> BizyAirImageResult:
        return BizyAirImageResult(image_url=self.primary_image_url)


class BizyAirOpenApiClient(BizyAirBaseClient):
    """BizyAir 文生图 OpenAPI 客户端"""

    API_URL = "https://api.bizyair.cn/w/v1/webapp/task/openapi/create"
    WEB_APP_ID = 39429
    DEFAULT_RANDOM_SEED_MIN = 0
    DEFAULT_RANDOM_SEED_MAX = 2147483647

    PROMPT_KEY = "17:BizyAir_NanoBananaPro.prompt"
    ASPECT_RATIO_KEY = "17:BizyAir_NanoBananaPro.aspect_ratio"
    RESOLUTION_KEY = "17:BizyAir_NanoBananaPro.resolution"
    SEED_PLACEHOLDER = "{random_seed}"
    PROMPT_PLACEHOLDER = "{prompt}"
    ASPECT_RATIO_PLACEHOLDER = "{aspect_ratio}"
    RESOLUTION_PLACEHOLDER = "{resolution}"

    ALLOWED_ASPECT_RATIOS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"}
    ALLOWED_RESOLUTIONS = {"1K", "2K", "4K", "auto"}
    SUCCESS_STATUS = "Success"

    def __init__(
            self,
            bearer_token: str,
            api_url: str | None = None,
            web_app_id: int = WEB_APP_ID,
            timeout: float = 180.0,
            parameter_bindings: list[BizyAirOpenApiParameterBinding] | None = None,
    ) -> None:
        super().__init__(bearer_token=bearer_token, timeout=timeout)
        self.api_url = api_url or self.API_URL
        self.web_app_id = int(web_app_id)
        self.parameter_bindings = parameter_bindings or self.default_parameter_bindings()

    @classmethod
    def default_parameter_bindings(cls) -> list[BizyAirOpenApiParameterBinding]:
        return [
            BizyAirOpenApiParameterBinding(field=cls.PROMPT_KEY, value_template=cls.PROMPT_PLACEHOLDER),
            BizyAirOpenApiParameterBinding(field=cls.ASPECT_RATIO_KEY, value_template=cls.ASPECT_RATIO_PLACEHOLDER),
            BizyAirOpenApiParameterBinding(field=cls.RESOLUTION_KEY, value_template=cls.RESOLUTION_PLACEHOLDER),
        ]

    @classmethod
    def parse_parameter_bindings(cls, raw_bindings: Any) -> list[BizyAirOpenApiParameterBinding]:
        if raw_bindings is None:
            return cls.default_parameter_bindings()
        if not isinstance(raw_bindings, list) or not raw_bindings:
            raise ValueError("openapi_parameter_mappings 必须是非空列表")

        bindings: list[BizyAirOpenApiParameterBinding] = []
        for index, item in enumerate(raw_bindings):
            if not isinstance(item, dict):
                raise ValueError(f"openapi_parameter_mappings[{index}] 必须是对象")

            field = cls._require_mapping_text(item.get("field"), f"openapi_parameter_mappings[{index}].field")
            if "value" not in item:
                raise ValueError(f"openapi_parameter_mappings[{index}].value 缺失")

            bindings.append(BizyAirOpenApiParameterBinding(field=field, value_template=item.get("value")))
        return bindings

    def _validate_aspect_ratio(self, aspect_ratio: str) -> None:
        self._validate_choice(aspect_ratio, self.ALLOWED_ASPECT_RATIOS, "aspect_ratio")

    def _validate_resolution(self, resolution: str) -> None:
        self._validate_choice(resolution, self.ALLOWED_RESOLUTIONS, "resolution")

    def _build_request_payload(self, prompt: str, aspect_ratio: str, resolution: str, suppress_preview_output: bool = False) -> dict[str, Any]:
        return {
            "web_app_id": self.web_app_id,
            "suppress_preview_output": suppress_preview_output,
            "input_values": self._build_input_values(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            ),
        }

    def _build_input_values(self, prompt: str, aspect_ratio: str, resolution: str) -> dict[str, Any]:
        placeholder_values = self._build_placeholder_values(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        )
        input_values: dict[str, Any] = {}
        for binding in self.parameter_bindings:
            input_values[binding.field] = self._resolve_template_value(binding.value_template, placeholder_values)
        return input_values

    def _build_placeholder_values(self, prompt: str, aspect_ratio: str, resolution: str) -> dict[str, Any]:
        return {
            self.PROMPT_PLACEHOLDER: prompt,
            self.ASPECT_RATIO_PLACEHOLDER: aspect_ratio,
            self.RESOLUTION_PLACEHOLDER: resolution,
            self.SEED_PLACEHOLDER: self._generate_random_seed(),
        }

    def _resolve_template_value(self, value_template: Any, placeholder_values: dict[str, Any]) -> Any:
        if isinstance(value_template, str):
            stripped = value_template.strip()
            if stripped in placeholder_values:
                return placeholder_values[stripped]

            resolved = value_template
            for placeholder, value in placeholder_values.items():
                resolved = resolved.replace(placeholder, str(value))
            return resolved

        if isinstance(value_template, list):
            return [self._resolve_template_value(item, placeholder_values) for item in value_template]

        if isinstance(value_template, dict):
            return {key: self._resolve_template_value(value, placeholder_values) for key, value in value_template.items()}

        return value_template

    @classmethod
    def placeholder_reference_text(cls) -> str:
        return "\n".join([
            "支持的占位符：",
            f"- {cls.PROMPT_PLACEHOLDER}: 本次生成 prompt",
            f"- {cls.ASPECT_RATIO_PLACEHOLDER}: 本次生成 aspect_ratio",
            f"- {cls.RESOLUTION_PLACEHOLDER}: 本次生成 resolution",
            f"- {cls.SEED_PLACEHOLDER}: 随机生成的 32 位非负整数种子",
        ])

    @classmethod
    def default_parameter_mapping_config(cls) -> list[dict[str, Any]]:
        return [
            {"field": cls.PROMPT_KEY, "value": cls.PROMPT_PLACEHOLDER},
            {"field": cls.ASPECT_RATIO_KEY, "value": cls.ASPECT_RATIO_PLACEHOLDER},
            {"field": cls.RESOLUTION_KEY, "value": cls.RESOLUTION_PLACEHOLDER},
        ]

    @classmethod
    def _require_mapping_text(cls, value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{field_name} 不能为空")
        return text

    @classmethod
    def _generate_random_seed(cls) -> int:
        return random.randint(cls.DEFAULT_RANDOM_SEED_MIN, cls.DEFAULT_RANDOM_SEED_MAX)

    async def generate_image(
            self,
            prompt: str,
            aspect_ratio: str = "1:1",
            resolution: str = "1K",
            suppress_preview_output: bool = False,
    ) -> BizyAirImageResult:
        response = await self.create_task(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            suppress_preview_output=suppress_preview_output,
        )
        return response.to_image_result()

    async def create_task(
            self,
            prompt: str,
            aspect_ratio: str = "1:1",
            resolution: str = "1K",
            suppress_preview_output: bool = False,
    ) -> BizyAirOpenApiResponse:
        prompt = self._require_non_empty_text(prompt, "prompt")
        resolution = self._normalize_resolution(resolution)
        self._validate_aspect_ratio(aspect_ratio)
        self._validate_resolution(resolution)

        payload = self._build_request_payload(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            suppress_preview_output=suppress_preview_output,
        )

        headers = self._build_headers()
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            response = await client.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> BizyAirOpenApiResponse:
        if not isinstance(data, dict):
            raise BizyAirOpenApiProtocolError(f"返回结果不是 JSON object: {type(data)}")

        status = str(data.get("status", "")).strip()
        if status != self.SUCCESS_STATUS:
            raise BizyAirOpenApiError(f"OpenAPI 调用失败，status={status!r}, body={data}")

        request_id = self._require_protocol_text(data.get("request_id"), "request_id")
        response_type = self._require_protocol_text(data.get("type"), "type")

        raw_outputs = data.get("outputs")
        if not isinstance(raw_outputs, list) or not raw_outputs:
            raise BizyAirOpenApiProtocolError(f"outputs 不存在或为空: {raw_outputs}")

        outputs: list[BizyAirOpenApiOutput] = []
        for index, item in enumerate(raw_outputs):
            if not isinstance(item, dict):
                raise BizyAirOpenApiProtocolError(f"outputs[{index}] 不是 object: {item}")

            object_url = self._require_protocol_text(item.get("object_url"), f"outputs[{index}].object_url")
            try:
                object_url = self._validate_url(object_url, f"outputs[{index}].object_url")
            except ValueError as exc:
                raise BizyAirOpenApiProtocolError(str(exc)) from exc

            output_ext = self._require_protocol_text(item.get("output_ext"), f"outputs[{index}].output_ext")
            outputs.append(
                BizyAirOpenApiOutput(
                    object_url=object_url,
                    output_ext=output_ext,
                    cost_time=self._optional_int(item.get("cost_time")),
                    audit_status=self._optional_int(item.get("audit_status")),
                    error_type=self._optional_text(item.get("error_type")),
                )
            )

        return BizyAirOpenApiResponse(
            type=response_type,
            status=status,
            request_id=request_id,
            outputs=outputs,
            raw_data=data,
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise BizyAirOpenApiProtocolError(f"字段不是合法整数: {value}") from exc

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _require_protocol_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise BizyAirOpenApiProtocolError(f"{field_name} 为空")
        return text
