from flask import Flask, request, jsonify, render_template, redirect, url_for
from pymongo import MongoClient
import os
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Connect to MongoDB (Replace <username>, <password>, and <cluster-url>)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://caleb:nThg9wXrILxQR3s0@rsvp-app.14g8a.mongodb.net/rsvp-demo")
client = MongoClient(MONGO_URI)
db = client['rsvp-demo']

# Collections
events_collection = db['events']
master_list_collection = db['master_list']

# Home Route
@app.route('/')
def home():
    return render_template("home.html")

# Event Management Routes
@app.route('/events', methods=['GET', 'POST'])
def manage_events():
    if request.method == 'POST':
        data = {
            "name": request.form['name'],
            "date": request.form['date'],
            "capacity": int(request.form['capacity']),
            "invitees": [],
            "current_batch": 0
        }
        events_collection.insert_one(data)
        return redirect(url_for('manage_events'))
    events = list(events_collection.find({}, {"_id": 0}))
    return render_template("events.html", events=events)

# Master List Routes
@app.route('/master-list', methods=['GET', 'POST'])
def manage_master_list():
    if request.method == 'POST':
        data = {
            "name": request.form['name'],
            "phone": request.form['phone'],
            "tags": request.form['tags'].split(",")  # Split tags by comma
        }
        master_list_collection.insert_one(data)
        return redirect(url_for('manage_master_list'))
    master_list = list(master_list_collection.find({}, {"_id": 0}))
    return render_template("master_list.html", master_list=master_list)

if __name__ == '__main__':
    app.run(debug=True)