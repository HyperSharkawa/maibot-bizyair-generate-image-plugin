import pytest

from services.template_placeholder_utils import TemplatePlaceholderUtils


class TestExtractPlaceholderNames:
    def test_single_placeholder(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names("{prompt}") == ["prompt"]

    def test_multiple_placeholders(self):
        result = TemplatePlaceholderUtils.extract_placeholder_names("{prompt} and {style}")
        assert result == ["prompt", "style"]

    def test_no_placeholders(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names("hello world") == []

    def test_empty_string(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names("") == []

    def test_nested_braces_extracts_inner(self):
        # 正则 \{([^{}]+)\} 会匹配 {{not_a_var}} 中的 {not_a_var}
        result = TemplatePlaceholderUtils.extract_placeholder_names("{{not_a_var}}")
        assert result == ["not_a_var"]

    def test_whitespace_in_placeholder(self):
        result = TemplatePlaceholderUtils.extract_placeholder_names("{ prompt }")
        assert result == ["prompt"]

    def test_empty_braces_ignored(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names("{  }") == []


class TestExtractPlaceholderNamesFromAny:
    def test_string(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names_from_any("{a}") == {"a"}

    def test_list(self):
        result = TemplatePlaceholderUtils.extract_placeholder_names_from_any(["{a}", "{b}", "plain"])
        assert result == {"a", "b"}

    def test_dict(self):
        result = TemplatePlaceholderUtils.extract_placeholder_names_from_any({"k": "{x}", "k2": "{y}"})
        assert result == {"x", "y"}

    def test_nested(self):
        result = TemplatePlaceholderUtils.extract_placeholder_names_from_any([{"k": "{a}"}, "{b}"])
        assert result == {"a", "b"}

    def test_non_string_type(self):
        assert TemplatePlaceholderUtils.extract_placeholder_names_from_any(42) == set()
        assert TemplatePlaceholderUtils.extract_placeholder_names_from_any(None) == set()


class TestCollectBuiltinPlaceholderNames:
    def test_filters_builtin_only(self):
        builtins = frozenset({"random_seed", "current_datetime"})
        result = TemplatePlaceholderUtils.collect_builtin_placeholder_names(
            "{random_seed} and {prompt}", builtins
        )
        assert result == {"random_seed"}

    def test_no_builtins_found(self):
        builtins = frozenset({"random_seed"})
        result = TemplatePlaceholderUtils.collect_builtin_placeholder_names("{prompt}", builtins)
        assert result == set()


class TestCollectNonBuiltinPlaceholderNames:
    def test_filters_out_builtins(self):
        builtins = frozenset({"random_seed", "current_datetime"})
        result = TemplatePlaceholderUtils.collect_non_builtin_placeholder_names(
            "{random_seed} and {prompt} and {style}", builtins
        )
        assert result == {"prompt", "style"}

    def test_all_builtin(self):
        builtins = frozenset({"random_seed"})
        result = TemplatePlaceholderUtils.collect_non_builtin_placeholder_names("{random_seed}", builtins)
        assert result == set()

    def test_list_input(self):
        builtins = frozenset({"random_seed"})
        result = TemplatePlaceholderUtils.collect_non_builtin_placeholder_names(
            ["{random_seed}", "{prompt}"], builtins
        )
        assert result == {"prompt"}


class TestCollectCustomPlaceholderNames:
    def test_excludes_action_params_and_builtins(self):
        result = TemplatePlaceholderUtils.collect_custom_placeholder_names(
            "{prompt} {random_seed} {english_prompt}",
            action_parameter_names={"prompt"},
            builtin_names=frozenset({"random_seed"}),
        )
        assert result == {"english_prompt"}

    def test_empty_when_all_known(self):
        result = TemplatePlaceholderUtils.collect_custom_placeholder_names(
            "{prompt}",
            action_parameter_names={"prompt"},
            builtin_names=frozenset(),
        )
        assert result == set()
