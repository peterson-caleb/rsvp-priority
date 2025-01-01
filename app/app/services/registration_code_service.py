# app/services/registration_code_service.py
from datetime import datetime, timedelta
import secrets
from bson import ObjectId
import logging

class RegistrationCodeService:
    def __init__(self, db):
        self.db = db
        self.codes_collection = db['registration_codes']
        
    def create_code(self, created_by_user_id, expires_in_days=7, max_uses=1):
        code = secrets.token_urlsafe(16)
        code_doc = {
            "code": code,
            "created_by": ObjectId(created_by_user_id),
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=expires_in_days),
            "max_uses": max_uses,
            "uses": 0,
            "is_active": True
        }
        try:
            result = self.codes_collection.insert_one(code_doc)
            print(f"Created new code: {code}")
            return code
        except Exception as e:
            print(f"Error creating code: {str(e)}")
            return None

    def validate_code(self, code):
        print(f"\nValidating code: {code}")
        
        # First, try to find the code
        code_doc = self.codes_collection.find_one({"code": code})
        
        if not code_doc:
            print(f"Code not found in database")
            return False
            
        print(f"Found code document: {code_doc}")
        
        # Check active status
        if not code_doc.get('is_active'):
            print(f"Code is not active")
            return False
            
        # Check expiration
        expires_at = code_doc.get('expires_at')
        if expires_at and expires_at <= datetime.utcnow():
            print(f"Code has expired. Expires at: {expires_at}, Current time: {datetime.utcnow()}")
            return False
            
        # Check usage count
        uses = code_doc.get('uses', 0)
        max_uses = code_doc.get('max_uses', 1)
        if uses >= max_uses:
            print(f"Code usage limit reached. Uses: {uses}, Max uses: {max_uses}")
            return False
            
        print("Code validation successful!")
        return True

    def use_code(self, code):
        print(f"\nAttempting to use code: {code}")
        
        # Find the code first
        code_doc = self.codes_collection.find_one({"code": code})
        if not code_doc:
            return False
            
        # Update the code usage if it's valid
        result = self.codes_collection.update_one(
            {
                "code": code,
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow()},
                "uses": {"$lt": code_doc["max_uses"]}
            },
            {
                "$inc": {"uses": 1}
            }
        )
        
        success = result.modified_count > 0
        print(f"Code usage {'successful' if success else 'failed'}")
        return success

    def list_active_codes(self):
        return list(self.codes_collection.find({
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        }))

    def debug_show_code(self, code):
        """Helper method to show code details"""
        code_doc = self.codes_collection.find_one({"code": code})
        if code_doc:
            print("\nCode details:")
            for key, value in code_doc.items():
                print(f"{key}: {value}")