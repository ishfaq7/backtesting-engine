import pytest

from btengine.data.errors import InvalidResponseError
from btengine.data.validation import coerce_float, ensure_list_of_dicts, require_fields


def test_ensure_list_of_dicts_accepts_valid_list() -> None:
    data = [{"a": 1}, {"a": 2}]
    assert ensure_list_of_dicts(data, endpoint="/x") == data


def test_ensure_list_of_dicts_rejects_none() -> None:
    with pytest.raises(InvalidResponseError):
        ensure_list_of_dicts(None, endpoint="/x")


def test_ensure_list_of_dicts_rejects_non_list() -> None:
    with pytest.raises(InvalidResponseError):
        ensure_list_of_dicts({"a": 1}, endpoint="/x")


def test_ensure_list_of_dicts_rejects_non_dict_items() -> None:
    with pytest.raises(InvalidResponseError):
        ensure_list_of_dicts([{"a": 1}, "not a dict"], endpoint="/x")


def test_require_fields_passes_when_present() -> None:
    require_fields({"a": 1, "b": 2}, ["a", "b"], endpoint="/x")


def test_require_fields_raises_when_missing() -> None:
    with pytest.raises(InvalidResponseError) as exc_info:
        require_fields({"a": 1}, ["a", "b"], endpoint="/x")
    assert "b" in str(exc_info.value)


@pytest.mark.parametrize("value, expected", [(1, 1.0), ("2.5", 2.5), (3.0, 3.0)])
def test_coerce_float_converts_numeric_values(value: object, expected: float) -> None:
    assert coerce_float({"f": value}, "f", endpoint="/x") == expected


def test_coerce_float_rejects_non_numeric() -> None:
    with pytest.raises(InvalidResponseError):
        coerce_float({"f": "not-a-number"}, "f", endpoint="/x")


def test_coerce_float_rejects_missing_field() -> None:
    with pytest.raises(InvalidResponseError):
        coerce_float({}, "f", endpoint="/x")
