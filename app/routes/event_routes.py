from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from .. import event_service, contact_service
from datetime import datetime
from bson import ObjectId
from flask_login import login_required
import pytz
import json

bp = Blueprint('events', __name__)

@bp.route('/events', methods=['GET', 'POST'])
@login_required
def manage_events():
    if request.method == 'POST':
        try:
            event_data = { 'name': request.form['name'], 'date': request.form['date'], 'capacity': int(request.form['capacity']) }
            event_service.create_event(event_data)
            flash('Event created successfully!', 'success')
        except ValueError as e:
            flash(f'Error creating event: {str(e)}', 'error')
        return redirect(url_for('events.manage_events'))
    events = event_service.get_events()
    for event in events:
        event['_id'] = str(event['_id'])
    now = datetime.now(pytz.UTC)
    return render_template('events/list.html', events=events, now=now)

@bp.route('/events/<event_id>/invitees', methods=['GET'])
@login_required
def manage_invitees(event_id):
    event = event_service.get_event(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('events.manage_events'))
    contacts = contact_service.get_contacts()
    current_invitee_ids = {invitee.get('contact_id') for invitee in event.invitees}
    return render_template(
        'events/manage_invitees.html',
        event=event,
        contacts=contacts,
        current_invitee_ids=current_invitee_ids
    )

@bp.route('/events/<event_id>/add_invitees', methods=['POST'])
@login_required
def add_invitees(event_id):
    selected_contact_ids = request.form.getlist('invitees_to_add')
    if not selected_contact_ids:
        flash('No invitees selected.', 'warning')
        return redirect(url_for('events.manage_invitees', event_id=event_id))
    try:
        invitees_to_add = [contact_service.get_contact(cid) for cid in selected_contact_ids]
        added_count = event_service.add_invitees(event_id, invitees_to_add)
        if added_count > 0:
            flash(f'{added_count} new invitees added successfully!', 'success')
        else:
            flash('No new invitees were added (they may already be on the list).', 'info')
    except Exception as e:
        flash(f'Error adding invitees: {str(e)}', 'error')
    return redirect(url_for('events.manage_invitees', event_id=event_id))

@bp.route('/events/<event_id>/toggle_automation', methods=['POST'])
@login_required
def toggle_automation(event_id):
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

@bp.route('/events/<event_id>/reorder_invitees', methods=['POST'])
@login_required
def reorder_invitees(event_id):
    try:
        new_order = request.json.get('invitee_order', [])
        event_service.reorder_invitees(event_id, new_order)
        return jsonify({'message': 'Order updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/events/<event_id>/delete_invitee/<invitee_id>', methods=['POST'])
@login_required
def delete_invitee(event_id, invitee_id):
    try:
        event_service.delete_invitee(event_id, invitee_id)
        flash('Invitee removed successfully!', 'success')
    except Exception as e:
        flash(f'Error removing invitee: {str(e)}', 'error')
    return redirect(url_for('events.manage_invitees', event_id=event_id))

# ... (and any other routes you had in this file, like rsvp_page and submit_rsvp) ...