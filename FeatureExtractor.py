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

        # self.all_artist_features = []

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

        
        artist_uris = set([artist["uri"] for artist in artists])
        all_artist_info = []

        for uri in artist_uris: 

            artist_info = self.SPOTIFY.artist(uri)
            artist_count = sum([1 for artist_dict in artists if artist_dict["uri"] == uri])
            artist_info["playlist_count"] = artist_count
        
            all_artist_info.append(artist_info)
        
        print(f"_get_playlist_artists: information retrieved for {len(artist_uris)} artists.")
        return all_artist_info
    
    def _get_spotify_artist_by_search(self, artist_name):

        """Returns artist information for a given artist name. To be called for artists 
           NOT present in the starter playlist."""

        try: 
            artist_info = self.SPOTIFY.search(q=artist_name, type="artist").get("artists", {}).get("items", [])[0]
            artist_info["playlist_count"] = 0

            return artist_info
        
        except Exception as e: 
            
            print(f"_get_spotify_artist_by_search: no artist found for query {artist_name}; error {e}.")

    def _generate_discog_features(self, artist_dicts):

        all_artist_info = []

        for artist_dict in artist_dicts:

            if artist_dict:
                uri = artist_dict.get("uri", None)

                if uri:

                    # album info
                    albums = self.SPOTIFY.artist_albums(uri, include_groups="album")
                    # number of albums
                    artist_dict["albums"] = albums["total"]
                    album_items = albums["items"]
                    # doesn't account for singles outside albums
                    # don't want to count an album twice if a deluxe version was released
                    # note that live versions are counted for now
                    tracks_count = 0
                    for album in album_items: 
                        tracks_count += album["total_tracks"]
                    
                    artist_dict["tracks"] = tracks_count
                    
                    artist_dict["last_album_date"] = album_items[0]["release_date"] if album_items else None
                    artist_dict["first_album_date"] = album_items[-1]["release_date"] if album_items else None
                
                    all_artist_info.append(artist_dict)
                else: 
                    print(f"_generate_discog_features: skipping artist {artist_dict.get('name', '')}.")

        print(f"_generate_discog_features: discography features generated for {len(artist_dicts)} artists.")
        return all_artist_info
    
    def _get_spotify_features(self, artist_dicts):

        """Generates and returns features for each artist."""

        features = []

        for artist_dict in artist_dicts: 

            features.append({"name": artist_dict.get("name", ""),
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

        artist_info = []
        
        for artist_name in artist_names: 

            url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&username={self.lastfm_username}&api_key={self.lastfm_api_key}&format=json"

            try: 
                response = requests.get(url).json()["artist"]
                
                artist_info.append({
                    "name": artist_name,
                    "lastfm_listeners": response.get("stats", {}).get("listeners", 0),
                    "lastfm_playcount": response.get("stats", {}).get("playcount", 0),
                    "personal_playcount": response.get("stats", {}).get("userplaycount", 0),
                    "lastfm_tags": [tag["name"] for tag in response.get("tags", {}).get("tag", "")] 
                                    if response.get("tags", {}).get("tag", "") else [],
                    "summary": response.get("bio", {}).get("summary", "")
                })

            except Exception as e: 
                print(f"Artist {artist_name} not found on lastfm.")

        print(f"_get_lastfm_features: Lastfm features retrieved for {len(artist_info)} artists.")
        return artist_info
    
    def _get_artist_events(self, artist_name):

        """Returns a list of FUTURE events associated with a provided artist name from the Discovery API. Max 200."""

        artist_name_formatted = "+".join(artist_name.split()).lower()
        url = f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={self.discovery_api_key}&classificationName=music&keyword={artist_name_formatted}&sort=date,name,asc&size=200"
        response = requests.get(url).json()

        # if artist was found
        if "_embedded" in response.keys():
            
            return response["_embedded"]["events"]

        return None
    
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

        print(event_info.get("name", ""), classifications)
        return True
    
    def _get_artist_coperformers(self, artist_events):

        """Returns lists of tour and festival coperformers, and determines whether or not an artist 
           is currently on tour, about to start tour, or not on tour."""

        tour_status = "not_touring" 
        tour_date = None
        current_date = datetime.now()
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
                
                # grab coperformers for each event (assuming that each event w the same title has the same coperformers)
                event_attractions = events_info[0].get("_embedded", {}).get("attractions", [])
                # names of coperformers for this event 
                # TODO :5
                event_attractions = [adict["name"] for adict in event_attractions[:5] if self.__is_tour(adict)]
            
                if event_is_tour: 
                    tour_coperformers += event_attractions
                    if tour_date == None: 
                        event_date_str = events_info[0]["dates"]["start"]["localDate"]
                        tour_date = datetime.strptime(event_date_str, "%Y-%m-%d")
                else:
                    festival_coperformers += event_attractions

            # determine specific tour status
            if tour_date: 
                if tour_date >= future_threshold: 
                    tour_status = "upcoming_tour"
                elif current_date <= tour_date <= future_threshold:
                    tour_status = "on_tour"

        # TODO: note that both coperformer sets will include the original artist
        return tour_status, tour_date, set(tour_coperformers), Counter(festival_coperformers)
    
    def _get_similar_artists(self, artist_name):

        """Returns similar artists to a given artist, alongside similarity score (from Lastfm)"""

        artist_name_formatted = "+".join(artist_name.split()).lower()
        # TODO: setting limit to 2 for testing
        url = f"https://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist={artist_name_formatted}&api_key={self.lastfm_api_key}&format=json&limit=2"
        response = requests.get(url).json().get("similarartists", {}).get("artist", [])

        return response
    
    def get_all_artist_features(self): 

        """Consolidates feature extraction pipeline across all sources."""

        playlist_artist_info = self._get_playlist_artists()
        playlist_artist_names = [artist_dict.get("name", "") for artist_dict in playlist_artist_info]

        all_artists = set(playlist_artist_names)

        similar_artists = {}
        artist_tour_status = []
        artist_coperformers = {}

        for artist_name in playlist_artist_names: 
            
            artist_similar_artists = self._get_similar_artists(artist_name)
            similar_artists[artist_name] = artist_similar_artists
            all_artists.update(artist["name"] for artist in artist_similar_artists)

            artist_events = self._get_artist_events(artist_name)
            tour_status, tour_date, tour_coperformers, festival_coperformers = self._get_artist_coperformers(artist_events)
            # TODO: I haven't retrieved tour info for the coperformers 
            artist_tour_status.append({
                "name": artist_name, 
                "tour_status": tour_status, 
                "tour_date": tour_date})
            artist_coperformers[artist_name] = {
                "tour_coperformers": tour_coperformers,
                "festival_coperformers": festival_coperformers
            }
            all_artists.update(tour_coperformers)
            all_artists.update(festival_coperformers.keys())

        print(f"get_all_artist_features: all_artists length {len(all_artists)}.")
        print(f"get_all_artist_features: all event information retrieved.")

        # get Spotify features 
            # for playlist artists
        playlist_artist_info = self._generate_discog_features(playlist_artist_info)
        playlist_artist_features = self._get_spotify_features(playlist_artist_info)
            # for non playlist artists
        non_playlist_artists = set(all_artists) - set(playlist_artist_names)
        non_playlist_artist_info = [self._get_spotify_artist_by_search(name) for name in non_playlist_artists]
        print(f"get_all_artist_features: completed _get_spotify_artist_by_search for {len(non_playlist_artist_info)} artists.")
        
        non_playlist_artist_info = self._generate_discog_features(non_playlist_artist_info)
        non_playlist_artist_features = self._get_spotify_features(non_playlist_artist_info)

        all_spotify_features = pd.DataFrame(playlist_artist_features + non_playlist_artist_features)

        # get Lastfm features
        all_lastfm_features = pd.DataFrame(self._get_lastfm_features(all_artists))

        all_features = all_spotify_features.merge(all_lastfm_features, how="left", on="name")
        all_features = all_features.merge(pd.DataFrame(artist_tour_status), how="left", on="name")

        # TODO: testing purposes
        all_features.to_csv("ALL_FEATURES.csv", index=False)
        print(f"All features written to ALL_FEATURES.csv.")
        return all_features

if __name__ == "__main__":

    # load all API keys
    load_dotenv()

    extractor = FeatureExtractor(spotify_client_id=os.environ.get("SPOTIFY_CLIENT_ID"), 
                                 spotify_client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"), 
                                 playlist_url="https://open.spotify.com/playlist/142oZDOc1za2dkUwyonA1P?si=f651169be5044b4d", 
                                 lastfm_api_key=os.environ.get("LASTFM_API_KEY"), 
                                 lastfm_username="jasminexx18", 
                                 discovery_api_key=os.environ.get("TM_API_KEY"))
    
    all_features = extractor.get_all_artist_features()