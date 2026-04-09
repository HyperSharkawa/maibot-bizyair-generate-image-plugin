import pytest

from services.action_parameter_utils import (
    build_action_parameters,
    is_parameter_required,
    normalize_parameter,
)


class TestNormalizeParameter:
    def test_normal(self):
        assert normalize_parameter("prompt", "f") == "prompt"

    def test_strips_whitespace(self):
        assert normalize_parameter("  prompt  ", "f") == "prompt"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            normalize_parameter("", "field")

    def test_none_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            normalize_parameter(None, "field")


class TestIsParameterRequired:
    def test_required(self):
        assert is_parameter_required("必填", "f") is True

    def test_optional_explicit(self):
        assert is_parameter_required("选填", "f") is False

    def test_optional_empty(self):
        assert is_parameter_required("", "f") is False

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="只能是"):
            is_parameter_required("maybe", "f")


class TestBuildActionParameters:
    def test_normal(self):
        raw = [
            {"name": "prompt", "description": "描述词", "required": "必填"},
            {"name": "style", "description": "风格", "required": "选填"},
        ]
        params, required = build_action_parameters(raw)
        assert params == {"prompt": "描述词", "style": "风格"}
        assert required == {"prompt"}

    def test_duplicate_name_raises(self):
        raw = [
            {"name": "prompt", "description": "d1"},
            {"name": "prompt", "description": "d2"},
        ]
        with pytest.raises(ValueError, match="重复"):
            build_action_parameters(raw)

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="必须是非空列表"):
            build_action_parameters([])

    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="必须是非空列表"):
            build_action_parameters("not a list")

    def test_non_dict_item_raises(self):
        with pytest.raises(ValueError, match="必须是对象"):
            build_action_parameters(["not a dict"])

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            build_action_parameters([{"description": "d"}])

    def test_default_required_is_optional(self):
        raw = [{"name": "x", "description": "d"}]
        params, required = build_action_parameters(raw)
        assert "x" in params
        assert required == set()
