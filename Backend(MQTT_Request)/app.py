from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import requests
from datetime import datetime, UTC
import paho.mqtt.client as mqtt
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///accidents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# SerpApi Key
SERPAPI_KEY = "71a702028ca3fba4908e09bbdb46ed0fef1dbbb6a6ff2f79871c6f34d1c480f4"

# MQTT Configuration
MQTT_BROKER = "test.mosquitto.org"  # Public MQTT broker (replace with your broker)
MQTT_PORT = 1883
MQTT_TOPIC = "accident/data"  # Topic to subscribe to

# Initialize MQTT Client
mqtt_client = mqtt.Client()

# Global variable to store the last processed payload
last_payload = None


class Accident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    nearest_hospital = db.Column(db.String(200))  # Store hospital name
    hospital_address = db.Column(db.String(200))  # Store hospital address
    hospital_phone = db.Column(db.String(50))  # Store hospital phone


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


# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker successfully.")
        client.subscribe(MQTT_TOPIC, qos=2)  # Subscribe to the topic
        print(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"Failed to connect to MQTT broker. Result code: {rc}")


def on_message(client, userdata, msg):
    """Callback when a message is received on the subscribed topic."""
    global last_payload

    try:
        payload = msg.payload.decode().strip()  # Decode and strip whitespace
        #print("Raw payload:", payload)  # Debugging: Print the raw payload

        if not payload:
            print("Error: Empty payload received")
            return

        # Parse the payload as JSON
        data = json.loads(payload)
        print("Received data:", data)

        # Validate incoming JSON data
        if not data or "car_id" not in data or "latitude" not in data or "longitude" not in data:
            print("Invalid data received")
            return

        # Ensure latitude and longitude are floats
        try:
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except (ValueError, KeyError) as e:
            print(f"Error parsing latitude/longitude: {e}")
            return

        # Add a unique identifier (timestamp) if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        # Normalize the payload for comparison
        normalized_payload = json.dumps(data, sort_keys=True)

        # Check for duplicate payload
        if normalized_payload == last_payload:
            print("Duplicate message ignored (same payload)")
            return

        # Update the last processed payload
        last_payload = normalized_payload

        # Push an application context
        with app.app_context():
            # Search for the nearest hospital
            hospital = search_nearest_hospital(latitude, longitude)

            # Create a new accident record
            new_accident = Accident(
                car_id=data['car_id'],
                latitude=latitude,
                longitude=longitude,
                nearest_hospital=hospital["name"] if hospital else "Not found",
                hospital_address=hospital["address"] if hospital else "Not found",
                hospital_phone=hospital["phone"] if hospital else "Not found"
            )
            db.session.add(new_accident)
            db.session.commit()
            print("Data saved to database")

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except KeyError as e:
        print(f"Missing key in JSON data: {e}")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")


# Configure MQTT Client
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to MQTT Broker
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  # Start the MQTT loop in a separate thread


@app.route('/')
def index():
    # Get all accidents for the table
    all_accidents = Accident.query.order_by(Accident.timestamp.desc()).all()
    return render_template('index.html', all_accidents=all_accidents)


if __name__ == "__main__":
    app.run(debug=True)