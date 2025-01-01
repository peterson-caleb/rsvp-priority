# create_admin.py
from app import create_app, user_service
from app.services.user_service import UserService
import getpass

def create_initial_admin():
    app = create_app()
    
    with app.app_context():
        # Create a new instance of UserService
        from app import mongo
        user_service_instance = UserService(mongo.db)
        
        print("Create Initial Admin User")
        print("-" * 30)
        
        username = input("Enter admin username: ")
        email = input("Enter admin email: ")
        password = getpass.getpass("Enter admin password: ")
        confirm_password = getpass.getpass("Confirm admin password: ")
        
        if password != confirm_password:
            print("Passwords don't match!")
            return
        
        try:
            user = user_service_instance.create_user(
                username=username,
                email=email,
                password=password,
                is_admin=True,
                registration_method='admin_created'
            )
            print(f"\nAdmin user created successfully!")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            
        except Exception as e:
            print(f"Error creating admin user: {str(e)}")

if __name__ == "__main__":
    create_initial_admin()