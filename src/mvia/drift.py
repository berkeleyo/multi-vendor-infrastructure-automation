"""Desired-state comparison."""

from typing import Any

from mvia.models import DriftItem, DriftReport, Inventory, ProviderName, Resource


def _key(resource: Resource) -> str:
    return f"{resource.provider}/{resource.kind}/{resource.id}"


def _configuration(resource: Resource) -> dict[str, Any]:
    data = resource.model_dump(mode="json")
    if resource.provider is ProviderName.AWS and resource.kind == "subnet":
        data["attributes"].pop("available_ip_count", None)
    return data


def compare(desired: Inventory, actual: Inventory) -> DriftReport:
    wanted = {_key(item): item for item in desired.resources}
    found = {_key(item): item for item in actual.resources}
    items: list[DriftItem] = []
    for key in sorted(wanted.keys() | found.keys()):
        if key not in found:
            items.append(DriftItem(status="missing", key=key, desired=wanted[key]))
        elif key not in wanted:
            items.append(DriftItem(status="unexpected", key=key, actual=found[key]))
        else:
            left = _configuration(wanted[key])
            right = _configuration(found[key])
            differences = sorted(field for field in left if left[field] != right[field])
            if differences:
                items.append(
                    DriftItem(
                        status="changed",
                        key=key,
                        desired=wanted[key],
                        actual=found[key],
                        differences=differences,
                    )
                )
    summary = {
        status: sum(item.status == status for item in items)
        for status in ("missing", "unexpected", "changed")
    }
    return DriftReport(in_sync=not items, summary=summary, items=items)
