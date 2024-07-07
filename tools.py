# tools.py
import threading
from datetime import datetime
from queue import Queue
import json
import sys
import sqlite3


def create_thread(target, args=()):
    thread = threading.Thread(target=target, args=args)
    return thread


def create_queue():
    queue = Queue()
    return queue



