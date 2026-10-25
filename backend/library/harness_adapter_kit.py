"""Optional full v2 validation shared by native observation consumers."""
from importlib import import_module


def _unavailable():
    raise ValueError("Accepted Harness kit v2 validation is unavailable.")


def validate_adapter_kit(kit):
    if not isinstance(kit, dict):
        return _unavailable()
    schema = kit.get("schema")
    if schema == "harness.kit/1":
        return  # Existing consumers retain their v1 checks.
    if schema != "harness.kit/2":
        raise ValueError("Unsupported accepted Harness kit schema.")
    try:
        validate = import_module("backend.library.harness_kit").validate_kit
    except (ImportError, AttributeError) as error:
        raise ValueError("Accepted Harness kit v2 validation is unavailable.") from error
    if not callable(validate):
        return _unavailable()
    validate(kit)  # Never strip provenance to satisfy an older validator.
