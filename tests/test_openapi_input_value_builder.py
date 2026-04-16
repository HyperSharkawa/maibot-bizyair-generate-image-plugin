import pytest

from clients.openapi_models import BizyAirOpenApiParameterBinding
from services.action_parameter_utils import ActionParameterDefinition
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

    def test_upload_field_parsed(self):
        """upload 字段应被正确解析到 binding 对象上"""
        raw = [
            {"field": "node.image", "value_type": "string", "value": "{ref_image}", "upload": True},
            {"field": "node.prompt", "value_type": "string", "value": "{prompt}"},
        ]
        bindings = BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)
        assert bindings[0].upload is True
        assert bindings[1].upload is False

    def test_upload_field_defaults_false(self):
        """未指定 upload 时默认为 False"""
        raw = [{"field": "f", "value_type": "string", "value": "x"}]
        bindings = BizyAirOpenApiInputValueBuilder.parse_parameter_bindings(raw)
        assert bindings[0].upload is False

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
    async def _build(
        self,
        bindings,
        template_context,
        action_inputs=None,
        action_parameter_names=None,
        required_action_parameters=None,
        action_parameter_definitions=None,
        builtin_placeholder_values=None,
        upload_api_key=None,
    ):
        """异步构建 input_values 的测试辅助方法"""
        return await BizyAirOpenApiInputValueBuilder.build_input_values(
            parameter_bindings=bindings,
            template_context=template_context,
            action_inputs=action_inputs or template_context,
            action_parameter_names=action_parameter_names or set(template_context.keys()),
            required_action_parameters=required_action_parameters or set(),
            action_parameter_definitions=action_parameter_definitions or {},
            builtin_placeholder_values=builtin_placeholder_values or {},
            upload_api_key=upload_api_key,
        )

    @pytest.mark.asyncio
    async def test_simple_substitution(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.prompt", value_template="{prompt}", value_type="string")]
        result = await self._build(bindings, {"prompt": "a cat"})
        assert result == {"n.prompt": "a cat"}

    @pytest.mark.asyncio
    async def test_int_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.seed", value_template="{seed}", value_type="int")]
        result = await self._build(bindings, {"seed": "42"})
        assert result == {"n.seed": 42}

    @pytest.mark.asyncio
    async def test_boolean_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.flag", value_template="{flag}", value_type="boolean")]
        result = await self._build(bindings, {"flag": "true"})
        assert result == {"n.flag": True}

    @pytest.mark.asyncio
    async def test_json_coercion(self):
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.data", value_template='[1, 2, 3]', value_type="json"
        )]
        result = await self._build(bindings, {"prompt": "cat"})
        assert result == {"n.data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_empty_value_skipped_by_default(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{missing}", value_type="string")]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "missing"},
            action_parameter_definitions={
                "missing": ActionParameterDefinition(name="missing", description="missing", required=False)
            },
        )
        assert "n.x" not in result

    @pytest.mark.asyncio
    async def test_send_if_empty_forces_inclusion(self):
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.x", value_template="{missing}", value_type="string", send_if_empty=True
        )]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "missing"},
            action_parameter_definitions={
                "missing": ActionParameterDefinition(name="missing", description="missing", required=False)
            },
        )
        assert result["n.x"] == ""

    @pytest.mark.asyncio
    async def test_builtin_placeholder_substituted(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.seed", value_template="{random_seed}", value_type="int")]
        result = await self._build(
            bindings, {"prompt": "cat"},
            builtin_placeholder_values={"{random_seed}": 12345},
        )
        assert result == {"n.seed": 12345}

    @pytest.mark.asyncio
    async def test_undefined_variable_raises(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{unknown}", value_type="string")]
        with pytest.raises(ValueError, match="unknown"):
            await self._build(bindings, {"prompt": "cat"})

    @pytest.mark.asyncio
    async def test_int_error_contains_field_and_value(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.seed", value_template="abc", value_type="int")]
        with pytest.raises(ValueError, match="n.seed"):
            await self._build(bindings, {"prompt": "cat"})

    @pytest.mark.asyncio
    async def test_boolean_error_contains_field_and_value(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.flag", value_template="not-bool", value_type="boolean")]
        with pytest.raises(ValueError, match="not-bool"):
            await self._build(bindings, {"prompt": "cat"})

    @pytest.mark.asyncio
    async def test_optional_missing_raise_error_only_when_referenced(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{aspect_ratio}", value_type="string")]
        with pytest.raises(ValueError, match="raise_error"):
            await self._build(
                bindings,
                {"prompt": "cat"},
                action_inputs={"prompt": "cat"},
                action_parameter_names={"prompt", "aspect_ratio"},
                action_parameter_definitions={
                    "aspect_ratio": ActionParameterDefinition(
                        name="aspect_ratio",
                        description="比例",
                        required=False,
                        missing_behavior="raise_error",
                    )
                },
            )

    @pytest.mark.asyncio
    async def test_optional_missing_use_default_when_referenced(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{aspect_ratio}", value_type="string")]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "aspect_ratio"},
            action_parameter_definitions={
                "aspect_ratio": ActionParameterDefinition(
                    name="aspect_ratio",
                    description="比例",
                    required=False,
                    missing_behavior="use_default",
                    default_value="1:1",
                )
            },
        )
        assert result == {"n.x": "1:1"}

    @pytest.mark.asyncio
    async def test_optional_missing_keep_placeholder_becomes_empty_when_referenced(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{aspect_ratio}", value_type="string")]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "aspect_ratio"},
            action_parameter_definitions={
                "aspect_ratio": ActionParameterDefinition(
                    name="aspect_ratio",
                    description="比例",
                    required=False,
                    missing_behavior="keep_placeholder",
                )
            },
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_required_missing_raises_when_referenced(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="{prompt}", value_type="string")]
        with pytest.raises(ValueError, match="必填参数 prompt 未填写"):
            await self._build(
                bindings,
                {"style": "anime"},
                action_inputs={"style": "anime"},
                action_parameter_names={"prompt", "style"},
                required_action_parameters={"prompt"},
                action_parameter_definitions={
                    "prompt": ActionParameterDefinition(name="prompt", description="提示词", required=True)
                },
            )

    @pytest.mark.asyncio
    async def test_optional_missing_not_referenced_does_not_raise(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="fixed", value_type="string")]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "aspect_ratio"},
            action_parameter_definitions={
                "aspect_ratio": ActionParameterDefinition(
                    name="aspect_ratio",
                    description="比例",
                    required=False,
                    missing_behavior="raise_error",
                )
            },
        )
        assert result == {"n.x": "fixed"}

    @pytest.mark.asyncio
    async def test_multiple_occurrences_of_same_missing_optional_are_all_replaced(self):
        bindings = [BizyAirOpenApiParameterBinding(field="n.x", value_template="x={a}, y={a}", value_type="string")]
        result = await self._build(
            bindings,
            {"prompt": "cat"},
            action_inputs={"prompt": "cat"},
            action_parameter_names={"prompt", "a"},
            action_parameter_definitions={
                "a": ActionParameterDefinition(name="a", description="A", required=False)
            },
        )
        assert result == {"n.x": "x=, y="}

    @pytest.mark.asyncio
    async def test_upload_true_without_api_key_raises(self):
        """upload=True 但未提供 upload_api_key 时应抛错"""
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.image", value_template="{ref}", value_type="string", upload=True
        )]
        with pytest.raises(ValueError, match="upload_api_key"):
            await self._build(
                bindings,
                {"ref": "/some/path.png"},
            )

    @pytest.mark.asyncio
    async def test_upload_true_url_passthrough(self):
        """upload=True 但值已经是 URL 时应直接透传，不调用上传"""
        bindings = [BizyAirOpenApiParameterBinding(
            field="n.image", value_template="{ref}", value_type="string", upload=True
        )]
        result = await self._build(
            bindings,
            {"ref": "https://example.com/image.png"},
            upload_api_key="test-key",
        )
        assert result == {"n.image": "https://example.com/image.png"}


class TestCollectBuiltinPlaceholderNamesFromBindings:
    def test_extracts_builtins(self):
        raw = [
            {"field": "f", "value": "{random_seed} {prompt}", "value_type": "string"},
        ]
        result = BizyAirOpenApiInputValueBuilder.collect_builtin_placeholder_names_from_bindings(raw)
        assert "random_seed" in result
        assert "prompt" not in result
