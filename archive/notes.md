# Past Notes
### Action Items (Jul. 10, 2025)
* Re-organize the current pipeline - it's a bit of a mess. 
  * Add documentation and types.
  * Determine the exact input and output of each function. Band name lowercasing and punctuation stripping is really confusing.
  * Investigate the workings of the cache. 
    * Might need to restructure some of the data being written to the cache, primarily the events data, because the vast amount of information pulled (incl. random unneccessary links) will cause issues if the JSON file gets too big.
* Parallelize API calls. Understand how they work.
* Think about what other data sources to pull information from. 
  * Remember that a big initial goal was to try and somehow integrate social media data (or in general, just more social aspects of the artist/music universe). I wonder if linking artists together by their record label would be somewhat of a proxy for that.
* Think about any additional features to use. 
  * Nationality feels a bit wrong to use, but if I did want to use it, I think I might need to do some NLP on the band summary. Don't know if there is a resource where I can directly pull their nationality, but lastfm summaries almost always state where the band is from. Same thing for band formation year, although maybe the time of first album release is a good enough proxy for that (or not, as oftentimes bands start with EPs. Come to think of it, I'm not sure why I didn't include EPs in the album/track count).
    * Annoyingly, there is no direct way to grab an artist's EPs via the Spotify API; all EPs are returned if you look for singles, but I cannot find anything from the API response that distinguishes between a single and an EP.
* With the current features, try and put everything together to create a basic preliminary visualization. Might help me think of things to add.

### Rough Outline (Jul. 7, 2025)
1. Grab playlist data from Spotify API.
   * The information available from the Spotify API should be enough. Features such as the number of releases, popularity, etc.
   * Later, in the UI itself, I would like the option to select a playlist instead of solely using a predefined one. This would then require the ability to automatically grab the playlist's most up-to-date features at any given moment. 
   * Note: I don't think I need features such as subgenres and audio features, as I believe those are likely already taken into account by lastfm in their recommendations to some extent. However, if needed, someone made an Exportify CLI (I have yet to try it) that may be useful here. It's just that as far as I'm concerned, I don't think it would do me any good to have those features if I cannot get those features for the similar artists. Also, Exportify yields song-level data.
2. Generate relevant features using Spotify API.
   * These (remember, artist-level) features would be things like: 
     * popularity (not sure how this is computed; I wonder if it would be better estimated via the total number of streams, although that would require more API requests and slow down the pipeline; lastfm has artist total playcounts that I can use instead)
     * number of releases
     * year of first release
     * year of last release
     * number of albums
     * number of tracks
     * number of times they show up in playlist (as primary artist or as a feature)
     * artist picture (for UI visualization purposes but obviously not a feature)
3. Generate relevant features using Lastfm API.
   * From `artist.getInfo` endpoint - things like: 
     * total listeners
     * total playcount
     * number of MY streams 
     * tags (genre tags; may or may not use; if I do use though, would need some way of filtering out irrelevant tags)
     * description/summary: for visualization purposes but also allows me to mine for nationality (+ record label, history, etc.) using some NLP technique if I'd like to use it as a feature or visualization tag
     * on tour: lastfm has a binary `ontour` label for each artist, although I think I want more detailed tour info, e.g., starting tour soon. 
4. Grab similar artists using Lastfm API.
   * In the final UI, I want to be able to toggle how many ripples outwards to go. Start with just one though; that would also be the ripple that contains the most immediate artists I should look into as they are deemed most similar to the ones I already like.
5. Grab touring data from external API - Songkick or Bandsintown.
6. Compute similarity/prioritization score using features and weights (GNN implementation).
   * Make sure that similar artists who are already in the playlist are not considered in the score. Or actually, would it make sense to weigh similar artists of those artists more heavily? That might make more sense actually.
   * Take into account the features listed in steps 2 and 3. Compute specific weights accordingly (proportion of artist songs in playlist, e.g.)
   * Generate rankings (top 5 or 10 highest similarity scorers)
7. Build UI. 
   * I want to have a means of visualizing the knowledge graph. I want to be able to select a node (an artist) and see their profile (basic info, their image, some of their general features)
   * I want the recommendations to have explainability - what features contributed to their being recommended?
   * Filtering options: 
      * Number of similar artist ripples outward
      * Minimum number of tracks an artist has in the playlist in order to be considered
      * Minimum number of my streams on that artist (^)
      * Which features to consider in the recommendations
    * I also want the ability to just directly select artists (2 or more) to generate the knowledge graph and recommendations for.
    * I would prefer not to use streamlit; I'm a bit tired of it and would prefer some novelty. I'm also not sure what frameworks even allow for visualization of knowledge graphs. I presume the KG can be produced in Plotly.
      * [Gradio](https://www.gradio.app/)
      * I want something similar to [this](https://huggingface.co/spaces/emilyalsentzer/SHEPHERD)
8. **Grab social media data; further prioritize artists commonly mentioned or recommended by social media accounts. This is a difficult thing to figure out and I will try it after I've finished everything else.

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