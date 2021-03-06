#!/usr/bin/env python3
import sys
import re
import socket
import struct
import subprocess
import jsonpickle
from gi.repository import GLib
from enum import Enum
from msg import Msg,Urgency

def linesplit(socket):
    buffer = socket.recv(16)
    buffer = buffer.decode("UTF-8")
    buffering = True
    while buffering:
        if '\n' in buffer:
            (line, buffer) = buffer.split("\n", 1)
            yield line
        else:
            more = socket.recv(16)
            more = more.decode("UTF-8")
            if not more:
                buffering = False
            else:
                buffer += more
    if buffer:
        yield buffer
msg = "<span color='green'><i>Delete</i>:    Dismiss notification.\n<i>Alt+Enter</i>: Mark notification seen.\n<i>Alt+r</i>      Reload</span>";
rofi_command = [ 'rofi' , '-dmenu', '-p', 'Notifications:', '-markup', '-mesg', msg]

def strip_tags(value):
  "Return the given HTML with all tags stripped."
  return re.sub(r'<[^>]*?>', '', value)

def call_rofi(entries, additional_args=[]):
    additional_args.extend([ '-kb-custom-1', 'Delete',
                             '-kb-custom-2', 'Alt+Return',
                             '-kb-custom-3', 'Alt+r',
                             '-markup-rows',
                             '-sep', '\\0',
                             '-format', 'i',
                             '-eh', '2' ])
    proc = subprocess.Popen(rofi_command+ additional_args,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    for e in entries:
        proc.stdin.write((e).encode('utf-8'))
        proc.stdin.write(struct.pack('B', 0))
    proc.stdin.close()
    answer = proc.stdout.read().decode("utf-8")
    exit_code = proc.wait()
    # trim whitespace
    if answer == '':
        return None,exit_code
    else:
        return int(answer),exit_code


def send_command(cmd):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect("/tmp/rofi_notification_daemon")
    print("Send: {cmd}".format(cmd=cmd))
    client.send(bytes(cmd, 'utf-8'))
    client.close()


did = None
cont=True
while cont:
    cont=False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect("/tmp/rofi_notification_daemon")
    client.send(b"list",4)
    ids=[]
    entries=[]
    index=0
    urgent=[]
    low=[]
    args=[]
    for a in linesplit(client):
        if len(a) > 0:
            msg = jsonpickle.decode(a)
            ids.append(msg)
            mst = ("<b>{summ}</b> <small>({app})</small>\n<i>{body}</i>".format(
                   summ=GLib.markup_escape_text(strip_tags(msg.summary)),
                   app=GLib.markup_escape_text(strip_tags(msg.application)),
                   body=GLib.markup_escape_text(strip_tags(msg.body.replace("\n"," ")))))
            entries.append(mst)
            if Urgency(msg.urgency) is Urgency.critical:
                urgent.append(str(index))
            if Urgency(msg.urgency) is Urgency.low:
                low.append(str(index))
            index+=1
    if len(urgent):
        args.append("-u")
        args.append(",".join(urgent))
    if len(low):
        args.append("-a")
        args.append(",".join(low))

    # Select previous selected row.
    if did != None:
        args.append("-selected-row")
        args.append(str(did))
    # Show rofi
    did,code = call_rofi(entries,args)
    # Dismiss notification
    if did != None and code == 10:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect("/tmp/rofi_notification_daemon")
        send_command("del:{mid}".format(mid=ids[did].mid))
        cont=True
    # Seen notification
    elif did != None and code == 11:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect("/tmp/rofi_notification_daemon")
        send_command("saw:{mid}".format(mid=ids[did].mid))
        cont=True
    elif did != None and code == 12:
        cont=True
