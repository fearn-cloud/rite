from ipaddress import IPv4Address, AddressValueError

from .errors import ValidationError


def validate_dns_filtering_exceptions(model):
    errors = []
    seen_names = set()
    seen_ipv4_addresses = set()
    for index, exception in enumerate(model.dns_filtering_exceptions):
        path = f"inventory/dns-filtering-exceptions.yaml:exceptions[{index}]"
        name = exception.get("name")
        ipv4_address = exception.get("ipv4_address")
        if not name or not ipv4_address:
            errors.append(
                ValidationError(
                    code="malformed_dns_filtering_exception",
                    path=path,
                    message="DNS Filtering Exception requires name and ipv4_address.",
                )
            )
            continue
        if name in seen_names:
            errors.append(
                ValidationError(
                    code="duplicate_dns_filtering_exception_name",
                    path=path,
                    message=f"DNS Filtering Exception name {name!r} must be unique.",
                )
            )
        seen_names.add(name)
        if ipv4_address in seen_ipv4_addresses:
            errors.append(
                ValidationError(
                    code="duplicate_dns_filtering_exception_ipv4_address",
                    path=path,
                    message=f"DNS Filtering Exception ipv4_address {ipv4_address!r} must be unique.",
                )
            )
        seen_ipv4_addresses.add(ipv4_address)
        try:
            IPv4Address(ipv4_address)
        except (AddressValueError, TypeError, ValueError):
            errors.append(
                ValidationError(
                    code="invalid_dns_filtering_exception_ipv4_address",
                    path=path,
                    message="DNS Filtering Exception ipv4_address must be a valid IPv4 address.",
                )
            )
    return errors
