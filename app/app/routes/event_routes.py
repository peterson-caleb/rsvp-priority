# app/routes/event_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import event_service, contact_service, sms_service
from bson import ObjectId
from flask_login import login_required

# At the top of both event_routes.py and contact_routes.py:
from flask_login import login_required

bp = Blueprint('events', __name__)

@bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if request.method == 'POST':
        event_data = {
            'name': request.form['name'],
            'date': request.form['date'],
            'capacity': int(request.form['capacity']),
            'batch_size': int(request.form.get('batch_size', 10))
        }
        event_service.create_event(event_data)
        flash('Event created successfully!', 'success')
        return redirect(url_for('events.manage_events'))

    events = event_service.get_events()
    master_list = contact_service.get_contacts()

    # Debug print
    print("Master List:", master_list)
    
    for event in events:
        event['_id'] = str(event['_id'])
        for invitee in event.get('invitees', []):
            if '_id' in invitee:
                invitee['_id'] = str(invitee['_id'])
    
    for contact in master_list:
        if '_id' in contact:
            contact['_id'] = str(contact['_id'])

    return render_template('events/list.html', events=events, master_list=master_list)

@bp.route('/add_invitees/<event_id>', methods=['POST'])
@login_required
def add_invitees(event_id):
    selected_invitee_ids = request.form.getlist('invitees[]')
    print("Selected IDs:", selected_invitee_ids)  # Debug print

    if not selected_invitee_ids:
        flash('No invitees selected.', 'warning')
        return redirect(url_for('events.manage_events'))

    try:
        # Convert string IDs to ObjectId and get the contacts
        invitees = []
        for id in selected_invitee_ids:
            contact = contact_service.get_contact(id)
            if contact:
                invitees.append(contact)
            print(f"Found contact for ID {id}:", contact)  # Debug print

        print("All invitees to add:", invitees)  # Debug print

        # Add invitees to event
        event_service.add_invitees(event_id, invitees)
        flash('Invitees added successfully!', 'success')
    except Exception as e:
        print("Error adding invitees:", str(e))  # Debug print
        flash(f'Error adding invitees: {str(e)}', 'error')
    
    return redirect(url_for('events.manage_events'))

@bp.route('/delete_invitee/<event_id>/<invitee_id>', methods=['POST'])
@login_required
def delete_invitee(event_id, invitee_id):
    event_service.delete_invitee(event_id, invitee_id)
    flash('Invitee removed successfully!', 'success')
    return redirect(url_for('events.manage_events'))

@bp.route('/send_invitations/<event_id>', methods=['POST'])
@login_required
def send_invitations(event_id):
    try:
        # Get the event
        event = event_service.get_event(event_id)
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('events.manage_events'))
        
        # Get pending invitees
        pending_invitees = [i for i in event.invitees if i['status'] == 'pending']
        if not pending_invitees:
            flash('No pending invitees to invite', 'warning')
            return redirect(url_for('events.manage_events'))
        
        # Send invitations
        success_count = 0
        fail_count = 0
        for invitee in pending_invitees:
            try:
                # Send SMS
                message_sid = sms_service.send_invitation(
                    phone_number=invitee['phone'],
                    event_name=event.name,
                    event_date=event.date
                )
                
                if message_sid:
                    success_count += 1
                    # Update invitee status to 'invited'
                    event_service.update_invitee_status(event_id, invitee['_id'], 'invited')
                else:
                    fail_count += 1
                    
            except Exception as e:
                print(f"Error sending invitation to {invitee['phone']}: {str(e)}")
                fail_count += 1
        
        # Flash appropriate message
        if success_count > 0:
            flash(f'Successfully sent {success_count} invitations', 'success')
        if fail_count > 0:
            flash(f'Failed to send {fail_count} invitations', 'error')
            
    except Exception as e:
        flash(f'Error sending invitations: {str(e)}', 'error')
    
    return redirect(url_for('events.manage_events'))

@bp.route('/test_sms/<event_id>/<invitee_id>', methods=['POST'])
@login_required
def test_sms(event_id, invitee_id):
    try:
        # Get event from MongoDB directly
        event_data = event_service.events_collection.find_one({"_id": ObjectId(event_id)})
        if not event_data:
            flash('Event not found', 'error')
            return redirect(url_for('events.manage_events'))
            
        # Find the invitee
        invitee = next((i for i in event_data.get('invitees', []) 
                       if str(i['_id']) == invitee_id), None)
        
        if not invitee:
            flash('Invitee not found', 'error')
            return redirect(url_for('events.manage_events'))
            
        # Send test message
        print(f"Sending test SMS to {invitee['phone']}")  # Debug print
        message_sid = sms_service.send_invitation(
            phone_number=invitee['phone'],
            event_name=event_data['name'],
            event_date=event_data['date']
        )
        
        if message_sid:
            flash(f"Test message sent successfully to {invitee['name']} ({invitee['phone']})", 'success')
        else:
            flash(f"Failed to send test message to {invitee['name']}", 'error')
            
    except Exception as e:
        print(f"Error in test_sms: {str(e)}")  # Debug print
        flash(f'Error: {str(e)}', 'error')
        
    return redirect(url_for('events.manage_events'))