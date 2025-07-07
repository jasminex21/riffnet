# Riff Net
*Note - name is subject to change.*

I aim for this to be a musical artist recommender - it will output a list or ranking of artists one should look into, based on artists they already like. The technical basis of this will be a Graph Neural Network trained on a Knowledge Graph that links artists together based on features such as: 
* Genre, subgenre
* Age/era (e.g., 1980s vs 2020s)
* Musical/sonical properties - general mood, tempo, etc.
* General artist properties - number of albums/songs, year of first release, band makeup, etc.
* (Tentative, but I'd like to try and take into account upcoming tours and new music, as well as social media presence and connections to other bands)

### Project Scoping (Jul. 7, 2025)
Obviously it is not feasible for me to store features for every artist on the platform, which is why I should start with a subset of related artists for each playlist artist. Music platforms already leverage fancy and complex algorithms (e.g. collaborative filtering) to recommend artists; there is no way I can do *better* than that with my resources, and so the only way from there is to leverage it and to improve upon it, and to fine-tune it for myself. Spotify has recently deprecated several API endpoints, including the similar artists one, and so in order to try and leverage pre-existing structures for artist recommendations, I will need to find some external resource. Once I can find a resource that allows me to obtain similar/related artists for a given subset of artists, it would just become a task of consolidating and prioritizing those related artists based on my relationship with the starter artists, as well as external data (social media, tour, etc.).

My best bet for finding related artists is the lastfm API. To get a given artist's similar artists, we just need the artist name or their MusicBrainz mbid. I can map a Spotify artist to an MBID via a call like in the below. In most cases the name should be enough, the only times there may be issues is if artists have the same name, but ambiguity should be avoided whenever possible. Note though that for some reason, the endpoints do not seem to work for certain artists if I search by MBID (e.g., it works for Cher (`bfcc6d75-a6a5-4bc6-8282-47aec8531818`) but not Bad Omens (`eecada09-acfc-472d-ae55-e9e5a43f12d8`)). For some artists Lastfm does not record the MBID, so looks like I'll have to search primarily by artist name and use MBID as a fallback, and if that doesn't work, I'll have to exclude that artist.

Request: `https://musicbrainz.org/ws/2/url/?query=url:https://open.spotify.com/artist/3Ri4H12KFyu98LMjSoij5V&targettype=artist&fmt=json`
```json
{
  "created": "2025-07-07T15:23:27.917Z",
  "count": 1,
  "offset": 0,
  "urls": [
    {
      "id": "f41b1cc5-1c2a-42fd-a276-e22f92db3082",
      "score": 100,
      "resource": "https://open.spotify.com/artist/3Ri4H12KFyu98LMjSoij5V",
      "relation-list": [
        {
          "relations": [
            {
              "type": "free streaming",
              "type-id": "769085a1-c2f7-4c24-a532-2375a77693bd",
              "direction": "backward",
              "artist": {
                "id": "eecada09-acfc-472d-ae55-e9e5a43f12d8",
                "name": "Bad Omens",
                "sort-name": "Bad Omens",
                "disambiguation": "metalcore band"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

MBID issue: 

Absolutely no clue how they determine which artists have an MBID and which do not (it's certainly not based on popularity). The artist.getInfo returns for Bad Omens vs President:

```json
"artist": {
    "name": "Bad Omens",
    "url": "https://www.last.fm/music/Bad+Omens",
    "image": [
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/34s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "small"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/64s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "medium"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/174s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "large"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "extralarge"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "mega"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": ""
      }
    ],
    "streamable": "0",
    "ontour": "1",
    "stats": {
      "listeners": "607862",
      "playcount": "60363393"
}
"artist": {
    "name": "President",
    "mbid": "5c13110c-f3b6-41eb-96f1-fceed830d9cc",
    "url": "https://www.last.fm/music/President",
    "image": [
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/34s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "small"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/64s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "medium"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/174s/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "large"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "extralarge"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": "mega"
      },
      {
        "#text": "https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png",
        "size": ""
      }
    ],
    "streamable": "0",
    "ontour": "1",
    "stats": {
      "listeners": "39356",
      "playcount": "488935"
    }
}
```

I could try to take advantage of lastfm tags, although those are user-curated and not always formal genres (e.g., users can tag an artist as something like "my favorite"). I could try and filter those, but I don't want for that process to be overly time-consuming, and anyways I imagine that lastfm is already taking genre into account in their recommendations.

Because of API and just general resource limitations, it is probably best if I restrict this project just to my own playlist(s). It can specifically help me find artists I will like based on artists already present in my hard n heavy playlist; this will allow me to implement features that I, specifically, care about, such as the social media aspects. Weighing the importance (higher prioritization) of similar artists can come down to engineered features such as: 
* proportion of songs in playlist by a certain artist (artists similar to this artist would be more heavily weighted)
* number of streams by certain artists (same case as above; I can get this data from lastfm)
* recency of certain artists (artists I am listening to a lot recently are those I am currently obsessed with, and I typically would like to find artists similar to those)

Probably I will end up computing some sort of "prioritization score" for each similar artist, based on the above metrics (and more as I think of them), as well as artist-to-similar-artist relationships (if a similar artist is associated with multiple artists in my playlist, they are probably worth looking into).

The good thing about restricting the scope of this project just to myself is that I get to implement a bunch of features that make sense for my specific desires, but not necessarily for others. Perhaps others don't care about artist tours as much as I do. I also want for the final UI to have lots of filtering options. 
* For example, for the core nodes: 
  * minimum number of songs an artist needs on the playlist in order to be considered a core node
  * minimum number of streams (^)
* Others:
  * How many "ripples" of related artists outward to go from the core nodes 
  * The ability to select the features being used to determine recommendations 

### First Draft Proposal (Jul. 1, 2025)
> Jul. 7, 2025 note: much of the proposal is not exactly feasible, just due to the lack of resources. See the project scope section above.
* Music / artist recommender - KG -> GNN implementation
  * In addition to being a useful tool for me, this would also help me practice my deep learning implementation skills. 
  * The key aim of this project would be to give me curated music artist recommendations, based on the artists I know I like. I want to be able to select an artist and look at other artists who are highly similar. Not entirely sure about what the final product would look like - perhaps it would provide a ranking of top artists I ought to look into based on a selected artist or a selected few artists.
  * The idea I have in mind is to make a GNN of musical artists; not entirely sure about the span/range or how to control it, but ideally I'd like to focus on the ones I already really like, and expand outwards from there. So maybe all the unique artists present in my hard n heavy playlist or something. But what I want to do is to have each artist be a node, and to connect them to related artists via shared features such as genre (and subgenres), popularity, and just general traits about the artists. I'd also like to see if I can enhance this by pulling information from social media. There are accounts I follow on social media who specialize in posting about metal/alternative artists, and oftentimes I explore and tend to like the ones they post. Another thing - it makes me really sad when I get into artists just after they've finished touring, so it would also be nice to highlight or at least tag artists as "starting a tour soon" so that I can look into them early and won't miss their tour if I find out I like them. What I find interesting in my experiences is that while music providers generally recommend other artists based on what seems more like the music itself, it's a little more nuanced irl. I got into Bad Omens and ultimately metal as a whole because Waterparks fans liked them - and ofc Waterparks is not metal, so I wonder what aspect the two of those artists share that causes this overlap. Not sure I can really answer that, but worth thinking about. 
  * Implementation details: 
    * I'll pull the artists from my hard n heavy playlist for starters, using the Spotify API. Ultimately, it may be nice to, in whatever user interface I end up with, to provide the option of selecting a playlist to choose from (to determine the range of starter artists) but for testing purposes we can start easy.
    * Generate features: 
      * Also using the Spotify API, pull features about the artists. Not sure what features are still available via the endpoints but things like popularity, genre, etc. would be useful. I'm actually not sure about genres - I don't remember how specific Spotify gets w them but I'd like high specificity, since I generally am in the metal orbit already and we need that to be further broken down. A better option might be [pygn](https://github.com/cweichen/pygn) for the Gracenote API.
        * I'm not sure if I can access "new album coming soon" sorta data from the Spotify API, I haven't seen that before
        * Maybe do some feature engineering of sorts to see if you can grab number of albums, number of songs, year of first release, those sort of things.
        * Nationality and gender? Feels kinda wrong to use those as a feature in recommendations BUT I feel like I tend to skew towards Western (+Australia) and male bands. Like if you were to recommend BABYMETAL (I think they're Japanese) I know I wouldn't like them.
      * Not sure abt the feasibility of this, but try and pull social media data. To be honest there aren't a ton of music content creators I follow, maybe just like State of the Scene on Twitter and fellbrink on Insta. But that can be expanded with time. I can try and pull their posts and use some sort of NLP/NER technique to extract artists they mention within some time frame.
      * Use the Bandsintown API to see what artists are starting a tour soon. Even if this is not used as a feature in training for the rankings, it can be used just to tag artists as starting tour soon.
* Generalization: this is something that can be generalized - ideally, I want it to be a platform where anyone can input, say, a playlist link, and then see based on artists represented in that playlist what new artists they should look into. However, the social media aspect would be difficult. Unless I modified it such that it does some sort of follower intersection thing (% of followers of artist A who also follow artist B) but I don't believe that is super feasible. Will think about it some more.