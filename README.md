aw-importer-lastfm
==================

This extension imports data from [lastfm](last.fm) by watching a folder for changes.

You can get an export of your data from this website: https://mainstream.ghan.nl/export.html

This watcher is currently in a early stage of development, please submit PRs if you find bugs!


# Usage

## Step 1: Installation

### Using pipx

```
pipx install https://github.com/RTnhN/aw-importer-lastfm.git
```

### From source

Clone the repo

```
git clone https://github.com/RTnhN/aw-importer-lastfm && cd aw-importer-lastfm
```

Install the requirements:

```sh
pip install .
```

First run (generates empty config that you need to fill out):
```sh
python aw-importer-lastfm/main.py
```

## Step 2: Enter config

You will need to add the path to the folder where you will add the csv files from lastfm. You can also update the polling time. Since there is no listening duration data, you will need to specify a default duration for the events.

## Step 3: Add the csv export to the folder

## Step 4: Restart the server and enable the watcher

Note: it might take a while to churn though all the data the first time or two depending on how long you have been using lastfm. Once it is imported, it will not re-import the file (it will change the name of imported files) or re-import individual events since unique ids are given to the events based on the song name, timestamp, album, and artist.


