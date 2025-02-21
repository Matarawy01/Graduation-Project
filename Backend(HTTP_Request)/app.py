from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accidents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# SerpApi Key
SERPAPI_KEY = "71a702028ca3fba4908e09bbdb46ed0fef1dbbb6a6ff2f79871c6f34d1c480f4"

class Accident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    nearest_hospital = db.Column(db.String(200))  # Store hospital name
    hospital_address = db.Column(db.String(200))  # Store hospital address
    hospital_phone = db.Column(db.String(50))     # Store hospital phone

# Create database tables
with app.app_context():
    db.create_all()


def search_nearest_hospital(latitude, longitude):
    """Search for the nearest hospital using SerpAPI."""
    search_url = "https://serpapi.com/search"
    params = {
        "engine": "google_maps",
        "type": "search",
        "q": "hospitals",
        "ll": f"@{latitude},{longitude},15z",
        "key": SERPAPI_KEY
    }
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "local_results" in data and data["local_results"]:
            # Get the first hospital from the results
            hospital = data["local_results"][0]
            return {
                "name": hospital.get("title"),
                "address": hospital.get("address"),
                "phone": hospital.get("phone")
            }
    except Exception as e:
        print(f"Error searching for hospitals: {e}")
    return None


@app.route('/api/accident', methods=['POST'])
def receive_accident_data():
    data = request.json
    print("Received data:", data)  # Log incoming data
    
    # Validate incoming JSON data
    if not data or "car_id" not in data or "latitude" not in data or "longitude" not in data:
        return jsonify({"error": "Invalid data. Please provide car_id, latitude, and longitude."}), 400

    # Search for the nearest hospital
    hospital = search_nearest_hospital(data['latitude'], data['longitude'])

    # Create a new accident record
    new_accident = Accident(
        car_id=data['car_id'],
        latitude=data['latitude'],
        longitude=data['longitude'],
        nearest_hospital=hospital["name"] if hospital else "Not found",
        hospital_address=hospital["address"] if hospital else "Not found",
        hospital_phone=hospital["phone"] if hospital else "Not found"
    )
    db.session.add(new_accident)
    db.session.commit()

    return jsonify({"message": "Data received successfully"}), 201


@app.route('/')
def index():
    # Get all accidents for the table
    all_accidents = Accident.query.order_by(Accident.timestamp.desc()).all()
    return render_template('index.html', all_accidents=all_accidents)


if __name__ == "__main__":
    app.run(debug=True)