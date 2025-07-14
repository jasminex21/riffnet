# Riff Net
*Note - name is subject to change.*

I aim for this to be a musical artist recommender - it will output a list or ranking of artists one should look into, based on artists they already like. The technical basis of this will be a Graph Neural Network trained on a Knowledge Graph that links artists together based on features such as: 
* Genre, subgenre
* Age/era (e.g., 1980s vs 2020s)
* Musical/sonical properties - general mood, tempo, etc.
* General artist properties - number of albums/songs, year of first release, band makeup, etc.
* (Tentative, but I'd like to try and take into account upcoming tours and new music, as well as social media presence and connections to other bands)

Music recommendors built by platforms such as Spotify are already comprehensive. They apply most of the features I've listed above, as well as detailed audio/sonical features and microgenres (that are no longer available via their API). In addition, they leverage their vast amounts of user data to apply techniques such as collaboative filtering. There is no way I can build a tool that is better (i.e., more comprehensive) than theirs, and so this project mainly aims to build upon pre-existing tools, such that:

1. I can visualize the connections between artists I listen to and enjoy
2. the recommendor suggests artists based on specific features that general recommendors may not consider (e.g., tour data, social data)

### Notes (Jul. 14, 2025)
* For large playlists, the number of artists whose information is retrieved increases exponentially, and runtime follows accordingly. It is probably not feasible to make this application generalizable to multiple playlists for that reason. What I think I will do is to restrict the scope of this project just to my HARD & HEAVY playlist, and allow for it to be updated (e.g., click a button to update the pulled artists) - that should not be overly time-consuming, since I have most artists already cached.
  * For reference - as of today, my HARD & HEAVY playlist has 50 artists, which ultimately results in 8,308 artist relationships. This took around 15-20 minutes to run, which is clearly not something I would like to do multiple times.
* It would be nice to store past artist relations. The Discovery API only grabs *future* events, which means that if I were to update my data after certain events have passed, the artist relationships involved in those events would be overlooked, despite them obviously being of importance. So perhaps make it so that the events cache is not overwritten but appended to.
* There appears to be some issue with the tour classification logic - most look correct, but I've seen some cases where festivals are counted as tours (A Day to Remember and Nickelback are *not* touring together, but they are performing at a festval together). This is most likely bc "Festival" is not listed in the event's classifications - perhaps try and filter via the event title; if it contains "Fest" or "Festival" just classify it as a festival.

### Artist Relationship (Jul. 13, 2025)
* I have completed the logic of the feature-pulling pipeline. I do still need to implement parallel processing, but I'd like to figure out how to store artist-artist relationships first.
* Structure: 
  
  ```json
  [
  {"source": "spiritbox", "target": "bad omens", "type": "similarity", "weight": 0.85},
  {"source": "spiritbox", "target": "periphery", "type": "tour", "weight": 1.0, "event_date": "2025-08-15"},
  {"source": "hatebreed", "target": "dayseeker", "type": "festival", "weight": 2, "event_name": "louder than life"}
  ]
  ```

  * Note that `source`, `target`, and `type` are mandatory; `weight` indicates the strength of the relationship, and all other keys are optional features associated with the connection, e.g., `event_name`.