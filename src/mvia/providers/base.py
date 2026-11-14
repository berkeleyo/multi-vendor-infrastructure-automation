from abc import ABC, abstractmethod

from mvia.models import Resource


class Provider(ABC):
    @abstractmethod
    def discover(self) -> list[Resource]:
        """Return normalized read-only resources."""
