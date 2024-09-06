#!/usr/bin/env python3

import sys
from pathlib import Path
import logging
import csv
from time import sleep
from datetime import datetime, timedelta

from aw_core import dirs
from aw_core.models import Event
from aw_client.client import ActivityWatchClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCHER_NAME = "aw-importer-lastfm"

logger = logging.getLogger(WATCHER_NAME)
DEFAULT_CONFIG = f"""
[{WATCHER_NAME}]
data_path = ""
default_duration = 60
"""


def parse_and_add_data(aw, bucket_name, path, default_duration):
    already_logged_events = set(
        event["data"]["uid"] for event in aw.get_events(bucket_name)
    )
    added_logs = 0
    batch_events = []  # For batch processing

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            try:
                uts, timestamp_raw, artist, album, track = (
                    row[0].strip(),
                    row[1].strip(),
                    row[2].strip(),
                    row[4].strip(),
                    row[6].strip(),
                )
                title = f"{track} by {artist} on {album}"
                uid = uts + artist + album + track
                seconds = datetime.fromtimestamp(int(uts)).second
                timestamp = datetime.strptime(timestamp_raw, "%d %b %Y, %H:%M")
                timestamp_with_seconds = timestamp + timedelta(seconds=seconds)
                timestamp_with_seconds_iso = timestamp_with_seconds.isoformat()
                if uid not in already_logged_events:
                    data = {
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "track": track,
                        "uid": uid,
                    }
                    new_event = Event(
                        timestamp=timestamp_with_seconds_iso,
                        duration=int(default_duration),
                        data=data,
                    )
                    batch_events.append(new_event)
                    added_logs += 1
            except Exception:
                print(f"There was a problem with the following row: {row}")
                continue

        # Batch insert if supported
        if batch_events:
            aw.insert_events(bucket_name, batch_events)

        print_statusline(f"Added {added_logs} item(s)")


def load_config():
    from aw_core.config import load_config_toml as _load_config

    return _load_config(WATCHER_NAME, DEFAULT_CONFIG)


def print_statusline(msg):
    last_msg_length = (
        len(print_statusline.last_msg) if hasattr(print_statusline, "last_msg") else 0
    )
    print(" " * last_msg_length, end="\r")
    print(msg, end="\r")
    print_statusline.last_msg = msg


class CSVFileHandler(FileSystemEventHandler):
    """Custom event handler for watchdog to process new or modified CSV files."""

    def __init__(self, aw, bucket_name, data_path, default_duration):
        self.aw = aw
        self.bucket_name = bucket_name
        self.data_path = data_path
        self.default_duration = default_duration

    def on_created(self, event):
        """Called when a new file or folder is created."""
        self.process(event)

    def process(self, event):
        """Process the file if it's a CSV that hasn't been imported yet."""
        if not event.is_directory and event.src_path.endswith(".csv"):
            file_path = Path(event.src_path)
            if not file_path.stem.endswith("_imported"):
                parse_and_add_data(
                    self.aw, self.bucket_name, file_path, self.default_duration
                )
                file_path.rename(
                    self.data_path
                    / Path(file_path.stem + "_imported" + file_path.suffix)
                )


def main():
    logging.basicConfig(level=logging.INFO)

    config_dir = dirs.get_config_dir(WATCHER_NAME)
    config = load_config()
    data_path = config[WATCHER_NAME].get("data_path", "")
    default_duration = int(config[WATCHER_NAME].get("default_duration", 0))

    if not data_path:
        logger.warning(
            """You need to specify the folder that has the data files.
                       You can find the config file here:: {}""".format(
                config_dir
            )
        )
        sys.exit(1)

    if default_duration == 0:
        logger.warning(
            """You need to specify a default duration for the events.
                       You can find the config file here:: {}""".format(
                config_dir
            )
        )
        sys.exit(1)

    aw = ActivityWatchClient(WATCHER_NAME, testing=False)
    bucket_name = "{}_{}".format(aw.client_name, aw.client_hostname)
    if aw.get_buckets().get(bucket_name) == None:
        aw.create_bucket(bucket_name, event_type="lifecycle_data", queued=True)
    aw.connect()

    # Set up watchdog observer
    event_handler = CSVFileHandler(aw, bucket_name, Path(data_path), default_duration)
    observer = Observer()
    observer.schedule(event_handler, data_path, recursive=True)
    observer.start()

    try:
        while True:
            sleep(1)  # Keep the script running
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
