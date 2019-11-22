#!/usr/bin/env python3

import subprocess
import threading
from socket import gethostbyaddr
from collections import namedtuple
from bs4 import BeautifulSoup
from urllib.request import urlopen
from queue import Queue
from flask import Flask
from flask import request

app = Flask(__name__)

YT_URL = r'https://www.youtube.com/watch?v='

RecordType = namedtuple('RecordType', ['title', 'url', 'submitter_host', 'submitter_ip'])

song_queues = dict()
player = None
terminate = False
player_thread = None
now_playing = None

def main_player_loop():
    global player
    global terminate
    global now_playing

    print('Main player loop started')

    terminate = False


    while terminate == False:
        tmp_queues = list(song_queues.items())
        for (tmp_ip, q) in tmp_queues:
            if q.qsize() == 0: # queue for this user is empty, skip
                continue
            try:
                now_playing = q.get(timeout=1)
                song_url = now_playing.url
            except:
                continue

            player = subprocess.Popen(['mpv', '--no-video', song_url])
            player.wait()
            now_playing = None
            player = None
    now_playing = None
    player = None


@app.route('/help')
def help():
    routes = [str(r) for r in app.url_map.iter_rules()]
    return '<br/>'.join(routes)


@app.route('/flush')
def flush_queue():
    tmp_ip = request.remote_addr
    if tmp_ip in song_queues:
        tmp_queue = song_queues[tmp_ip]
        with tmp_queue.mutex:
            tmp_queue.queue.clear()
        return 'queue flushed'
    else:
        return 'No queue for this user'

@app.route('/flush_all')
def flush_all_queues():
    for q in song_queues.values():
        with q.mutex:
            q.queue.clear()
    return 'Flushed all queues'

@app.route('/')
def list_songs():
    output = []

    if now_playing is not None:
        output.append('Now playing: {}   submitted by {}<br/><br/>'.format(now_playing.title, now_playing.submitter_host))
    for (tmp_ip, q) in song_queues.items():
        tmp_hostname = gethostbyaddr(tmp_ip)[0]

        output.append('From {}:'.format(tmp_hostname))

        with q.mutex:
            song_list = q.queue.copy()

        if len(song_list) > 0:
            titoli = [record.title for record in song_list]
            output.extend(titoli)
    return '<br/>'.join(output)


@app.route('/start')
def player_start():
    global player_thread

    if player_thread is None:
        player_thread = threading.Thread(target=main_player_loop)
        player_thread.start()
        return 'player started'
    else:
        return 'player is running already'


@app.route('/skip')
def player_skip():
    global player

    if player is not None:
        player.kill()
        player = None
        return 'DONE'
    return 'nothing is being played'


@app.route('/kill')
def player_kill():
    global player
    global terminate
    global player_thread

    terminate = True
    ret = player_skip()
    player_thread.join()
    player_thread = None
    flush_queue()

    return ret


@app.route('/youtube/<string:ytid>')
def load_youtube(ytid):
    tmp_url = YT_URL + ytid
    tmp_title = BeautifulSoup(urlopen(tmp_url), 'lxml').title.string
    tmp_submitter_ip = request.remote_addr
    tmp_submitter = gethostbyaddr(tmp_submitter_ip)[0]

    if tmp_title == 'YouTube':
        return 'Invalid youtube id {}'.format(ytid)

    if tmp_submitter_ip not in song_queues:
        q = Queue()
        song_queues[tmp_submitter_ip] = q
    else:
        q = song_queues[tmp_submitter_ip]

    tmp_record = RecordType(title=tmp_title, url=tmp_url, submitter_host=tmp_submitter, submitter_ip=tmp_submitter_ip)
    q.put(tmp_record)
    elements = q.qsize()
    return '{}<br/>{}<br/>Queue size:{}'.format(tmp_title, tmp_submitter, elements)


if __name__ == '__main__':
    player_thread = threading.Thread(target=main_player_loop)
    player_thread.start()
    app.run(host='0.0.0.0')
