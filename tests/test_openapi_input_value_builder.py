import pytest

from clients.openapi_models import BizyAirOpenApiParameterBinding
from services.openapi_input_value_builder import BizyAirOpenApiInputValueBuilder


class TestParseParameterBindings:
    def test_normal(self):
        raw = [
            {"field": "node.prompt", "value_type": "string", "value": "{prompt}"},
            {"field": "node.seed", "value_type": "int", "value": "{random_seed}", "send_if_empty": True},
        ]
        bindings = BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)
        assert len(bindings) == 2
        assert bindings[0].field == "node.prompt"
        assert bindings[0].value_type == "string"
        assert bindings[1].send_if_empty is True

    def test_none_returns_empty(self):
        assert BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(None) == []

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="必须是非空列表"):
            BizyAirOpenApiInputValueBuilder.parse_parameter_bindings([])

    def test_missing_field_raises(self):
        raw = [{"value_type": "string", "value": "x"}]
        with pytest.raises(ValueError, match="field"):
            BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)

    def test_missing_value_raises(self):
        raw = [{"field": "f", "value_type": "string"}]
        with pytest.raises(ValueError, match="value 缺失"):
            BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)

    def test_invalid_value_type_raises(self):
        raw = [{"field": "f", "value_type": "float", "value": "1.0"}]
        with pytest.raises(ValueError, match="不支持"):
            BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)


class TestBuildInputValues:
    def _build(self, bindings, template_context, action_inputs=None, action_parameter_names=None,
               required_action_parameters=None, builtin_placeholder_values=None):
        return BizyAirOpenApiInputValueBuilder.build_input_values(
            parameter_bindings=bindings,
            template_context=template_context,
            action_inputs=action_inputs or template_context,
            action_parameter_names=action_parameter_names or set(template_context.keys()),
            required_action_parameters=required_action_parameters or set(),
            builtin_placeholder_values=builtin_placeholder_values or {},
        )

    def test_simple_substitution(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.prompt", value_template="{prompt}", value_type="string")]
        result = self._build(bindings, {"prompt": "a cat"})
        assert result == {"n.prompt": "a cat"}

    def test_int_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.seed", value_template="{seed}", value_type="int")]
        result = self._build(bindings, {"seed": "42"})
        assert result == {"n.seed": 42}

    def test_boolean_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.flag", value_template="{flag}", value_type="boolean")]
        result = self._build(bindings, {"flag": "true"})
        assert result == {"n.flag": True}

    def test_json_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.data", value_template='[1, 2, 3]', value_type="json"
        )]
        result = self._build(bindings, {"prompt": "cat"})
        assert result == {"n.data": [1, 2, 3]}

    def test_empty_value_skipped_by_default(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{missing}", value_type="string")]
        result = self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "missing"},
        )
        assert "n.x" not in result

    def test_send_if_empty_forces_inclusion(self):
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.x", value_template="{missing}", value_type="string", send_if_empty=True
        )]
        result = self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "missing"},
        )
        assert result["n.x"] == ""

    def test_builtin_placeholder_substituted(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.seed", value_template="{random_seed}", value_type="int")]
        result = self._build(
            bindings, {"prompt": "cat"},
            builtin_placeholder_values={"{random_seed}": 12345},
        )
        assert result == {"n.seed": 12345}

    def test_undefined_variable_raises(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{unknown}", value_type="string")]
        with pytest.raises(ValueError, match="未定义的变量"):
            self._build(bindings, {"prompt": "cat"})


class TestCollectBuiltinPlaceholderNamesFromBindings:
    def test_extracts_builtins(self):
        raw = [
            {"field": "f", "value": "{random_seed} {prompt}", "value_type": "string"},
        ]
        result = BizyAirOpenApiInputValueBuilder.collect_builtin_placeholder_names_from_bindings(raw)
        assert "random_seed" in result
        assert "prompt" not in result
