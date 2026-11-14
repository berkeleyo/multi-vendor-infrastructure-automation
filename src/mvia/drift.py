"""Desired-state comparison."""

from mvia.models import DriftItem, DriftReport, Inventory, Resource


def _key(resource: Resource) -> str:
    return f"{resource.provider}/{resource.kind}/{resource.id}"


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
            left = wanted[key].model_dump(mode="json")
            right = found[key].model_dump(mode="json")
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
