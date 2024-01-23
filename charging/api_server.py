import json
from typing import Any

from flask import Flask, jsonify, request
from charging.db import add_event, get_event


app = Flask(__name__)


def _get_message(message: Any, code: int = 200):
    return jsonify({'message': message, 'code': code}), code


@app.route('/api/reserve_now/<serial_number>', methods=['GET', 'PUT', 'POST'])
def reserve_now(serial_number: str):
    # Get request parameters
    token = {
        'type': request.args.get('type', None, type=str),
        'id_token': request.args.get('id_token', None, type=str),
    }

    # Check token is set correctly
    if token['type'] is None or token['id_token'] is None:
        return _get_message('Bad request', 400)

    # Add event to DB
    add_event('reserve_now', serial_number, token)

    return _get_message('OK')


'''
@app.get('/api/get/<serial_number>')
def test_get(serial_number: str):
    return _get_message(get_event('reserve_now', serial_number))
'''


if __name__ == '__main__':
    app.run(host='::', port=8000)
