import pandas as pd
import numpy as np
import json
import spotipy
import re
import requests
import time
import os
import string
import traceback
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List 

class FeatureExtractor: 

    def __init__(self, spotify_client_id: str, spotify_client_secret: str, 
                 playlist_url: str, lastfm_api_key: str, lastfm_username: str, 
                 discovery_api_key: str, features_filename: str):
        
        auth_manager = SpotifyClientCredentials(client_id=spotify_client_id,
                                                client_secret=spotify_client_secret)
        self.SPOTIFY = spotipy.Spotify(auth_manager=auth_manager)

        self.playlist_url = playlist_url
        self.lastfm_api_key = lastfm_api_key
        self.lastfm_username = lastfm_username
        self.discovery_api_key = discovery_api_key

        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_expiry = timedelta(days=7)
        self.cache_lock = Lock()

        self.features_filename = features_filename

    # TODO
    def _save_cache(self, cache, cache_file):

        cache_path = os.path.join(self.cache_dir, cache_file)

        with open(cache_path, "w") as f:
            json.dump(cache, f)

        print(f"_save_cache: {len(cache)} items saved to cache {cache_file}.")

    # TODO
    def _load_cache(self, cache_file):

        cache_path = os.path.join(self.cache_dir, cache_file)

        if os.path.exists(cache_path):

            with open(cache_path, "r") as f:

                cache = json.load(f)
                current_time = datetime.now().timestamp()

                return {k: v for k, v in cache.items() 
                        if v.get("timestamp", 0) + self.cache_expiry.total_seconds() > current_time}
        
        return {}
    
    def _get_spotify_features(self, artist_dicts: List[dict]) -> List[dict]:

        """Filters dicts of artist info for the desired Spotify features."""

        features = []

        for artist_dict in artist_dicts: 

            features.append({"name": artist_dict.get("name", "").lower(),
                             "uri": artist_dict.get("uri", ""),
                             "genres": artist_dict.get("genres", []),
                             "albums": artist_dict.get("albums", 0),
                             'tracks': artist_dict.get("tracks", 0),
                             'last_album_date': artist_dict.get("last_album_date", ""),
                             'first_album_date': artist_dict.get("first_album_date", ""),
                             "popularity": artist_dict.get("popularity", 0),
                             "followers": artist_dict.get("followers", {}).get("total", 0),
                             "playlist_count": artist_dict.get("playlist_count", 0),
                             "spotify_url": artist_dict.get("external_urls", {}).get("spotify", ""),
                             "image_320": artist_dict.get("images", [])[1].get("url", "") if artist_dict.get("images", []) else []
            })

        print(f"_get_spotify_features: Spotify features collected for {len(features)} artists.")
        return features
    
    def _generate_discog_features(self, artist_dicts) -> List[dict]:

        """Propagates discography features (number of albums, number of tracks, 
           album release dates) for artists."""

        spotify_cache = self._load_cache("spotify_discog_cache.json")

        def fetch_discog(artist_dict): 

            if not artist_dict:
                return None
            
            artist_name = artist_dict["name"]
            cache_key = artist_name.lower()
            uri = artist_dict.get("uri", None)

            if cache_key in spotify_cache: 
                return spotify_cache[cache_key]["data"]
            
            try: 
                time.sleep(0.2)
                # album info
                albums = self.SPOTIFY.artist_albums(uri, include_groups="album") if uri else {"total": 0, "items": []}
                # number of albums
                artist_dict["albums"] = albums["total"]
                album_items = albums["items"]
                # note that track count only includes tracks from albums, meaning that:
                    # singles outside albums are not accounted for
                    # tracks are counted twice if a deluxe version of a album is released
                artist_dict["tracks"] = sum(album["total_tracks"] for album in album_items)
                artist_dict["last_album_date"] = album_items[0]["release_date"] if album_items else None
                artist_dict["first_album_date"] = album_items[-1]["release_date"] if album_items else None
                
                with self.cache_lock:
                    spotify_cache[cache_key] = {"data": artist_dict, "timestamp": datetime.now().timestamp()}
                
                return artist_dict

            except Exception as e:
                print(f"_generate_discog_features: Error obtaining Spotify discography features for artist {artist_name}; {e}.")
                artist_dict["albums"] = 0
                artist_dict["tracks"] = 0
                artist_dict["last_album_date"] = None
                artist_dict["first_album_date"] = None

                with self.cache_lock: 
                    spotify_cache[cache_key] = {"data": artist_dict, "timestamp": datetime.now().timestamp()}
                
                return artist_dict
            
        all_artist_info = []
        # for artist_dict in artist_dicts: 
        #     all_artist_info.append(fetch_discog(artist_dict))

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_artist = {executor.submit(fetch_discog, artist_dict): artist_dict for artist_dict in artist_dicts}
            for future in as_completed(future_to_artist):
                result = future.result()
                if result:
                    all_artist_info.append(result)

        self._save_cache(spotify_cache, "spotify_discog_cache.json")
        print(f"_generate_discog_features: discography features generated for {len(all_artist_info)} artists.")
        return all_artist_info
    
    def _get_playlist_artists(self) -> List[dict]: 

        """Retrieves artist-level data for each unique artist in the provided 
           playlist."""    

        # grab tracks in playlist
        time.sleep(0.2)
        response = self.SPOTIFY.playlist_tracks(self.playlist_url, offset=0)
        # considering only the primary artist of each track
        artists = [track["track"]["artists"][0] for track in response["items"]]
        # artists = [artist_dict for track in response["items"] 
        #            for artist_dict in track["track"]["artists"]]
        # total number of tracks on playlist - needed to determine the number 
        # of loops (max tracks per req. is 100)
        total = response["total"]

        # for larger playlists, multiple requests need to be made to fetch all tracks
        for offset in range(100, total + 1, 100): 
            response = self.SPOTIFY.playlist_tracks(self.playlist_url, offset=offset)
            artists += [track["track"]["artists"][0] for track in response["items"]]
            # artists += [artist_dict for track in response["items"] 
            #             for artist_dict in track["track"]["artists"]]
        
        # set of unique names and URIs
        artist_identifiers = set([(artist["name"].lower(), 
                                   artist["uri"]) for artist in artists])
        all_artist_info = []

        spotify_cache = self._load_cache("spotify_artist_cache.json")
        
        def fetch_artist(uri, name):

            if name in spotify_cache:

                return spotify_cache[name]["data"]
            
            try:
                artist_info = self.SPOTIFY.artist(uri)
                artist_count = sum(1 for artist_dict in artists if artist_dict["uri"] == uri)
                artist_info["playlist_count"] = artist_count
                spotify_cache[name.lower()] = {"data": artist_info, "timestamp": datetime.now().timestamp()}

                return artist_info
            
            except Exception as e:
                print(f"_get_playlist_artists: Error for URI {uri}: {e}")
                return None

        # for (name, uri) in artist_identifiers: 
        #     all_artist_info.append(fetch_artist(uri, name))

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_artist = {executor.submit(fetch_artist, uri, name): (name, uri) for (name, uri) in artist_identifiers}
            for future in as_completed(future_to_artist):
                result = future.result()
                if result:
                    all_artist_info.append(result)

        self._save_cache(spotify_cache, "spotify_artist_cache.json")
        print(f"_get_playlist_artists: information retrieved for {len(artist_identifiers)} artists.")
        
        all_artist_info = self._generate_discog_features(all_artist_info)
        return self._get_spotify_features(all_artist_info)
    
    def _get_spotify_artist_by_search(self, artist_names: List[str]) -> List[dict]:

        """Retrieves artist-level Spotify features for a list of provided artist names 
           using Spotify's search function. For each query, the first match is returned.
           This should be used for any artist whose URI us unknown (i.e. they are 
           not in the playlist)."""

        spotify_cache = self._load_cache("spotify_artist_cache.json")

        def fetch_search(artist_name):

            cache_key = artist_name.lower()
            if cache_key in spotify_cache: 
                return spotify_cache[cache_key]["data"]

            try: 
                time.sleep(0.2)
                artist_info = self.SPOTIFY.search(q=artist_name, 
                                                  type="artist").get("artists", {}).get("items", [])[0]
                
                artist_info["playlist_count"] = 0
                spotify_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}

                return artist_info
            
            except Exception as e: 
                
                print(f"_get_spotify_artist_by_search: no artist found for query {artist_name}; error {e}.")
                return {"name": cache_key, "uri": "", "genres": [], 
                        "popularity": 0, "followers": {"total": 0}, "playlist_count": 0}
        
        searched_artists = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_artist = {executor.submit(fetch_search, name): name for name in artist_names if name}
            for future in as_completed(future_to_artist):
                result = future.result()
                if result:
                    searched_artists.append(result)

        # for artist_name in artist_names:
           
        #     searched_artists.append(fetch_search(artist_name))
        
        self._save_cache(spotify_cache, "spotify_artist_cache.json")
        
        searched_artists = self._generate_discog_features(searched_artists)
        return self._get_spotify_features(searched_artists)
    
    def _get_lastfm_features(self, artist_names: List[str]) -> List[dict]: 

        """Retrieves Lastfm features for a list of artist names."""

        lastfm_cache = self._load_cache("lastfm_cache.json")

        def fetch_lastfm(artist_name):

            cache_key = artist_name.lower()
            if cache_key in lastfm_cache:
                return lastfm_cache[cache_key]["data"]
            
            url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&username={self.lastfm_username}&api_key={self.lastfm_api_key}&format=json"

            try: 
                response = requests.get(url).json()["artist"]
                artist_info = {"name": artist_name.lower(),
                               "lastfm_listeners": response.get("stats", {}).get("listeners", 0),
                               "lastfm_playcount": response.get("stats", {}).get("playcount", 0),
                               "personal_playcount": response.get("stats", {}).get("userplaycount", 0),
                               "lastfm_tags": [tag["name"] for tag in response.get("tags", {}).get("tag", [])],
                               "summary": response.get("bio", {}).get("summary", "")}
                lastfm_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}
                return artist_info

            except Exception as e: 
                print(f"Artist {artist_name} not found on lastfm.")
                artist_info = {"name": artist_name.lower(), 
                               "lastfm_listeners": 0, 
                               "lastfm_playcount": 0, 
                               "personal_playcount": 0, 
                               "lastfm_tags": [], 
                               "summary": ""}
                lastfm_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}
                return artist_info
        
        artists_info = []
        
        # for artist_name in artist_names: 
        #     artists_info.append(fetch_lastfm(artist_name))

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_artist = {executor.submit(fetch_lastfm, name): name for name in artist_names}
            for future in as_completed(future_to_artist):
                result = future.result()
                if result:
                    artists_info.append(result)

        self._save_cache(lastfm_cache, "lastfm_cache.json")

        print(f"_get_lastfm_features: Lastfm features retrieved for {len(artists_info)} artists.")
        return artists_info
    
    def _get_similar_artists(self, artist_names: List[str]) -> dict[str]:

        """Retreives for each artist a list of the top ten similar artists (artist_name, similarity_score)
           from Lastfm. 
           
           Notes:
           - Spotify has deprecated its similar artists endpoint; otherwise, I would use that primarily.
           - I am making the assumption that Lastfm is already taking into account features such as 
             shared genres, listeners (collaborative filtering of some form), and tags. My intention is 
             to build upon that.
           - Some artists, strangely, yield no similar artists via API call, even if they do have similar
             artists if I search manually on the website. Spelling mistakes are not the issue.
           """

        lastfm_cache = self._load_cache("lastfm_similar_cache.json")

        def fetch_similar(artist_name):

            cache_key = artist_name.lower()
            if cache_key in lastfm_cache: 
                return lastfm_cache[cache_key]["data"]
            
            artist_name_formatted = "+".join(artist_name.split()).lower()
            # set limit if needed
            url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name_formatted}&api_key={self.lastfm_api_key}&format=json"

            try: 
                response = requests.get(url).json().get("similarartists", {}).get("artist", [])
                # tuples of (artist, similarity score)
                similar_artists = [(artist["name"].lower(), artist["match"]) for artist in response]
                lastfm_cache[cache_key] = {"data": similar_artists, "timestamp": datetime.now().timestamp()}
                return similar_artists
            
            except Exception as e: 
                print(f"_get_similar_artists: Error fetching similar artists for artist {artist_name}: {e}")
                lastfm_cache[cache_key] = {"data": [], "timestamp": datetime.now().timestamp()}
                return []

        similar_artists = {}
        # for artist_name in artist_names: 
        #     similar_artists[artist_name] = fetch_similar(artist_name)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for name in artist_names:
                future_to_artist = {executor.submit(fetch_similar, name)}
                for future in as_completed(future_to_artist):
                    result = future.result()
                    if result:
                        similar_artists[name] = result
        
        self._save_cache(lastfm_cache, "lastfm_similar_cache.json")
        print(f"Similar artists retrieved for {len(similar_artists)} artists.")
        return similar_artists
    
    def _get_artist_events(self, artist_names: List[str]) -> dict[str]:

        """Retrieves upcoming artist events from Ticketmaster's Discovery API.
           Returns a nested dict with artist names as keys, and a nested dict
           of their unique events and their dates, classifications, and
           attractions (co-performers)."""

        ticketmaster_cache = self._load_cache("ticketmaster_cache.json")

        def fetch_events(artist_name):

            cache_key = artist_name.lower()
            if cache_key in ticketmaster_cache: 
                return ticketmaster_cache[cache_key]["data"]
            
            artist_name_formatted = "+".join(artist_name.split()).lower()
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={self.discovery_api_key}&classificationName=music&keyword={artist_name_formatted}&sort=date,name,asc&size=20"
            
            try: 
                response = requests.get(url).json()
                events = response.get("_embedded", {}).get("events", [])
                events_compressed = [
                {
                    "name": event.get("name", ""),
                    "dates": event.get("dates", {}),
                    "classifications": event.get("classifications", []),
                    "attractions": [
                        {"name": attr.get("name", "").lower(), 
                         "type": attr.get("type", "")}
                        for attr in event.get("_embedded", {}).get("attractions", [])
                        if attr.get("type", "") == "attraction" and attr.get("name") != None
                    ]
                } for event in events
                if artist_name.lower() in [attr.get("name", "").lower()
                                   for attr in event.get("_embedded", {}).get("attractions", [])]]
                
                # group events with the same name together to avoid iterating repetitively
                event_groups = {}
                for event in events_compressed: 
                    event_name = event.get("name", "").lower()
                    event_name = event_name.translate(str.maketrans('', '', string.punctuation))
                    event_groups[event_name] = {"dates": event["dates"], 
                                                "classifications": event["classifications"], 
                                                "attractions": event["attractions"]}
                
                ticketmaster_cache[cache_key] = {"data": event_groups, "timestamp": datetime.now().timestamp()}
                return event_groups
            
            except Exception as e: 
                print(f"_get_artist_events: Error fetching events for artist {artist_name}: {e}; {traceback.format_exc()}.")
                ticketmaster_cache[cache_key] = {"data": {}, "timestamp": datetime.now().timestamp()}
                return {}
        
        artist_events = {}
        # for artist_name in artist_names: 
        #     artist_events[artist_name.lower()] = fetch_events(artist_name)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for name in artist_names:
                future_to_artist = {executor.submit(fetch_events, name)}
                for future in as_completed(future_to_artist):
                    result = future.result()
                    if result:
                        artist_events[name.lower()] = result

        print(f"_get_artist_events: Events fetched for {len(artist_events)} artists.")
        self._save_cache(ticketmaster_cache, "ticketmaster_cache.json")
        return artist_events
    
    def __is_tour(self, event_info): 

        """Helper function that infers whether a specific event is part of 
        an artist tour or a festival."""

        classifications = event_info.get("classifications", [])

        for c in classifications: 

            if c.get("subType", {}).get("name") == "Festival": 
                return False
                
        # if there are more than 5 performers, it's probably a festival 
        # the most openers I've ever heard of for a tour is 3, 4 incl. the headliner
        if len(event_info.get("_embedded", {}).get("attractions", [])) > 5: 
            return False

        return True

    def _get_artist_coperformers(self, artist_names: List[str], 
                                 get_coperformers: bool=False):

        """Returns a list of dictionaries, each corresponding to an artist and containing
           their tour status (str), tour date (datetime.date), tour coperformers (set[str]),
           and festival coperformers (Counter[str])."""
        
        current_date = datetime.now().date()
        # if a tour is 30+ days in the future, it is an upcoming tour
        # any less than that and it is considered a current tour 
        future_threshold = current_date + timedelta(days=30)

        artist_event_groups = self._get_artist_events(artist_names)
        # print(artist_event_groups)

        def fetch_coperformers(artist_name, events):

            tour_coperformers = []
            festival_coperformers = []
            tour_status = "not_touring" 
            tour_date = None

            if len(events) == 0: 
                print(f"fetch_coperformers: NO EVENTS FOR ARTIST {artist_name}")

            for event_name, event in events.items(): 
                
                event_is_tour = self.__is_tour(event)

                if get_coperformers: 
                    event_attractions = [attr["name"].lower() for attr in event.get("attractions", [])]

                    if artist_name.lower() not in event_attractions: 
                        print(f"Skipping events for artist name {artist_name} with attractions {event_attractions}")
                        continue

                    if event_is_tour: 
                        tour_coperformers += event_attractions
                    else:
                        festival_coperformers += event_attractions

                if tour_date == None and event_is_tour: 
                    event_date_str = event["dates"]["start"]["localDate"]
                    tour_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()

            # determine specific tour status
            if tour_date: 
                if tour_date >= future_threshold: 
                    tour_status = "upcoming_tour"
                elif current_date <= tour_date <= future_threshold:
                    tour_status = "on_tour"

            # remove the artist from their own coperformer groups
            tour_coperformers = set(tour_coperformers) - set([artist_name.lower()])
            festival_coperformers = Counter(festival_coperformers)
            festival_coperformers.pop(artist_name.lower(), None)

            artist_tour_data = {
                "name": artist_name.lower(),
                "tour_status": tour_status,
                "tour_date": tour_date,
                "tour_coperformers": tour_coperformers,
                "festival_coperformers": festival_coperformers
            }

            return artist_tour_data

        all_artist_tour_info = []
        for artist_name, events in artist_event_groups.items(): 

            all_artist_tour_info.append(fetch_coperformers(artist_name, events))

        return all_artist_tour_info
    
    def get_all_artist_features(self):

        # start with playlist artists - these are Spotify features
        playlist_spotify_features = self._get_playlist_artists()
        # lowercase names of playlist artists
        playlist_artist_names = [artist.get("name", "") for artist in playlist_spotify_features]
        # lastfm features
        playlist_lastfm_features = self._get_lastfm_features(playlist_artist_names)
        # tour data with coperformers
        playlist_tour_data = self._get_artist_coperformers(playlist_artist_names, get_coperformers=True)
        # get similar artists - note for each artist these are tuples of (name, score)
        similar_artists = self._get_similar_artists(playlist_artist_names)

        # new artists linked to playlist artists
        all_artists = set([tup[0].lower() for artist, tuples in similar_artists.items() 
                           for tup in tuples] + 
                          [co.lower() for coperformers in playlist_tour_data 
                           for co in coperformers["tour_coperformers"]] + 
                          [co.lower() for coperformers in playlist_tour_data 
                           for co in coperformers["festival_coperformers"]])
        # remove festival names - some were accidentally included despite my filtering
        festival_names = ["aftershock", "louder than life", "rock fest", "rockville", "welcome to rockville", 
                    "lollapalooza", "sonic temple", "mayhem festival", "coachella", "bonnaroo"]
        all_artists = all_artists - set(festival_names)
        nonplaylist_artist_names = all_artists - set(playlist_artist_names)
        # get features of new artists - spotify
        nonplaylist_spotify_features = self._get_spotify_artist_by_search(nonplaylist_artist_names)
        # lastfm
        nonplaylist_lastfm_features = self._get_lastfm_features(nonplaylist_artist_names)
        # tour data - not including coperformers
        nonplaylist_tour_data = self._get_artist_coperformers(nonplaylist_artist_names, get_coperformers=False)

        # consolidate all features across all artists
        playlist_all_features = pd.DataFrame(playlist_spotify_features).merge(pd.DataFrame(playlist_lastfm_features),
                                                                              how="left", on="name")
        playlist_all_features = playlist_all_features.merge(pd.DataFrame(playlist_tour_data), 
                                                            how="left", on="name")

        nonplaylist_all_features = pd.DataFrame(nonplaylist_spotify_features).merge(pd.DataFrame(nonplaylist_lastfm_features), 
                                                                                    how="left", on="name")
        nonplaylist_all_features = nonplaylist_all_features.merge(pd.DataFrame(nonplaylist_tour_data), 
                                                                  how="left", on="name")
        # TODO: only add to relations if present in all features
        # TODO: there is still some issue w lowercasing - as seen in viz.
        # artist relations
            # lastfm similarity
        relations = []
        for origin, similar_ls in similar_artists.items(): 

            for (similar_artist, sim_score) in similar_ls: 

                relations.append({
                    "origin": origin, 
                    "target": similar_artist, 
                    "type": "similarity",
                    "weight": float(sim_score)})
        # coperformers
        for coperformer_dict in playlist_tour_data:

            origin = coperformer_dict["name"]
            tour_coperformers = coperformer_dict["tour_coperformers"]
            festival_coperformers = coperformer_dict["festival_coperformers"]

            for tour_co in tour_coperformers: 
                
                relations.append({
                    "origin": origin,
                    "target": tour_co, 
                    "type": "tour",
                    "weight": 1.0
                })
            for festival_co, cnt in festival_coperformers.items():

                relations.append({
                    "origin": origin, 
                    "target": festival_co,
                    "type": "festival", 
                    "weight": cnt
                })
        
        with open("artist_relationships.json", "w") as f:
            json.dump(relations, f, indent=2)

        print(f"get_all_artist_features: {len(relations)} artist relationships saved to artist_relationships.json.")

        ALL_FEATURES = pd.concat([playlist_all_features, nonplaylist_all_features])
        ALL_FEATURES = ALL_FEATURES.drop_duplicates(subset=["name"])
        ALL_FEATURES = ALL_FEATURES.dropna(subset=["name", "popularity", "albums", "lastfm_listeners", "tour_status"])
        
        ALL_FEATURES.to_csv(self.features_filename, index=False)

        print(f"get_all_artist_features: All features written to {self.features_filename}.")
        return ALL_FEATURES

if __name__ == "__main__":

    # load all API keys
    load_dotenv()

    extractor = FeatureExtractor(spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID"), 
                                 spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"), 
                                 playlist_url="https://open.spotify.com/playlist/142oZDOc1za2dkUwyonA1P?si=d00ef6f833e34213", 
                                 lastfm_api_key=os.environ.get("LASTFM_API_KEY"), 
                                 lastfm_username="jasminexx18", 
                                 discovery_api_key=os.environ.get("TM_API_KEY"), 
                                 features_filename="ALL_FEATURES_HARDNHEAVY.csv")
    
    all_features = extractor.get_all_artist_features()