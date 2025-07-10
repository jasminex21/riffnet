import pandas as pd
import numpy as np
import json
import spotipy
import re
import requests
import os
import string
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from spotipy.oauth2 import SpotifyClientCredentials

# TODO: 
    # Parallel processing for API calls
    # Cache API responses
    # Grab on_tour info for ALL artists (currently only gets playlist artists)
    # Some venue names and tribute artists are being taken
        # Perhaps do a check and only take attractions if the attraction on hand is in the list
    # Store and structure nodes and edges

class FeatureExtractor: 

    def __init__(self, spotify_client_id, spotify_client_secret, 
                 playlist_url, lastfm_api_key, lastfm_username, discovery_api_key):
        
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

        # self.all_artist_features = []

    def _save_cache(self, cache, cache_file):

        cache_path = os.path.join(self.cache_dir, cache_file)

        with open(cache_path, "w") as f:
            json.dump(cache, f)

        print(f"_save_cache: {len(cache)} items saved to cache {cache_file}.")

    def _load_cache(self, cache_file):

        cache_path = os.path.join(self.cache_dir, cache_file)

        if os.path.exists(cache_path):

            with open(cache_path, "r") as f:

                cache = json.load(f)
                current_time = datetime.now().timestamp()

                return {k: v for k, v in cache.items() 
                        if v.get("timestamp", 0) + self.cache_expiry.total_seconds() > current_time}
        
        return {}

    def _get_playlist_artists(self): 

        """Returns information for each unique artist in the provided playlist.
        
           e.g., for Sleep Token: 
           {'external_urls': {'spotify': 'https://open.spotify.com/artist/2n2RSaZqBuUUukhbLlpnE6'},
            'followers': {'href': None, 'total': 2512594},
            'genres': ['progressive metal', 'metalcore'],
            'href': 'https://api.spotify.com/v1/artists/2n2RSaZqBuUUukhbLlpnE6',
            'id': '2n2RSaZqBuUUukhbLlpnE6',
            'images': [...],
            'name': 'Sleep Token',
            'popularity': 85,
            'type': 'artist',
            'uri': 'spotify:artist:2n2RSaZqBuUUukhbLlpnE6',
            'playlist_count': 36}"""    

        response = self.SPOTIFY.playlist_tracks(self.playlist_url, offset=0)
        # each artist involved in a song with features is considered individually
        artists = [artist_dict for track in response["items"] for artist_dict in track["track"]["artists"]]
        # total number of tracks on playlist - needed to determine the number of loops (max tracks per req. is 100)
        total = response["total"]

        for offset in range(100, total + 1, 100): 

            response = self.SPOTIFY.playlist_tracks(self.playlist_url, offset=offset)
            artists += [artist_dict for track in response["items"] for artist_dict in track["track"]["artists"]]
      
        artist_identifiers = set([(artist["name"].lower().strip(string.punctuation), artist["uri"]) for artist in artists])
        all_artist_info = []

        spotify_cache = self._load_cache("spotify_artist_cache.json")
        
        def fetch_artist(uri, name):

            if name in spotify_cache:

                return spotify_cache[name]["data"]
            
            try:
                artist_info = self.SPOTIFY.artist(uri)
                artist_count = sum(1 for artist_dict in artists if artist_dict["uri"] == uri)
                artist_info["playlist_count"] = artist_count
                spotify_cache[name.lower().strip(string.punctuation)] = {"data": artist_info, "timestamp": datetime.now().timestamp()}

                return artist_info
            
            except Exception as e:
                print(f"_get_playlist_artists: Error for URI {uri}: {e}")
                return None

        for (name, uri) in artist_identifiers: 
            all_artist_info.append(fetch_artist(uri, name))
        #     artist_info = self.SPOTIFY.artist(uri)
        #     artist_count = sum([1 for artist_dict in artists if artist_dict["uri"] == uri])
        #     artist_info["playlist_count"] = artist_count
        
            # all_artist_info.append(artist_info)

        self._save_cache(spotify_cache, "spotify_artist_cache.json")
        print(f"_get_playlist_artists: information retrieved for {len(artist_identifiers)} artists.")
        return all_artist_info
    
    def _get_spotify_artist_by_search(self, artist_names):

        """Returns artist information for a given artist name. To be called for artists 
           NOT present in the starter playlist."""

        # load artist from cache if they are already recorded
        # goes by lowercase name
        spotify_cache = self._load_cache("spotify_artist_cache.json")

        def fetch_search(artist_name):
            cache_key = artist_name.lower()
            if cache_key in spotify_cache: 
                return spotify_cache[cache_key]["data"]

            try: 
                artist_info = self.SPOTIFY.search(q=artist_name, type="artist").get("artists", {}).get("items", [])[0]
                artist_info["playlist_count"] = 0
                # add to cache
                spotify_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}

                return artist_info
            
            except Exception as e: 
                
                print(f"_get_spotify_artist_by_search: no artist found for query {artist_name}; error {e}.")
                return {"name": cache_key, "uri": "", "genres": [], "popularity": 0, "followers": {"total": 0}, "playlist_count": 0}
        
        searched_artists = []
        for artist_name in artist_names:
           
            searched_artists.append(fetch_search(artist_name))
        
        self._save_cache(spotify_cache, "spotify_artist_cache.json")
        return searched_artists

    def _generate_discog_features(self, artist_dicts):

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
                spotify_cache[cache_key] = {"data": artist_dict, "timestamp": datetime.now().timestamp()}
                return artist_dict

            except Exception as e:
                print(f"_generate_discog_features: Error obtaining Spotify discography features for artist {artist_name}; {e}.")
                artist_dict["albums"] = 0
                artist_dict["tracks"] = 0
                artist_dict["last_album_date"] = None
                artist_dict["first_album_date"] = None
                spotify_cache[cache_key] = {"data": artist_dict, "timestamp": datetime.now().timestamp()}
                return artist_dict
            
        all_artist_info = []
        for artist_dict in artist_dicts: 
            all_artist_info.append(fetch_discog(artist_dict))

        self._save_cache(spotify_cache, "spotify_discog_cache.json")
        print(f"_generate_discog_features: discography features generated for {len(all_artist_info)} artists.")
        return all_artist_info
    
    def _get_spotify_features(self, artist_dicts):

        """Generates and returns features for each artist."""

        features = []

        for artist_dict in artist_dicts: 

            features.append({"name": artist_dict.get("name", "").lower().strip(string.punctuation),
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
    
    def _get_lastfm_features(self, artist_names): 

        """Grabs Lastfm features for a list of artist names. If the artist is not found, they are ignored."""

        lastfm_cache = self._load_cache("lastfm_cache.json")

        def fetch_lastfm(artist_name):

            cache_key = artist_name.lower()
            if cache_key in lastfm_cache:
                return lastfm_cache[cache_key]["data"]
            
            url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&username={self.lastfm_username}&api_key={self.lastfm_api_key}&format=json"

            try: 
                response = requests.get(url).json()["artist"]
                artist_info = {"name": artist_name.lower().strip(string.punctuation),
                               "lastfm_listeners": response.get("stats", {}).get("listeners", 0),
                               "lastfm_playcount": response.get("stats", {}).get("playcount", 0),
                               "personal_playcount": response.get("stats", {}).get("userplaycount", 0),
                               "lastfm_tags": [tag["name"] for tag in response.get("tags", {}).get("tag", [])],
                               "summary": response.get("bio", {}).get("summary", "")}
                lastfm_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}
                return artist_info

            except Exception as e: 
                print(f"Artist {artist_name} not found on lastfm.")
                artist_info = {"name": artist_name.lower().strip(string.punctuation), 
                               "lastfm_listeners": 0, 
                               "lastfm_playcount": 0, 
                               "personal_playcount": 0, 
                               "lastfm_tags": [], 
                               "summary": ""}
                lastfm_cache[cache_key] = {"data": artist_info, "timestamp": datetime.now().timestamp()}
                return artist_info
        
        artists_info = []
        
        for artist_name in artist_names: 
            artists_info.append(fetch_lastfm(artist_name))

        self._save_cache(lastfm_cache, "lastfm_cache.json")

        print(f"_get_lastfm_features: Lastfm features retrieved for {len(artists_info)} artists.")
        return artists_info
    
    def _get_artist_events(self, artist_names):

        """Returns a list of FUTURE events associated with a provided artist name from the Discovery API. Max 200."""

        ticketmaster_cache = self._load_cache("ticketmaster_cache.json")

        def fetch_events(artist_name):

            cache_key = artist_name.lower()
            if cache_key in ticketmaster_cache: 
                return ticketmaster_cache[cache_key]["data"]

            artist_name_formatted = "+".join(artist_name.split()).lower().strip(string.punctuation)
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={self.discovery_api_key}&classificationName=music&keyword={artist_name_formatted}&sort=date,name,asc&size=20"
            
            try: 
                response = requests.get(url).json()
                events = response.get("_embedded", {}).get("events", [])
                events_compressed = []
                for event in events: 
                    events_compressed.append({
                        "name": event["name"],
                        "dates": event["dates"],
                        "classifications": event["classifications"],
                        "_embedded": event["_embedded"]
                    })
                ticketmaster_cache[cache_key] = {"data": events_compressed, "timestamp": datetime.now().timestamp()}
                return events
            
            except Exception as e: 
                print(f"_get_artist_events: Error fetching events for artist {artist_name}: {e}.")
                ticketmaster_cache[cache_key] = {"data": [], "timestamp": datetime.now().timestamp()}
                return []
        
        artist_events = {}
        for artist_name in artist_names: 
            artist_events[artist_name.lower().strip(string.punctuation)] = fetch_events(artist_name)

        print(f"_get_artist_events: Events fetched for {len(artist_events)} artists.")
        self._save_cache(ticketmaster_cache, "ticketmaster_cache.json")
        return artist_events

    def __is_tour(self, event_info): 

        """Infers whether a specific event is part of an artist tour or a festival."""

        classifications = event_info.get("classifications", [])

        for c in classifications: 

            if c.get("subType", {}).get("name") == "Festival": 
                return False
                
        # if there are more than 5 performers, it's probably a festival 
        # the most openers I've ever heard of for a tour is 3, 4 incl. the headliner
        if len(event_info.get("_embedded", {}).get("attractions", [])) > 5: 
            return False

        return True
    
    def _get_artist_coperformers(self, artist_name, artist_events, get_coperformers=False):

        """Returns lists of tour and festival coperformers, and determines whether or not an artist 
           is currently on tour, about to start tour, or not on tour."""

        tour_status = "not_touring" 
        tour_date = None
        current_date = datetime.now().date()
        # if a tour is 30+ days in the future, it is an upcoming tour
        # any less than that and it is considered a current tour 
        future_threshold = current_date + timedelta(days=30)
        tour_coperformers = []
        festival_coperformers = []

        if artist_events:
            # group names (if the artist is touring, these tend to be the same, but not always)
            event_groups = {}

            for event in artist_events: 
                event_name = event.get("name", "").lower()
                event_name = event_name.translate(str.maketrans('', '', string.punctuation))
                event_groups.setdefault(event_name, []).append(event)

            for event_name, events_info in event_groups.items(): 

                event_is_tour = self.__is_tour(events_info[0])
                
                if get_coperformers:

                    # grab coperformers for each event (assuming that each event w the same title has the same coperformers)
                    event_attractions = events_info[0].get("_embedded", {}).get("attractions", [])
                    # names of coperformers for this event 
                    event_attractions = [adict["name"].lower().strip(string.punctuation) for adict in event_attractions if self.__is_tour(adict)]
                    
                    # ensure that all events are relevant to the correct artist
                    # (avoid grabbing things like tribute bands...whatever those are)
                    if artist_name.lower().strip(string.punctuation) not in event_attractions:
                        print(f"Skipping events for artist name {artist_name} with attractions {event_attractions}")
                        continue
                        
                    if event_is_tour: 
                        tour_coperformers += event_attractions
                    else:
                        festival_coperformers += event_attractions

                if tour_date == None and event_is_tour: 
                    event_date_str = events_info[0]["dates"]["start"]["localDate"]
                    tour_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()

            # determine specific tour status
            if tour_date: 
                if tour_date >= future_threshold: 
                    tour_status = "upcoming_tour"
                elif current_date <= tour_date <= future_threshold:
                    tour_status = "on_tour"

        # TODO: note that both coperformer sets will include the original artist
        return tour_status, tour_date, set(tour_coperformers), Counter(festival_coperformers)
    
    def _get_similar_artists(self, artist_names):

        """Returns similar artists to a given artist, alongside similarity score (from Lastfm)"""

        lastfm_cache = self._load_cache("lastfm_similar_cache.json")

        def fetch_similar(artist_name):

            cache_key = artist_name.lower()
            if cache_key in lastfm_cache: 
                return lastfm_cache[cache_key]["data"]
            
            artist_name_formatted = "+".join(artist_name.split()).lower().strip(string.punctuation)
            url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name_formatted}&api_key={self.lastfm_api_key}&format=json&limit=10"

            try: 
                response = requests.get(url).json().get("similarartists", {}).get("artist", [])
                # tuples of (artist, similarity score)
                similar_artists = [(artist["name"].lower().strip(string.punctuation), artist["match"]) for artist in response]
                lastfm_cache[cache_key] = {"data": similar_artists, "timestamp": datetime.now().timestamp()}
                return similar_artists
            except Exception as e: 
                print(f"_get_similar_artists: Error fetching similar artists for artist {artist_name}: {e}")
                lastfm_cache[cache_key] = {"data": [], "timestamp": datetime.now().timestamp()}
                return []

        similar_artists = {}
        for artist_name in artist_names: 
            similar_artists[artist_name] = fetch_similar(artist_name)
        
        self._save_cache(lastfm_cache, "lastfm_similar_cache.json")
        return similar_artists


    def get_all_artist_features(self): 

        """Consolidates feature extraction pipeline across all sources."""

        playlist_artist_info = self._get_playlist_artists()
        playlist_artist_names = [artist_dict.get("name", "").lower().strip(string.punctuation) for artist_dict in playlist_artist_info]

        all_artists = set(playlist_artist_names)

        # similar_artists = {}
        artist_tour_status = []
        # artist_coperformers = {}

        playlist_similar_artists = self._get_similar_artists(playlist_artist_names)
        playlist_artist_events = self._get_artist_events(playlist_artist_names)
        # TODO: update all artists
        for playlist_artist in playlist_artist_names: 
            all_artists.update([artist[0] for artist in playlist_similar_artists[playlist_artist]])

            tour_status, tour_date, tour_coperformers, festival_coperformers = self._get_artist_coperformers(playlist_artist, 
                                                                                                             playlist_artist_events[playlist_artist], 
                                                                                                             get_coperformers=True)
            artist_tour_status.append({
                "name": playlist_artist,
                "tour_status": tour_status,
                "tour_date": tour_date,
                "tour_coperformers": tour_coperformers,
                "festival_coperformers": festival_coperformers
            })
            # TODO: debug here
            all_artists.update(tour_coperformers)
            all_artists.update(festival_coperformers.keys())

        print(f"get_all_artist_features: all_artists length {len(all_artists)}.")

        # get Spotify features 
            # for playlist artists
        playlist_artist_info = self._generate_discog_features(playlist_artist_info)
        playlist_artist_features = self._get_spotify_features(playlist_artist_info)
            # for non playlist artists
        non_playlist_artists = set([a.lower().strip(string.punctuation) for a in all_artists]) - set([a.lower().strip(string.punctuation) for a in playlist_artist_names])
        non_playlist_artist_info = self._get_spotify_artist_by_search(non_playlist_artists)
        print(f"get_all_artist_features: completed _get_spotify_artist_by_search for {len(non_playlist_artist_info)} artists.")
        
        non_playlist_artist_info = self._generate_discog_features(non_playlist_artist_info)
        non_playlist_artist_features = self._get_spotify_features(non_playlist_artist_info)
        # dict of {artist_name: [events]}
        non_playlist_artist_events = self._get_artist_events(non_playlist_artists)
        # print(f"get_all_artist_features: events pulled for {len(non_playlist_artist_events)} non-playlist artists.")

        ### HERE call the other function
        non_playlist_artist_tours = []
        for non_p_artist, non_p_events in non_playlist_artist_events.items():

            tour_status, tour_date, _, __ = self._get_artist_coperformers(non_p_artist, non_p_events, get_coperformers=False)
            non_playlist_artist_tours.append({
                "name": non_p_artist, 
                "tour_status": tour_status, 
                "tour_date": tour_date,
                "tour_coperformers": set(), 
                "festival_coperformers": Counter()})

        all_spotify_features = pd.DataFrame(playlist_artist_features + non_playlist_artist_features)

        # get Lastfm features
        all_lastfm_features = pd.DataFrame(self._get_lastfm_features(all_artists))
        print(all_lastfm_features)
        all_features = all_spotify_features.merge(all_lastfm_features, how="left", on="name")
        tour_statuses = pd.concat([pd.DataFrame(artist_tour_status), pd.DataFrame(non_playlist_artist_tours)])
        all_features = all_features.merge(pd.DataFrame(tour_statuses), how="left", on="name")

        all_features = all_features.drop_duplicates(subset=["name"])
        # TODO: testing purposes
        all_features.to_csv("ALL_FEATURES.csv", index=False)
        print(f"All features written to ALL_FEATURES.csv.")
        return all_features

if __name__ == "__main__":

    # load all API keys
    load_dotenv()

    extractor = FeatureExtractor(spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID"), 
                                 spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"), 
                                 playlist_url="https://open.spotify.com/playlist/71r2QEy5TiCGplk0QYPUSC?si=3dc90be0b5e74143", 
                                 lastfm_api_key=os.environ.get("LASTFM_API_KEY"), 
                                 lastfm_username="jasminexx18", 
                                 discovery_api_key=os.environ.get("TM_API_KEY"))
    
    all_features = extractor.get_all_artist_features()