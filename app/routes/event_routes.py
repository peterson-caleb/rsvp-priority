# app/routes/event_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import event_service, contact_service
from datetime import datetime
from bson import ObjectId
from flask_login import login_required

bp = Blueprint('events', __name__)

@bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if request.method == 'POST':
        event_data = {
            'name': request.form['name'],
            'date': request.form['date'],
            'capacity': int(request.form['capacity'])
        }
        event_service.create_event(event_data)
        flash('Event created successfully!', 'success')
        return redirect(url_for('events.manage_events'))

    events = event_service.get_events()
    master_list = contact_service.get_contacts()

    # Convert ObjectIds to strings for template rendering
    for event in events:
        event['_id'] = str(event['_id'])
        for invitee in event.get('invitees', []):
            if '_id' in invitee:
                invitee['_id'] = str(invitee['_id'])
    
    for contact in master_list:
        if '_id' in contact:
            contact['_id'] = str(contact['_id'])

    now = datetime.now()

    return render_template('events/list.html', events=events, master_list=master_list, now=now)

@bp.route('/add_invitees/<event_id>', methods=['POST'])
@login_required
def add_invitees(event_id):
    selected_invitee_ids = request.form.getlist('invitees[]')

    if not selected_invitee_ids:
        flash('No invitees selected.', 'warning')
        return redirect(url_for('events.manage_events'))

    try:
        # Get the contacts from selected IDs
        invitees = []
        for id in selected_invitee_ids:
            contact = contact_service.get_contact(id)
            if contact:
                invitees.append(contact)

        # Add invitees to event
        event_service.add_invitees(event_id, invitees)
        flash('Invitees added successfully!', 'success')
        
    except Exception as e:
        flash(f'Error adding invitees: {str(e)}', 'error')
    
    return redirect(url_for('events.manage_events'))

@bp.route('/delete_invitee/<event_id>/<invitee_id>', methods=['POST'])
@login_required
def delete_invitee(event_id, invitee_id):
    try:
        event_service.delete_invitee(event_id, invitee_id)
        flash('Invitee removed successfully!', 'success')
    except Exception as e:
        flash(f'Error removing invitee: {str(e)}', 'error')
    return redirect(url_for('events.manage_events'))

@bp.route('/delete_event/<event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    try:
        if event_service.delete_event(event_id):
            flash('Event deleted successfully!', 'success')
        else:
            flash('Event not found.', 'error')
    except Exception as e:
        flash(f'Error deleting event: {str(e)}', 'error')
    return redirect(url_for('events.manage_events'))

@bp.route('/test_sms/<event_id>/<invitee_id>', methods=['POST'])
@login_required
def test_sms(event_id, invitee_id):
    try:
        event = event_service.get_event(event_id)
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('events.manage_events'))
            
        invitee = next((i for i in event.invitees 
                       if str(i['_id']) == invitee_id), None)
        
        if not invitee:
            flash('Invitee not found', 'error')
            return redirect(url_for('events.manage_events'))
            
        message_sid = event_service.sms_service.send_invitation(
            phone_number=invitee['phone'],
            event_name=event.name,
            event_date=event.date,
            event_code=event.event_code
        )
        
        if message_sid:
            flash(f"Test message sent successfully to {invitee['name']}", 'success')
        else:
            flash(f"Failed to send test message to {invitee['name']}", 'error')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        
    return redirect(url_for('events.manage_events'))