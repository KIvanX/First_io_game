import threading

from flask import Flask, render_template, request, session
import json
import time
import math
import random

app = Flask(__name__)
app.secret_key = '123456'
heros = {}
food = {}
colors = ['red', 'green', 'blue', 'yellow', 'violet']
WIDTH, HEIGHT = 3000, 2000


@app.route("/", methods=['POST', 'GET'])
def index():
    if session.get('player_id', 0) in heros:
        heros.pop(session['player_id'])
    return render_template("index.html")


@app.route("/init")
def init():
    session['player_id'] = round(random.random(), 10)
    chunk_id, x, y = round(random.random(), 10), random.randint(0, WIDTH), random.randint(0, HEIGHT)
    heros[session['player_id']] = {'chunks': {chunk_id: {'x': x, 'y': y, 'score': 150}},
                                   'camera_x': x,
                                   'camera_y': y,
                                   'color': random.choice(colors),
                                   'last_update': time.time(),
                                   'window_width': request.args.get('width'),
                                   'window_height': request.args.get('height'),
                                   'name': request.args.get('name')}
    return {'self_id': session['player_id']}


@app.route("/update")
def update():
    if 'player_id' not in session or session['player_id'] not in heros or not heros[session['player_id']]['chunks']:
        return {'status': 'reload'}

    heros[session['player_id']]['last_update'] = time.time()

    separation()
    move()
    vis_food = get_visible_food()
    food_collision(vis_food)
    heros_collision()

    return json.dumps({'heros': heros, 'food': vis_food, 'status': 'OK'})


def separation():
    clones = {}
    if request.args.get('is_jump') == 'true':
        for chunk in heros[session['player_id']]['chunks'].values():
            if chunk['score'] > 50 and len(heros[session['player_id']]['chunks']) + len(clones) < 10:
                chunk['score'] = chunk['score'] / 2**0.5
                clones[round(random.random(), 10)] = {'x': chunk['x'], 'y': chunk['y'], 'score': chunk['score'],
                                                      'energy': chunk['score'] // 2, 'time': time.time()}

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
        if chunk.get('energy', 0) > 0:
            scale *= chunk['energy'] / 5
            chunk['energy'] = int(chunk['energy'] * 4 / 5)
        elif 'energy' in chunk:
            chunk.pop('energy')

        chunk['x'] -= math.cos(math.radians(ang)) * (1500 / chunk['score']) * scale
        chunk['y'] -= math.sin(math.radians(ang)) * (1500 / chunk['score']) * scale
        chunk['x'] = 0 if chunk['x'] < 0 else WIDTH if chunk['x'] > WIDTH else chunk['x']
        chunk['y'] = 0 if chunk['y'] < 0 else HEIGHT if chunk['y'] > HEIGHT else chunk['y']
        cr_x, cr_y = cr_x + chunk['x'], cr_y + chunk['y']

    self_collisions()

    num_chunks = len(heros[session['player_id']]['chunks'])
    heros[session['player_id']]['camera_x'] = cr_x / (num_chunks if num_chunks > 0 else 1)
    heros[session['player_id']]['camera_y'] = cr_y / (num_chunks if num_chunks > 0 else 1)


def self_collisions():
    try:
        flag = True
        while flag:
            flag = False
            for c1 in heros[session['player_id']]['chunks'].values():
                for c2 in heros[session['player_id']]['chunks'].values():
                    if 'time' in c1 and time.time() - c1['time'] > 20:
                        c1.pop('time')
                    if c1.get('energy', 0) > c1['score'] / 5 or c2.get('energy', 0) > c2['score'] / 5:
                        continue
                    if c1 != c2 and ('time' in c1 or 'time' in c2):
                        if ((c1['x'] - c2['x']) ** 2 + (c1['y'] - c2['y']) ** 2) ** 0.5 <= c1['score'] + c2['score']:
                            flag = True
                            lng = ((c1['x'] - c2['x']) ** 2 + (c1['y'] - c2['y']) ** 2) ** 0.5
                            ang = math.degrees(math.acos((c1['x'] - c2['x']) / (lng if lng > 0 else 1)))
                            ang = ang if c1['y'] < c2['y'] else -ang + 360
                            c2['x'] += math.cos(math.radians(ang)) * (c1['score'] / c2['score'])
                            c2['y'] += math.sin(math.radians(ang)) * (c1['score'] / c2['score'])
                            c1['x'] += math.cos(math.radians(-ang)) * (c2['score'] / c1['score'])
                            c1['y'] += math.sin(math.radians(-ang)) * (c2['score'] / c1['score'])
    except:
        return 0


def get_visible_food():
    w, h = int(heros[session['player_id']]['window_width']) / 2, int(heros[session['player_id']]['window_height']) / 2
    center_x, center_y = heros[session['player_id']]['camera_x'], heros[session['player_id']]['camera_y']
    visible_food = {}
    for f_key, f in food.items():
        if center_x - w <= f['x'] <= center_x + w and center_y - h <= f['y'] <= center_y + h:
            visible_food[f_key] = f

    return visible_food


def food_collision(vis_food):
    try:
        food_to_del = set()
        for f_key, f in vis_food.items():
            for chunk in heros[session['player_id']]['chunks'].values():
                if (chunk['x'] - f['x']) ** 2 + (chunk['y'] - f['y']) ** 2 < chunk['score'] ** 2:
                    food_to_del.add(f_key)
                    chunk['score'] = (chunk['score']**2 + 20)**0.5

        for key in food_to_del:
            food.pop(key)
    except:
        return 0


def heros_collision():
    chunks_to_del = set()
    for k1, c1 in heros[session['player_id']]['chunks'].items():
        for key, hero in heros.items():
            for k2, c2 in hero['chunks'].items():
                ready = 'time' not in c1 and 'time' not in c2
                if (key != session['player_id'] or ready) and c1['score'] > c2['score']:
                    if (c1['x'] - c2['x']) ** 2 + (c1['y'] - c2['y']) ** 2 < (c1['score'] / 2 + c2['score'] / 4) ** 2:
                        chunks_to_del.add((key, k2))
                        c1['score'] = (c1['score']**2 + c2['score']**2)**0.5

    for key, k in chunks_to_del:
        heros[key]['chunks'].pop(k)


def updater():
    while True:
        if len(food) < 2000:
            for _ in range(30):
                food[round(random.random(), 10)] = ({'x': random.randint(0, WIDTH),
                                                     'y': random.randint(0, HEIGHT),
                                                     'color': random.choice(colors)})

        to_del = []
        for key in heros:
            if time.time() - heros[key]['last_update'] > 1:
                to_del.append(key)

        for key in to_del:
            heros.pop(key)

        time.sleep(0.1)


if __name__ == "__main__":
    threading.Thread(target=updater, daemon=True).start()
    app.run(host='0.0.0.0', debug=True)
