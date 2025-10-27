import csv
from flask import Flask, request, jsonify
from datetime import datetime
import logging
import json

app = Flask(__name__)
app.config['PYTHONUNBUFFERED'] = True

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

CSV_FILE = "dash_hotel_bookings.csv"


# ─────────────────────────────────────────────
# Load and Save CSV
# ─────────────────────────────────────────────
def load_bookings():
    try:
        with open(CSV_FILE, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            return [
                dict(
                    b,
                    num_guests=int(b["num_guests"]),
                    booking_id=int(b["booking_id"]),
                    created_on=b.get("created_on", ""),
                    modified_on=b.get("modified_on", "")
                )
                for b in reader
            ]
    except FileNotFoundError:
        return []



def save_bookings(bookings):
    with open(CSV_FILE, mode='w', newline='') as f:
        fieldnames = [
            "booking_id","created_on", "modified_on", "guest_name", "email", "phone", "hotel_branch",
            "room_type", "check_in", "check_out", "num_guests",
            "payment_status"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for b in bookings:
            writer.writerow({key: b.get(key, "") for key in fieldnames})


bookings = load_bookings()

# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
def find_booking(booking_id, email=None):
    for b in bookings:
        if b["booking_id"] == booking_id and (
                email is None or b["email"].lower() == email.lower()):
            return b
    return None


def next_booking_id():
    return max((b["booking_id"] for b in bookings), default=1000) + 1


@app.route("//")
def home():
    """Home endpoint returning welcome message"""
    return jsonify({"message":
                    "Welcome to Dash Hotel Booking API_Daphne"}), 200


# ─────────────────────────────────────────────
# Agent Hook Endpoint
# ─────────────────────────────────────────────
@app.route('/Agent-hook', methods=['POST'])
def agent_hook():
    body = request.get_json()
    handler = body.get("handler", {})
    data = body.get("session", {}).get("params", {})

    logger.info(f"Handler: {handler}")
    logger.info(f"Data: {data}")

    intent = handler.get("name")

    # ───────── View Booking ─────────
    if intent == "view_booking":
        booking_id = int(data.get("booking_id", 0))
        email = data.get("email", "")
        booking = find_booking(booking_id, email)
        if booking:
            return jsonify({"session": {"params": booking}})
        return jsonify({
            "prompt": {
                "override": {
                    "messages": [{"text": "No booking found."}]
                }
            }
        })

    # ───────── Cancel Booking ─────────
    elif intent == "cancel_booking":
        booking_id = int(data.get("booking_id", 0))
        email = data.get("email", "")
        booking = find_booking(booking_id, email)
        if booking:
            bookings.remove(booking)
            save_bookings(bookings)
            return jsonify({
                "prompt": {
                    "override": {
                        "messages": [{"text": "Booking successfully cancelled."}]
                    }
                }
            })
        return jsonify({
            "prompt": {
                "override": {
                    "messages": [{"text": "Booking not found."}]
                }
            }
        })

    # ───────── Modify Booking ─────────
    elif intent == "modify_booking":
        booking_id = int(data.get("booking_id", 0))
        email = data.get("email", "")
        booking = find_booking(booking_id, email)
        if booking:
            modified_on = datetime.today().strftime("%Y-%m-%d")

            check_in = data.get("check_in", booking.get("check_in"))
            check_out = data.get("check_out", booking.get("check_out"))

            try:
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
                check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
                modified_on_date = datetime.strptime(modified_on, "%Y-%m-%d")

                if check_in_date <= modified_on_date:
                    return jsonify({
                        "prompt": {
                            "override": {
                                "messages": [{"text": "Check-in date must be after today’s date."}]
                            }
                        }
                    })

                if check_out_date <= check_in_date:
                    return jsonify({
                        "prompt": {
                            "override": {
                                "messages": [{"text": "Check-out date must be after the check-in date."}]
                            }
                        }
                    })

            except ValueError:
                return jsonify({
                    "prompt": {
                        "override": {
                            "messages": [{"text": "Invalid date format. Please use YYYY-MM-DD."}]
                        }
                    }
                })

            # Update fields
            for key in [
                "guest_name", "phone", "hotel_branch", "room_type",
                "check_in", "check_out", "num_guests", "payment_status"
            ]:
                if key in data:
                    booking[key] = data[key]

            booking["modified_on"] = modified_on
            save_bookings(bookings)

            return jsonify({
                "session": {"params": booking},
                "prompt": {"override": {"messages": [{"text": "Booking updated successfully."}]}}
            })

        return jsonify({
            "prompt": {"override": {"messages": [{"text": "Booking not found."}]}}
        })

    # ───────── Create Booking ─────────
    elif intent == "create_booking":
        today = datetime.today().strftime('%Y-%m-%d')
        check_in = data.get("check_in", "")
        check_out = data.get("check_out", "")

        try:
            if check_in and check_out:
                check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
                check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
                created_on_date = datetime.strptime(today, "%Y-%m-%d")

                if created_on_date >= check_in_date or created_on_date >= check_out_date:
                    return jsonify({
                        "prompt": {
                            "override": {
                                "messages": [{"text": "Check-in and check-out dates must be after today’s date."}]
                            }
                        }
                    })

        except ValueError:
            return jsonify({
                "prompt": {
                    "override": {
                        "messages": [{"text": "Invalid date format. Please use YYYY-MM-DD."}]
                    }
                }
            })

        new_booking = {
            "booking_id": next_booking_id(),
            "created_on": today,
            "modified_on": "",
            "guest_name": data.get("guest_name", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "hotel_branch": data.get("hotel_branch", ""),
            "room_type": data.get("room_type", ""),
            "check_in": data.get("check_in", ""),
            "check_out": data.get("check_out", ""),
            "num_guests": int(data.get("num_guests", 1)),
            "payment_status": data.get("payment_status", "Unpaid")
        }
        bookings.append(new_booking)
        save_bookings(bookings)
        return jsonify({"session": {"params": new_booking}})

    # ───────── Unknown Intent ─────────
    return jsonify({
        "prompt": {
            "override": {
                "messages": [{"text": "Unknown action."}]
            }
        }
    })




# ────────────────────────────────────────────────────────────
#  Application Entry Point
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start Flask development server
    # host="0.0.0.0" makes it externally accessible
    # port=5000 is the standard Flask port
    # debug=True enables development features
    app.run(host="0.0.0.0", port=5000, debug=True)
