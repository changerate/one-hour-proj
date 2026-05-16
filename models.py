from dataclasses import dataclass


@dataclass
class Message:
    id: str
    timestamp: str
    username: str
    text: str

    @classmethod
    def from_row(cls, row: list[str]) -> "Message":
        if len(row) < 4:
            raise ValueError(f"Expected 4 columns, got {len(row)}")
        return cls(id=row[0], timestamp=row[1], username=row[2], text=row[3])

    def to_row(self) -> list[str]:
        return [self.id, self.timestamp, self.username, self.text]
