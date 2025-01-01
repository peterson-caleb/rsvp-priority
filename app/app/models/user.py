# app/models/user.py
from flask_login import UserMixin
from bson import ObjectId
from datetime import datetime

class User(UserMixin):
    def __init__(self, username, email, password_hash, is_admin=False, registration_method=None, _id=None):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.registration_method = registration_method  # 'invite_code' or 'admin_created'
        self.created_at = datetime.utcnow()
        self._id = _id if _id else ObjectId()

    @property
    def id(self):
        return str(self._id)

    @classmethod
    def from_dict(cls, data):
        return cls(
            username=data['username'],
            email=data['email'],
            password_hash=data['password_hash'],
            is_admin=data.get('is_admin', False),
            registration_method=data.get('registration_method'),
            _id=data.get('_id')
        )

    def to_dict(self):
        return {
            "_id": self._id,
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "is_admin": self.is_admin,
            "registration_method": self.registration_method,
            "created_at": self.created_at
        }