# app/routes/event_routes.py
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
    
    for event in events:
        event['_id'] = str(event['_id'])
        for invitee in event.get('invitees', []):
            if '_id' in invitee:
                invitee['_id'] = str(invitee['_id'])

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

    contacts = contact_service.get_contacts()
    all_tags = contact_service.get_all_tags()
    
    selected_tags = request.args.getlist('tags')
    
    if selected_tags:
        contacts = [c for c in contacts if any(tag in c.get('tags', []) for tag in selected_tags)]
    
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
        new_order = request.json.get('invitee_order', [])
        if not new_order:
            return jsonify({'error': 'No order provided'}), 400

        event_service.reorder_invitees(event_id, new_order)
        return jsonify({'message': 'Order updated successfully'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
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

@bp.route('/rsvp/<token>', methods=['GET'])
def rsvp_page(token):
    """The landing page for the guest to click Yes or No."""
    event, invitee = event_service.find_event_and_invitee_by_token(token)
    
    if not event or not invitee:
        return render_template("events/rsvp_confirmation.html", success=False, message="This invitation link is invalid or has expired.")
    
    if invitee['status'] not in ['invited', 'ERROR']:
        return render_template("events/rsvp_confirmation.html", success=True, message="Thank you, we have already received your response.")

    return render_template("events/rsvp_page.html", event=event, invitee=invitee, token=token)

@bp.route('/rsvp/submit/<token>/<response>', methods=['GET'])
def submit_rsvp(token, response):
    """Processes the Yes/No response and shows a confirmation page."""
    success, message = event_service.process_rsvp_from_url(token, response)
    
    return render_template("events/rsvp_confirmation.html", success=success, message=message)

