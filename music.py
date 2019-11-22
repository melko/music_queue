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

song_queue = Queue()
player = None
terminate = False
player_thread = None

def main_player_loop():
    global player
    global terminate

    print('Main player loop started')

    terminate = False


    while terminate == False:
        try:
            tmp_record = song_queue.get(timeout=1)
            song_url = tmp_record.url
        except:
            pass
        else:
            player = subprocess.Popen(['mpv', '--no-video', song_url])
            player.wait()
            player = None
    player = None


@app.route('/help')
def help():
    routes = [str(r) for r in app.url_map.iter_rules()]
    return '<br/>'.join(routes)


@app.route('/flush')
def flush_queue():
    with song_queue.mutex:
        song_queue.queue.clear()
    return 'queue flushed'

@app.route('/')
def list_songs():
    with song_queue.mutex:
        song_list = song_queue.queue.copy()

    if len(song_list) > 0:
        titoli = [record.title + '     submitted from ' + record.submitter_host for record in song_list]
        return '<br/>'.join(titoli)
    else:
        return 'Queue is empty'


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
    tmp_submitter = gethostbyaddr(request.remote_addr)[0]

    if tmp_title == 'YouTube':
        return 'Invalid youtube id {}'.format(ytid)

    tmp_record = RecordType(title=tmp_title, url=tmp_url, submitter_host=tmp_submitter, submitter_ip=request.remote_addr)
    song_queue.put(tmp_record)
    elements = song_queue.qsize()
    return '{}<br/>{}<br/>Queue size:{}'.format(tmp_title, tmp_submitter, elements)


if __name__ == '__main__':
    player_thread = threading.Thread(target=main_player_loop)
    player_thread.start()
    app.run(host='0.0.0.0')
