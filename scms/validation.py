"""Small request-validation helpers shared by the service modules."""
import re

from .errors import validation_error

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_unknown(data, allowed, errors):
    for name in data:
        if name not in allowed:
            errors[name] = "Unknown field."


def text(data, name, max_len, errors, required=True, strip=True):
    """Return a trimmed string, or None (recording an error) when invalid."""
    value = data.get(name)
    if value is None:
        if required:
            errors[name] = f"{name.replace('_', ' ').capitalize()} is required."
        return None
    if not isinstance(value, str):
        errors[name] = "Must be text."
        return None
    if strip:
        value = value.strip()
    if required and not value:
        errors[name] = f"{name.replace('_', ' ').capitalize()} is required."
        return None
    if len(value) > max_len:
        errors[name] = f"Must be at most {max_len} characters."
        return None
    return value


def integer(data, name, errors, minimum=None, maximum=None, required=True):
    value = data.get(name)
    if value is None:
        if required:
            errors[name] = f"{name.replace('_', ' ').capitalize()} is required."
        return None
    # bool is a subclass of int; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        errors[name] = "Must be an integer."
        return None
    if minimum is not None and value < minimum:
        errors[name] = f"Must be at least {minimum}."
        return None
    if maximum is not None and value > maximum:
        errors[name] = f"Must be at most {maximum}."
        return None
    return value


def raise_if_errors(errors):
    if errors:
        raise validation_error(errors)


def paging(args):
    """Parse ?page and ?page_size (page >= 1, page_size 1..100)."""
    errors = {}
    page = _query_int(args, "page", 1, 1, None, errors)
    page_size = _query_int(args, "page_size", 20, 1, 100, errors)
    raise_if_errors(errors)
    return page, page_size


def _query_int(args, name, default, minimum, maximum, errors):
    raw = args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        errors[name] = "Must be an integer."
        return default
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"between {minimum} and {maximum}" if maximum else f"at least {minimum}"
        errors[name] = f"Must be {bound}."
        return default
    return value
