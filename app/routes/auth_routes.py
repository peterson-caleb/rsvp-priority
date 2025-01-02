# app/routes/auth_routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from .. import user_service, registration_code_service

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = user_service.get_user_by_email(email)
        if user and user_service.verify_password(user, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        invitation_code = request.form['invitation_code']
        
        print(f"\nProcessing registration:")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Invitation code: {invitation_code}")
        
        try:
            # Debug: Show code details before validation
            registration_code_service.debug_show_code(invitation_code)
            
            # Validate invitation code
            if not registration_code_service.validate_code(invitation_code):
                flash('Invalid or expired invitation code', 'error')
                return render_template('auth/register.html')
            
            # Create user
            user = user_service.create_user(
                username=username,
                email=email,
                password=password,
                registration_method='invite_code'
            )
            
            # Mark invitation code as used
            if not registration_code_service.use_code(invitation_code):
                print(f"Warning: Could not mark invitation code {invitation_code} as used")
            
            # Log the user in
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
            
        except ValueError as e:
            print(f"ValueError during registration: {str(e)}")
            flash(str(e), 'error')
        except Exception as e:
            print(f"Error during registration: {str(e)}")
            flash('An error occurred during registration', 'error')
    
    return render_template('auth/register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Admin routes for managing invitation codes
@bp.route('/admin/invitation-codes', methods=['GET', 'POST'])
@login_required
def manage_invitation_codes():
    if not current_user.is_admin:
        flash('Unauthorized access', 'error')
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        expires_in_days = int(request.form.get('expires_in_days', 7))
        max_uses = int(request.form.get('max_uses', 1))
        
        code = registration_code_service.create_code(
            created_by_user_id=current_user.id,
            expires_in_days=expires_in_days,
            max_uses=max_uses
        )
        flash(f'New invitation code created: {code}', 'success')
    
    active_codes = registration_code_service.list_active_codes()
    return render_template('auth/invitation_codes.html', codes=active_codes)