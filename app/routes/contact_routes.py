# app/routes/contact_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import contact_service
from flask_login import login_required

bp = Blueprint('contacts', __name__)

@bp.route('/master-list', methods=['GET', 'POST'])
@login_required
def manage_master_list():
    if request.method == 'POST':
        contact_data = {
            'name': request.form['name'],
            'phone': request.form['phone'],
            'tags': [tag.strip() for tag in request.form['tags'].split(',') if tag.strip()]
        }
        contact_service.create_contact(contact_data)
        flash('Contact added successfully!', 'success')
        return redirect(url_for('contacts.manage_master_list'))

    # Get filter parameters
    tag_filter = request.args.get('tags')
    filters = {}
    if tag_filter:
        filters['tags'] = {'$in': tag_filter.split(',')}

    contacts = contact_service.get_contacts(filters)
    all_tags = contact_service.get_all_tags()
    
    return render_template('contacts/list.html', 
                         master_list=contacts, 
                         all_tags=all_tags, 
                         selected_tags=tag_filter.split(',') if tag_filter else [])

@bp.route('/delete_contact/<contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    contact_service.delete_contact(contact_id)
    flash('Contact deleted successfully!', 'success')
    return redirect(url_for('contacts.manage_master_list'))

@bp.route('/edit_contact/<contact_id>', methods=['POST'])
@login_required
def edit_contact(contact_id):
    contact_data = {
        'name': request.form['name'],
        'phone': request.form['phone'],
        'tags': [tag.strip() for tag in request.form['tags'].split(',') if tag.strip()]
    }
    contact_service.update_contact(contact_id, contact_data)
    flash('Contact updated successfully!', 'success')
    return redirect(url_for('contacts.manage_master_list'))