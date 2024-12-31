# app/models/contact.py
class Contact:
    def __init__(self, name, phone, tags=None):
        self.name = name
        self.phone = phone
        self.tags = tags or []

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            phone=data['phone'],
            tags=data.get('tags', [])
        )

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.phone,
            "tags": self.tags
        }