from typing import Any


def normalize_parameter_name(value: Any, field_name: str) -> str:
    """标准化参数名并校验不能为空"""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} 不能为空")
    return text



def is_parameter_required(value: Any, field_name: str) -> bool:
    """解析参数必填配置"""
    text = "" if value is None else str(value).strip()
    if text == "必填":
        return True
    if text in {"", "选填"}:
        return False
    raise ValueError(f"{field_name} 只能是“选填”或“必填”")



def normalize_parameter_description(value: Any, field_name: str) -> str:
    """标准化参数描述并校验不能为空"""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} 不能为空")
    return text



def build_action_parameters(raw_parameters: Any) -> tuple[dict[str, str], set[str]]:
    """根据配置构造动作参数定义与必填参数集合"""
    if not isinstance(raw_parameters, list) or not raw_parameters:
        raise ValueError("action_parameters 必须是非空列表")

    action_parameters: dict[str, str] = {}
    required_parameters: set[str] = set()
    for index, item in enumerate(raw_parameters):
        if not isinstance(item, dict):
            raise ValueError(f"action_parameters[{index}] 必须是对象")

        name = normalize_parameter_name(item.get("name"), f"action_parameters[{index}].name")
        description = normalize_parameter_description(item.get("description"), f"action_parameters[{index}].description")
        if name in action_parameters:
            raise ValueError(f"action_parameters[{index}].name 重复: {name}")

        action_parameters[name] = description
        if is_parameter_required(item.get("required", "选填"), f"action_parameters[{index}].required"):
            required_parameters.add(name)

    return action_parameters, required_parameters
