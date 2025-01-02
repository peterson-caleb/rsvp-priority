# app/services/user_service.py
from bson import ObjectId
import bcrypt
from ..models.user import User

class UserService:
    def __init__(self, db):
        self.db = db
        self.users_collection = db['users']
        # Create unique index for email and username
        self.users_collection.create_index('email', unique=True)
        self.users_collection.create_index('username', unique=True)

    def create_user(self, username, email, password, is_admin=False, registration_method=None):
        # Check if user already exists
        if self.users_collection.find_one({'$or': [{'email': email}, {'username': username}]}):
            raise ValueError('Username or email already exists')
        
        # Hash the password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user document
        user = User(
            username=username, 
            email=email, 
            password_hash=password_hash,
            is_admin=is_admin,
            registration_method=registration_method
        )
        
        # Insert into database
        result = self.users_collection.insert_one(user.to_dict())
        user._id = result.inserted_id
        return user

    def get_user(self, user_id):
        user_data = self.users_collection.find_one({'_id': ObjectId(user_id)})
        return User.from_dict(user_data) if user_data else None

    def get_user_by_email(self, email):
        user_data = self.users_collection.find_one({'email': email})
        return User.from_dict(user_data) if user_data else None

    def verify_password(self, user, password):
        return bcrypt.checkpw(password.encode('utf-8'), user.password_hash)

    def make_admin(self, user_id):
        result = self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_admin': True}}
        )
        return result.modified_count > 0

    def remove_admin(self, user_id):
        result = self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_admin': False}}
        )
        return result.modified_count > 0

    def list_users(self):
        return [User.from_dict(user_data) for user_data in self.users_collection.find()]