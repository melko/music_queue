#!/usr/bin/env python3

import threading
import pickle
import copy
import mpv
import time
from lxml.html import parse as parse_html
from socket import gethostbyaddr
from collections import namedtuple
from urllib.request import urlopen
from queue import Queue
from flask import Flask
from flask import request

app = Flask(__name__)

YT_URL = r'https://www.youtube.com/watch?v='
SKIP_THRESHOLD = 3
QUEUE_FILE = 'music_queue.dat'

RecordType = namedtuple('RecordType', ['title', 'url', 'submitter_host', 'submitter_ip'])

song_queues = dict()
skip_requests = set()
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

    if player is None:
        player = mpv.MPV(video=False, ytdl=True)


    while terminate == False:
        tmp_queues = reversed(list(song_queues.items()))
        for (tmp_ip, q) in tmp_queues:
            if terminate == True:
                break
            if q.qsize() == 0: # queue for this user is empty, skip
                continue
            try:
                now_playing = q.get(timeout=1)
                song_url = now_playing.url
            except:
                continue

            player.play(song_url)
            player.wait_for_playback()
            skip_requests.clear()
            dump_queue()
            now_playing = None
        time.sleep(1)
    now_playing = None
    skip_requests.clear()


def dump_queue():
    file = open(QUEUE_FILE, 'wb')
    tmp_dump = dict()

    for (tmp_ip, q) in song_queues.items():
        with q.mutex:
            tmp_dump[tmp_ip] = q.queue.copy()
    pickle.dump(tmp_dump, file)
    file.close()


def restore_queue():
    global song_queues

    try:
        file = open(QUEUE_FILE, 'rb')
    except:
        print('Nothing to restore')
        return

    try:
        tmp_dict = pickle.load(file)
    except:
        print('Failed restoring queue')
        tmp_dict = dict()
    file.close()

    for (tmp_ip, q) in tmp_dict.items():
        song_queues[tmp_ip] = Queue()
        song_queues[tmp_ip].queue.extend(q)


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
        output.append('Now playing: {} &emsp; submitted by {}'.format(now_playing.title, now_playing.submitter_host))
        if player is not None:
            output.append('Duration: {}/{}s - Volume: {}% - Paused: {}<br/><br/>'.format(int(player.time_pos), int(player.duration), player.volume, player.pause))
    for (tmp_ip, q) in song_queues.items():
        tmp_hostname = gethostbyaddr(tmp_ip)[0]

        output.append('From {}:'.format(tmp_hostname))

        with q.mutex:
            song_list = q.queue.copy()

        if len(song_list) > 0:
            titoli = ['&emsp; ' + record.title for record in song_list]
            output.extend(titoli)
    return '<br/>'.join(output)


@app.route('/volume/<int:v>')
def set_volume(v):
    if player is None:
        return 'Start player first'
    if v < 0 or v > 100:
        return 'Invalid value'
    player.volume = v
    return 'Volume set to {}'.format(v)

@app.route('/start')
def player_start():
    global player_thread

    if player_thread is None:
        restore_queue()
        player_thread = threading.Thread(target=main_player_loop)
        player_thread.start()
        return 'player started'
    else:
        return 'player is running already'


@app.route('/skip')
def player_skip():
    global player

    if player is not None and now_playing is not None:
        tmp_ip = request.remote_addr
        skip_requests.add(tmp_ip)
        if len(skip_requests) >= SKIP_THRESHOLD or tmp_ip == now_playing.submitter_ip:
            player.playlist_remove()
            return 'DONE'
        else:
            return 'skip counter increased to {}'.format(len(skip_requests))
    return 'nothing is being played'


@app.route('/pause')
def player_toggle_pause():
    global player

    if player is not None:
        player.pause = not player.pause
        return 'PAUSE set to {}'.format(player.pause)
    return 'no player found'


@app.route('/kill')
def player_kill():
    global player
    global terminate
    global player_thread

    terminate = True
    if player is not None:
        player.terminate()
        player = None
    #ret = player_skip()
    if player_thread is not None:
        player_thread.join()
        player_thread = None

    # killing twice remove the dump this way
    dump_queue()
    flush_queue()

    return 'killed'


@app.route('/remove/<int:n>')
def remove_song(n):
    tmp_submitter_ip = request.remote_addr

    if tmp_submitter_ip not in song_queues:
        return 'no queue for this ip'

    q = song_queues[tmp_submitter_ip]
    with q.mutex:
        try:
            tmp_record = q.queue[n]
        except IndexError:
            return 'No song found at position {}'.format(n)
        return_string = '{} &emsp removed from the queue'.format(tmp_record.title)
        del q.queue[n]
    return return_string

@app.route('/youtube/<string:ytid>')
def load_youtube(ytid):
    tmp_url = YT_URL + ytid
    tmp_title = parse_html(urlopen(tmp_url)).find('.//title').text
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

    dump_queue()
    return '{}<br/>{}<br/>Queue size:{}'.format(tmp_title, tmp_submitter, elements)


if __name__ == '__main__':
    player_thread = threading.Thread(target=main_player_loop)
    restore_queue()
    player_thread.start()
    app.run(host='0.0.0.0')
