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

WATCHER_NAME = "aw-importer-lastfm"


logger = logging.getLogger(WATCHER_NAME)
DEFAULT_CONFIG = f"""
[{WATCHER_NAME}]
data_path = ""
poll_time = 60.0
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

        print_statusline(f"Added {added_logs} items(s)")


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


def main():

    logging.basicConfig(level=logging.INFO)

    config_dir = dirs.get_config_dir(WATCHER_NAME)

    config = load_config()
    poll_time = float(config[WATCHER_NAME].get("poll_time"))
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

    # TODO: Fix --testing flag and set testing as appropriate
    aw = ActivityWatchClient(WATCHER_NAME, testing=False)
    bucket_name = "{}_{}".format(aw.client_name, aw.client_hostname)
    if aw.get_buckets().get(bucket_name) == None:
        aw.create_bucket(bucket_name, event_type="lifecycle_data", queued=True)
    aw.connect()

    while True:
        data_path = Path(data_path)
        files = list(data_path.glob("*.csv"))
        unimported_files = [
            file for file in files if not file.stem.endswith("_imported")
        ]

        for unimported_file in unimported_files:
            file_path = data_path / unimported_file
            parse_and_add_data(aw, bucket_name, file_path, default_duration)
            file_path.rename(
                data_path / Path(file_path.stem + "_imported" + file_path.suffix)
            )
        sleep(poll_time)


if __name__ == "__main__":
    main()
