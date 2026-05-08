from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory databases
greenhouses = {}
plants = {}

# ID trackers
gh_id_counter = 1
pl_id_counter = 1

# ==========================================
# GREENHOUSE CRUD ENDPOINTS
# ==========================================

@app.route('/greenhouses', methods=['POST'])
def create_greenhouse():
    global gh_id_counter
    data = request.get_json()
    gh = {
        'id': gh_id_counter,
        'name': data.get('name'),
    }
    greenhouses[gh_id_counter] = gh
    gh_id_counter += 1
    return jsonify(gh), 201

@app.route('/greenhouses', methods=['GET'])
def list_greenhouses():
    return jsonify(list(greenhouses.values())), 200

@app.route('/greenhouses/<int:gh_id>', methods=['GET'])
def get_greenhouse(gh_id):
    gh = greenhouses.get(gh_id)
    if gh:
        return jsonify(gh), 200
    return jsonify({'error': 'Greenhouse not found'}), 404

@app.route('/greenhouses/<int:gh_id>', methods=['PUT'])
def update_greenhouse(gh_id):
    gh = greenhouses.get(gh_id)
    if not gh:
        return jsonify({'error': 'Greenhouse not found'}), 404
    
    data = request.get_json()
    gh['name'] = data.get('name', gh['name'])
    return jsonify(gh), 200

@app.route('/greenhouses/<int:gh_id>', methods=['DELETE'])
def delete_greenhouse(gh_id):
    if gh_id in greenhouses:
        del greenhouses[gh_id]
        return '', 204
    return jsonify({'error': 'Greenhouse not found'}), 404


# ==========================================
# PLANT CRUD ENDPOINTS
# ==========================================

@app.route('/plants', methods=['POST'])
def create_plant():
    global pl_id_counter
    data = request.get_json()
    plant = {
        'id': pl_id_counter,
        'name': data.get('name'),
        'species': data.get('species'),
        'greenhouse_id': data.get('greenhouse_id')
    }
    plants[pl_id_counter] = plant
    pl_id_counter += 1
    return jsonify(plant), 201

@app.route('/plants', methods=['GET'])
def list_plants():
    return jsonify(list(plants.values())), 200

@app.route('/plants/<int:pl_id>', methods=['GET'])
def get_plant(pl_id):
    plant = plants.get(pl_id)
    if plant:
        return jsonify(plant), 200
    return jsonify({'error': 'Plant not found'}), 404

@app.route('/plants/<int:pl_id>', methods=['DELETE'])
def delete_plant(pl_id):
    if pl_id in plants:
        del plants[pl_id]
        return '', 204
    return jsonify({'error': 'Plant not found'}), 404

if __name__ == '__main__':
    # Listen on all network interfaces so Docker can expose it
    app.run(host='0.0.0.0', port=5000)