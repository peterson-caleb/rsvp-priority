from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .. import event_service, contact_service
from datetime import datetime
from bson import ObjectId
from flask_login import login_required
import pytz

bp = Blueprint('events', __name__)

@bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if request.method == 'POST':
        try:
            event_data = {
                'name': request.form['name'],
                'date': request.form['date'],
                'capacity': int(request.form['capacity'])
            }
            event_service.create_event(event_data)
            flash('Event created successfully!', 'success')
        except ValueError as e:
            flash(f'Error creating event: {str(e)}', 'error')
        return redirect(url_for('events.manage_events'))

    events = event_service.get_events()
    
    # Convert ObjectIds to strings for template rendering
    for event in events:
        event['_id'] = str(event['_id'])
        for invitee in event.get('invitees', []):
            if '_id' in invitee:
                invitee['_id'] = str(invitee['_id'])

    # Get current time in UTC for template
    now = datetime.now(pytz.UTC)

    return render_template('events/list.html', events=events, now=now)

@bp.route('/events/<event_id>/invitees', methods=['GET'])
@login_required
def manage_invitees(event_id):
    """Dedicated page for managing event invitees"""
    event = event_service.get_event(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('events.manage_events'))

    # Get all contacts and their tags for filtering
    contacts = contact_service.get_contacts()
    all_tags = contact_service.get_all_tags()
    
    # Get selected tags from query parameters
    selected_tags = request.args.getlist('tags')
    
    # Filter contacts if tags are selected
    if selected_tags:
        contacts = [c for c in contacts if any(tag in c.get('tags', []) for tag in selected_tags)]
    
    # Convert ObjectIds to strings
    event._id = str(event._id)
    for invitee in event.invitees:
        invitee['_id'] = str(invitee['_id'])
    
    for contact in contacts:
        contact['_id'] = str(contact['_id'])

    return render_template(
        'events/manage_invitees.html',
        event=event,
        contacts=contacts,
        all_tags=all_tags,
        selected_tags=selected_tags
    )


@bp.route('/events/<event_id>/add_invitees', methods=['POST'])
@login_required
def add_invitees(event_id):
    """Add invitees to an event from the simple multi-select list."""
    # THIS IS THE NEW DEBUGGING LINE
    print(f"DEBUG: Form data received: {request.form}")
    
    selected_contact_ids = request.form.getlist('invitees_to_add')

    if not selected_contact_ids:
        flash('No invitees selected.', 'warning')
        return redirect(url_for('events.manage_invitees', event_id=event_id))

    try:
        # Get the full contact details for each selected ID
        invitees_to_add = [contact_service.get_contact(cid) for cid in selected_contact_ids]
        
        if invitees_to_add:
            event_service.add_invitees(event_id, invitees_to_add)
            flash(f'{len(invitees_to_add)} invitees added successfully!', 'success')
        
    except Exception as e:
        flash(f'Error adding invitees: {str(e)}', 'error')
    
    return redirect(url_for('events.manage_invitees', event_id=event_id))

@bp.route('/events/<event_id>/reorder_invitees', methods=['POST'])
@login_required
def reorder_invitees(event_id):
    """Update invitee order based on provided order of IDs"""
    try:
        # Get the new order from the request
        new_order = request.json.get('invitee_order', [])
        if not new_order:
            return jsonify({'error': 'No order provided'}), 400

        # Update the order in the database
        event_service.reorder_invitees(event_id, new_order)
        return jsonify({'message': 'Order updated successfully'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/events/<event_id>/invitee/<invitee_id>/priority', methods=['POST'])
@login_required
def update_invitee_priority(event_id, invitee_id):
    """Update the priority of a single invitee"""
    try:
        new_priority = int(request.json.get('priority', 0))
        event_service.update_invitee_priority(event_id, invitee_id, new_priority)
        return jsonify({'message': 'Priority updated successfully'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/events/<event_id>/delete_invitee/<invitee_id>', methods=['POST'])
@login_required
def delete_invitee(event_id, invitee_id):
    """Remove an invitee from an event"""
    try:
        event_service.delete_invitee(event_id, invitee_id)
        flash('Invitee removed successfully!', 'success')
    except Exception as e:
        flash(f'Error removing invitee: {str(e)}', 'error')
    return redirect(url_for('events.manage_invitees', event_id=event_id))

@bp.route('/events/<event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete an entire event"""
    try:
        if event_service.delete_event(event_id):
            flash('Event deleted successfully!', 'success')
        else:
            flash('Event not found.', 'error')
    except Exception as e:
        flash(f'Error deleting event: {str(e)}', 'error')
    return redirect(url_for('events.manage_events'))

@bp.route('/events/<event_id>/test_sms/<invitee_id>', methods=['POST'])
@login_required
def test_sms(event_id, invitee_id):
    """Send a test SMS to an invitee"""
    try:
        event = event_service.get_event(event_id)
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('events.manage_events'))
            
        invitee = next((i for i in event.invitees 
                       if str(i['_id']) == invitee_id), None)
        
        if not invitee:
            flash('Invitee not found', 'error')
            return redirect(url_for('events.manage_invitees', event_id=event_id))
            
        message_sid, status, error_message = event_service.sms_service.send_invitation(
            phone_number=invitee['phone'],
            event_name=event.name,
            event_date=event.date,
            event_code=event.event_code
        )
        
        if status == 'SENT':
            flash(f"Test message sent successfully to {invitee['name']}", 'success')
        else:
            flash(f"Failed to send test message to {invitee['name']}: {error_message}", 'error')
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        
    return redirect(url_for('events.manage_invitees', event_id=event_id))

@bp.route('/events/<event_id>/retry_failed', methods=['POST'])
@login_required
def retry_failed_invitations(event_id):
    """Retry all failed invitations for an event"""
    try:
        event = event_service.get_event(event_id)
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('events.manage_events'))

        # Reset status of failed invitations to 'pending'
        failed_count = 0
        for invitee in event.invitees:
            if invitee['status'] == 'ERROR':
                invitee['status'] = 'pending'
                invitee.pop('error_message', None)
                failed_count += 1

        if failed_count > 0:
            event_service.update_event(event_id, {"invitees": event.invitees})
            flash(f'Reset {failed_count} failed invitations to pending status', 'success')
        else:
            flash('No failed invitations to retry', 'info')

    except Exception as e:
        flash(f'Error retrying invitations: {str(e)}', 'error')

    return redirect(url_for('events.manage_invitees', event_id=event_id))

@bp.route('/events/<event_id>/toggle_automation', methods=['POST'])
@login_required
def toggle_automation(event_id):
    """Toggles the automation status of an event between 'active' and 'paused'."""
    try:
        event = event_service.get_event(event_id)
        if not event:
            flash('Event not found.', 'error')
            return redirect(url_for('events.manage_events'))

        new_status = 'active' if event.automation_status == 'paused' else 'paused'
        event_service.update_event(event_id, {'automation_status': new_status})
        flash(f'Event automation has been set to {new_status}.', 'success')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')

    return redirect(url_for('events.manage_invitees', event_id=event_id))

