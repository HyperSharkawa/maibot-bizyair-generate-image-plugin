from __future__ import annotations

import json
import random
import re
from typing import Any

from ..clients import BizyAirOpenApiParameterBinding


class BizyAirOpenApiInputValueBuilder:
    """负责将 action/context/config 组装为 OpenAPI input_values"""

    PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")
    DEFAULT_RANDOM_SEED_MIN = 0
    DEFAULT_RANDOM_SEED_MAX = 2147483647
    SEED_PLACEHOLDER = "{random_seed}"
    BUILTIN_PLACEHOLDER_NAMES = frozenset({"random_seed"})

    @classmethod
    def parse_parameter_bindings(cls, raw_bindings: Any) -> list[BizyAirOpenApiParameterBinding]:
        """解析并校验参数映射配置"""
        if raw_bindings is None:
            return []
        if not isinstance(raw_bindings, list) or not raw_bindings:
            raise ValueError("openapi_parameter_mappings 必须是非空列表")

        bindings: list[BizyAirOpenApiParameterBinding] = []
        for index, item in enumerate(raw_bindings):
            if not isinstance(item, dict):
                raise ValueError(f"openapi_parameter_mappings[{index}] 必须是对象")

            field = cls._require_mapping_text(item.get("field"), f"openapi_parameter_mappings[{index}].field")
            if "value" not in item:
                raise ValueError(f"openapi_parameter_mappings[{index}].value 缺失")
            value_type = cls._require_mapping_text(item.get("value_type", "string"), f"openapi_parameter_mappings[{index}].value_type").lower()
            value_template = cls._coerce_mapping_value(item.get("value"), value_type, f"openapi_parameter_mappings[{index}].value")
            send_if_empty = bool(item.get("send_if_empty", False))

            bindings.append(BizyAirOpenApiParameterBinding(
                field=field,
                value_template=value_template,
                value_type=value_type,
                send_if_empty=send_if_empty,
            ))
        return bindings

    @classmethod
    def build_input_values(
            cls,
            parameter_bindings: list[BizyAirOpenApiParameterBinding],
            template_context: dict[str, Any],
            action_inputs: dict[str, Any],
            action_parameter_names: set[str],
            required_action_parameters: set[str],
            builtin_placeholder_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """根据映射规则构造 input_values"""
        if not isinstance(template_context, dict) or not template_context:
            raise ValueError("template_context 必须是非空对象")

        placeholder_values = cls._build_placeholder_values(
            template_context,
            builtin_placeholder_values=builtin_placeholder_values,
        )
        input_values: dict[str, Any] = {}
        for binding in parameter_bindings:
            resolved_value = cls._resolve_template_value(
                binding.value_template,
                placeholder_values,
                action_inputs=action_inputs,
                action_parameter_names=action_parameter_names,
                required_action_parameters=required_action_parameters,
            )
            if not binding.send_if_empty and cls._is_empty_mapping_value(resolved_value):
                continue
            input_values[binding.field] = resolved_value
        return input_values

    @classmethod
    def resolve_template_value_static(
            cls,
            value_template: Any,
            template_context: dict[str, Any],
            builtin_placeholder_values: dict[str, Any] | None = None,
    ) -> Any:
        """基于模板上下文静态解析模板值"""
        placeholder_values = cls._build_placeholder_values(
            template_context,
            builtin_placeholder_values=builtin_placeholder_values,
        )
        return cls._resolve_template_value_static(value_template, placeholder_values)

    @classmethod
    def build_builtin_placeholder_values(cls) -> dict[str, Any]:
        """构造当前执行周期可复用的内置变量值"""
        return {
            cls.SEED_PLACEHOLDER: cls._generate_random_seed(),
        }

    @classmethod
    def _build_placeholder_values(
            cls,
            template_context: dict[str, Any],
            builtin_placeholder_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造占位符到实际值的映射表"""
        placeholder_values = dict(builtin_placeholder_values or cls.build_builtin_placeholder_values())
        for key, value in template_context.items():
            placeholder_values[f"{{{key}}}"] = value
        return placeholder_values

    @classmethod
    def _resolve_template_value_static(cls, value_template: Any, placeholder_values: dict[str, Any]) -> Any:
        """静态递归解析模板值中的占位符"""
        if isinstance(value_template, str):
            stripped = value_template.strip()
            if stripped in placeholder_values:
                return placeholder_values[stripped]

            resolved = value_template
            for placeholder, value in placeholder_values.items():
                resolved = resolved.replace(placeholder, str(value))
            return resolved

        if isinstance(value_template, list):
            return [cls._resolve_template_value_static(item, placeholder_values) for item in value_template]

        if isinstance(value_template, dict):
            return {key: cls._resolve_template_value_static(value, placeholder_values) for key, value in value_template.items()}

        return value_template

    @classmethod
    def _resolve_template_value(
            cls,
            value_template: Any,
            placeholder_values: dict[str, Any],
            action_inputs: dict[str, Any],
            action_parameter_names: set[str],
            required_action_parameters: set[str],
    ) -> Any:
        """递归解析模板值中的占位符"""
        if isinstance(value_template, str):
            stripped = value_template.strip()
            if stripped in placeholder_values:
                return placeholder_values[stripped]

            resolved = value_template
            for placeholder, value in placeholder_values.items():
                resolved = resolved.replace(placeholder, str(value))
            return cls._resolve_remaining_placeholders(
                resolved,
                action_inputs=action_inputs,
                action_parameter_names=action_parameter_names,
                required_action_parameters=required_action_parameters,
            )

        if isinstance(value_template, list):
            return [
                cls._resolve_template_value(
                    item,
                    placeholder_values,
                    action_inputs=action_inputs,
                    action_parameter_names=action_parameter_names,
                    required_action_parameters=required_action_parameters,
                )
                for item in value_template
            ]

        if isinstance(value_template, dict):
            return {
                key: cls._resolve_template_value(
                    value,
                    placeholder_values,
                    action_inputs=action_inputs,
                    action_parameter_names=action_parameter_names,
                    required_action_parameters=required_action_parameters,
                )
                for key, value in value_template.items()
            }

        return value_template

    @classmethod
    def _resolve_remaining_placeholders(
            cls,
            resolved_text: str,
            action_inputs: dict[str, Any],
            action_parameter_names: set[str],
            required_action_parameters: set[str],
    ) -> str:
        """处理替换后仍残留的占位符"""
        result = resolved_text
        for placeholder_name in cls._extract_placeholder_names(resolved_text):
            if (
                    placeholder_name in action_parameter_names
                    and placeholder_name not in required_action_parameters
                    and placeholder_name not in action_inputs
            ):
                result = result.replace(f"{{{placeholder_name}}}", "")
                continue
            raise ValueError(f"模板中引用了未定义的变量: {placeholder_name}")
        return result

    @classmethod
    def _extract_placeholder_names(cls, value: str) -> list[str]:
        """提取字符串中的占位符名称"""
        return [match.group(1).strip() for match in cls.PLACEHOLDER_PATTERN.finditer(value) if match.group(1).strip()]

    @classmethod
    def _is_empty_mapping_value(cls, value: Any) -> bool:
        """判断映射结果是否为空值"""
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    @classmethod
    def _coerce_mapping_value(cls, value: Any, value_type: str, field_name: str) -> Any:
        """按声明类型强制转换映射值"""
        if value_type == "string":
            if value is None:
                return ""
            return str(value)

        raw_text = "" if value is None else str(value).strip()

        if value_type == "int":
            try:
                return int(raw_text)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field_name} 不是合法整数: {value}") from exc

        if value_type == "boolean":
            normalized = raw_text.lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            raise ValueError(f"{field_name} 不是合法布尔值: {value}")

        if value_type == "json":
            if not raw_text:
                raise ValueError(f"{field_name} 不能为空")
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{field_name} 不是合法 JSON: {value}") from exc

        raise ValueError(f"{field_name} 的类型不支持: {value_type}")

    @classmethod
    def _require_mapping_text(cls, value: Any, field_name: str) -> str:
        """校验映射字段文本非空"""
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{field_name} 不能为空")
        return text

    @classmethod
    def _generate_random_seed(cls) -> int:
        """生成随机种子值"""
        return random.randint(cls.DEFAULT_RANDOM_SEED_MIN, cls.DEFAULT_RANDOM_SEED_MAX)
