import pytest
from unittest.mock import AsyncMock

from services.custom_variable_resolver import CustomVariableResolver


def _make_resolver(
        raw_variables=None,
        action_inputs=None,
        action_parameter_names=None,
) -> CustomVariableResolver:
    return CustomVariableResolver(
        raw_variables=raw_variables or [],
        action_inputs=action_inputs or {},
        action_parameter_names=action_parameter_names or set(),
        llm_value_factory=AsyncMock(return_value="llm_result"),
        builtin_variable_provider=None,
    )


class TestParseVariableDefinitions:
    def test_normal(self):
        raw = [
            {"key": "style", "mode": "literal", "values": '["anime"]', "probability": 1.0},
        ]
        r = _make_resolver(raw_variables=raw, action_parameter_names={"prompt"})
        assert "style" in r.variable_definitions
        assert r.variable_definitions["style"].mode == "literal"
        assert r.variable_definitions["style"].values == ["anime"]

    def test_reserved_name_conflict_raises(self):
        raw = [{"key": "prompt", "mode": "literal", "values": '["x"]'}]
        with pytest.raises(ValueError, match="冲突"):
            _make_resolver(raw_variables=raw, action_parameter_names={"prompt"})

    def test_builtin_name_conflict_raises(self):
        raw = [{"key": "random_seed", "mode": "literal", "values": '["x"]'}]
        with pytest.raises(ValueError, match="冲突"):
            _make_resolver(raw_variables=raw)

    def test_duplicate_key_raises(self):
        raw = [
            {"key": "style", "mode": "literal", "values": '["a"]'},
            {"key": "style", "mode": "literal", "values": '["b"]'},
        ]
        with pytest.raises(ValueError, match="重复"):
            _make_resolver(raw_variables=raw)

    def test_invalid_mode_raises(self):
        raw = [{"key": "style", "mode": "invalid", "values": '["x"]'}]
        with pytest.raises(ValueError, match="只能是"):
            _make_resolver(raw_variables=raw)

    def test_probability_out_of_range_raises(self):
        raw = [{"key": "style", "mode": "literal", "values": '["x"]', "probability": 1.5}]
        with pytest.raises(ValueError, match="0 到 1"):
            _make_resolver(raw_variables=raw)

    def test_none_raw_variables(self):
        r = _make_resolver(raw_variables=None)
        assert r.variable_definitions == {}

    def test_empty_list(self):
        r = _make_resolver(raw_variables=[])
        assert r.variable_definitions == {}


class TestParseVariableValues:
    def test_json_list_string(self):
        raw = [{"key": "s", "mode": "literal", "values": '["a", "b"]'}]
        r = _make_resolver(raw_variables=raw)
        assert r.variable_definitions["s"].values == ["a", "b"]

    def test_native_list(self):
        raw = [{"key": "s", "mode": "literal", "values": ["x", "y"]}]
        r = _make_resolver(raw_variables=raw)
        assert r.variable_definitions["s"].values == ["x", "y"]

    def test_multiline_text(self):
        raw = [{"key": "s", "mode": "literal", "values": "line1\nline2\n"}]
        r = _make_resolver(raw_variables=raw)
        assert r.variable_definitions["s"].values == ["line1", "line2"]

    def test_none_values(self):
        raw = [{"key": "s", "mode": "literal", "values": None}]
        r = _make_resolver(raw_variables=raw)
        assert r.variable_definitions["s"].values == []


class TestCollectRequiredVariableKeys:
    def test_extracts_custom_vars_from_bindings(self):
        raw = [{"key": "ep", "mode": "literal", "values": '["x"]'}]
        r = _make_resolver(
            raw_variables=raw,
            action_parameter_names={"prompt"},
        )
        bindings = [
            {"field": "f1", "value": "{ep}", "value_type": "string"},
        ]
        keys = r.collect_required_variable_keys(bindings)
        assert keys == {"ep"}

    def test_ignores_action_params_and_builtins(self):
        raw = [{"key": "ep", "mode": "literal", "values": '["x"]'}]
        r = _make_resolver(
            raw_variables=raw,
            action_parameter_names={"prompt"},
        )
        bindings = [
            {"field": "f1", "value": "{prompt} {random_seed} {ep}", "value_type": "string"},
        ]
        keys = r.collect_required_variable_keys(bindings)
        assert keys == {"ep"}

    def test_none_bindings(self):
        r = _make_resolver()
        assert r.collect_required_variable_keys(None) == set()
