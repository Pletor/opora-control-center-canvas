"""Registered, domain-owned validation of optional native result extensions."""
from backend.library.harness_documentation_reports import validate_result as validate_documentation
from backend.library.harness_invocation_reports import validate_result as validate_harness
from backend.library.harness_paired_history import validate_result as validate_pairs

VALIDATORS = (validate_harness, validate_pairs, validate_documentation)


def validate_extensions(result, record, repo):
    for validate in VALIDATORS:
        validate(result, record, repo)
