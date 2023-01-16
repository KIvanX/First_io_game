from flask import Flask, render_template, request, session
import threading
import logging
import random
import json
import time
import math

app = Flask(__name__)
app.secret_key = '123456'
heros = {}
food = {}
colors = ['red', 'green', 'blue', 'yellow', 'violet']
WIDTH, HEIGHT = 3500, 2000


@app.route("/", methods=['POST', 'GET'])
def index():
    if session.get('player_id', 0) in heros:
        heros.pop(session['player_id'])
    return render_template("index.html")


@app.route("/set_name")
def set_name():
    session['player_name'] = request.args.get('name')
    if session.get('player_id', 0) in heros:
        heros[session['player_id']]['name'] = session['player_name']
    return {'status': 'OK'}


@app.route("/init")
def init():
    session['player_id'] = round(random.random(), 10)
    chunk_id, x, y = round(random.random(), 10), random.randint(0, WIDTH), random.randint(0, HEIGHT)
    heros[session['player_id']] = {'chunks': {chunk_id: {'x': x, 'y': y, 'score': 500}},
                                   'full_score': 50,
                                   'camera_x': x,
                                   'camera_y': y,
                                   'camera_width': int(request.args.get('width')),
                                   'camera_height': int(request.args.get('height')),
                                   'image': random.randint(1, 5),
                                   'name': session.get('player_name', '')}
    return {'self_id': session['player_id'], 'saved_name': session.get('player_name', '')}


@app.route("/update")
def update():
    if 'player_id' not in session or session['player_id'] not in heros or not heros[session['player_id']]['chunks']:
        return {'status': 'reload'}

    vis_food = []
    for _ in range(3):
        try:
            tick()
            separation()
            move()
            vis_food = get_visible_food()
            food_collision(vis_food)
            heros_collision()
            break
        except Exception as e:
            print(e)

    return json.dumps({'heros': heros, 'food': vis_food, 'status': 'OK'})


def tick():
    hero = heros[session['player_id']]
    for chunk in hero['chunks'].values():
        chunk['score'] *= 0.9995

    full = int(sum([c['score'] for c in hero['chunks'].values()]) / 10)
    hero['full_score'] = max(hero['full_score'], full) if abs(full - hero['full_score']) < 100 else full
    hero['camera_k'] = max(1.2 - hero['full_score']**0.4 / 100, 0.4)


def separation():
    clones = {}
    if request.args.get('is_jump') == 'true':
        for chunk in heros[session['player_id']]['chunks'].values():
            if chunk['score'] > 1000 and len(heros[session['player_id']]['chunks']) + len(clones) < 10:
                chunk['score'] = chunk['score'] / 2
                clones[round(random.random(), 10)] = {'x': chunk['x'], 'y': chunk['y'], 'score': chunk['score'],
                                                      'energy': chunk['score'] ** 0.5, 'time': time.time()}

    heros[session['player_id']]['chunks'] |= clones


def move():
    cr_x, cr_y = 0, 0
    mouse_x, mouse_y = request.args['mouse_x'], request.args['mouse_y']
    mouse_x, mouse_y = (float(mouse_x), float(mouse_y) + 50) if mouse_x != 'NaN' else (0, 0)

    for chunk in heros[session['player_id']]['chunks'].values():
        lng = ((mouse_x - chunk['x']) ** 2 + (mouse_y - chunk['y']) ** 2) ** 0.5
        ang = math.degrees(math.acos((chunk['x'] - mouse_x) / lng))
        ang = ang if mouse_y < chunk['y'] else -ang + 360
        scale = 1 if lng > 100 else lng / 100
        if chunk.get('energy', 0) > 5:
            scale *= chunk['energy'] / 5
            chunk['energy'] = int(chunk['energy'] * 4 / 5)
        elif 'energy' in chunk:
            chunk.pop('energy')

        chunk['x'] -= math.cos(math.radians(ang)) * (3000 / chunk['score']**0.7) * scale
        chunk['y'] -= math.sin(math.radians(ang)) * (3000 / chunk['score']**0.7) * scale
        chunk['x'] = 0 if chunk['x'] < 0 else WIDTH if chunk['x'] > WIDTH else chunk['x']
        chunk['y'] = 0 if chunk['y'] < 0 else HEIGHT if chunk['y'] > HEIGHT else chunk['y']
        cr_x, cr_y = cr_x + chunk['x'], cr_y + chunk['y']

    self_collisions()

    num_chunks = len(heros[session['player_id']]['chunks'])
    heros[session['player_id']]['camera_x'] = cr_x / (num_chunks if num_chunks > 0 else 1)
    heros[session['player_id']]['camera_y'] = cr_y / (num_chunks if num_chunks > 0 else 1)


def self_collisions():
    flag = True
    while flag:
        flag = False
        for c1 in heros[session['player_id']]['chunks'].values():
            for c2 in heros[session['player_id']]['chunks'].values():
                if 'time' in c1 and time.time() - c1['time'] > 30:
                    c1.pop('time')
                if c1.get('energy', 0) > c1['score'] / 5 or c2.get('energy', 0) > c2['score'] / 5:
                    continue
                if c1 != c2 and ('time' in c1 or 'time' in c2):
                    if ((c1['x'] - c2['x'])**2 + (c1['y'] - c2['y'])**2)**0.5 <= c1['score']**0.5 + c2['score']**0.5:
                        flag = True
                        lng = ((c1['x'] - c2['x']) ** 2 + (c1['y'] - c2['y']) ** 2) ** 0.5
                        ang = math.degrees(math.acos((c1['x'] - c2['x']) / (lng if lng > 0 else 1)))
                        ang = ang if c1['y'] < c2['y'] else -ang + 360
                        c2['x'] += math.cos(math.radians(ang)) * (c1['score'] / c2['score'])
                        c2['y'] += math.sin(math.radians(ang)) * (c1['score'] / c2['score'])
                        c1['x'] += math.cos(math.radians(-ang)) * (c2['score'] / c1['score'])
                        c1['y'] += math.sin(math.radians(-ang)) * (c2['score'] / c1['score'])


def get_visible_food():
    w = heros[session['player_id']]['camera_width'] / 2 / heros[session['player_id']]['camera_k']
    h = heros[session['player_id']]['camera_height'] / 2 / heros[session['player_id']]['camera_k']
    center_x, center_y = heros[session['player_id']]['camera_x'], heros[session['player_id']]['camera_y']
    visible_food = {}
    for f_key, f in food.items():
        if center_x - w <= f['x'] <= center_x + w and center_y - h <= f['y'] <= center_y + h:
            visible_food[f_key] = f

    return visible_food


def food_collision(vis_food):
    food_to_del = set()
    for f_key, f in vis_food.items():
        for chunk in heros[session['player_id']]['chunks'].values():
            if (chunk['x'] - f['x']) ** 2 + (chunk['y'] - f['y']) ** 2 < chunk['score']:
                food_to_del.add(f_key)
                chunk['score'] += 20

    for key in food_to_del:
        food.pop(key)


def heros_collision():
    chunks_to_del = set()
    for k1, c1 in heros[session['player_id']]['chunks'].items():
        for key, hero in heros.items():
            for k2, c2 in hero['chunks'].items():
                merge = key == session['player_id'] and 'time' not in c1 and 'time' not in c2 and c1['score'] > c2['score']
                if (key != session['player_id'] and c1['score'] > c2['score'] * 1.1) or merge:
                    if (c1['x'] - c2['x'])**2 + (c1['y'] - c2['y'])**2 < (c1['score']**0.5 - c2['score']**0.5 / 2)**2:
                        chunks_to_del.add((key, k2))
                        c1['score'] += c2['score']

    for key, k in chunks_to_del:
        heros[key]['chunks'].pop(k)


def updater():
    while True:
        if len(food) < 1000:
            for _ in range(30):
                food[round(random.random(), 10)] = ({'x': random.randint(0, WIDTH),
                                                     'y': random.randint(0, HEIGHT),
                                                     'color': random.choice(colors)})

        time.sleep(0.1)


if __name__ == "__main__":
    logging.disable(logging.INFO)
    threading.Thread(target=updater, daemon=True).start()
    app.run(host='0.0.0.0', port=5004)
