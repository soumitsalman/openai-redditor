import json
import csv
import os
import re
import pandas as pd
from enum import Enum

LOCATION_DIR = "C:\\Users\\soumi\\go-stuff\\reddit_data_dump\\"
JOINED_CHANNELS = "_joined_subreddits.json"
NEW_CHANNELS = "_recommended_subreddits.json"
NEW_POSTS = "_posts.json"
CONFIG = "_config.json"
LOGSTORE = "_logs.csv"



class ItemStatus(Enum):
    ANALYZED = "analyzed"
    INTERESTING = "interesting"
    SHORT_LISTED = "short_listed"
    ACTION_SUGGESTED = "action_suggested"
    ACTION_TAKEN = "action_taken"
    IGNORE = "ignore"

class SocialMediaDataStore:
    user_id = "" #currently this is not being used
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        store_prefix = LOCATION_DIR+user_id
        self.joined_channels = store_prefix+JOINED_CHANNELS
        self.new_channels = store_prefix + NEW_CHANNELS
        self.new_posts = store_prefix + NEW_POSTS
        self.user_config = store_prefix + CONFIG
        self.logfile = store_prefix + LOGSTORE
        self.user_logs = self.load_logs()
        
    def get_user_details(self):         
        with open(self.user_config, encoding = "utf-8") as f:
            blob = json.load(f)
        return blob

    # this is expected to return an arreay
    def get_areas_of_interest(self):
        # TODO: pull in from a database for the specific user
        return ["cyber security", "new software products", "software development", "api integration", "generative ai", "software product management", "software program management", "autonomous vehicle", "cloud infrastructure", "information security"]

    # these contain all channels and post retrieval related code

    # this is expected to return an array
    def get_subscribed_media_channels(self):
        # TODO: pull in from a database for the specific user
        with open(self.joined_subreddits, encoding='utf-8') as f:
            joined_sr = json.load(f)

        return joined_sr

    # this is expected to return an array
    def load_new_media_channels(self) -> list[dict[str, any]]:    
        # TODO: pull in from a database for the specific user
        with open(self.new_channels, encoding='utf-8') as f:
            rec_sr = json.load(f)["recommended_subreddits"]        
        return rec_sr

    # this is expected to return an array
    def get_channels_to_analyze(self) -> list[dict[str, any]]:           
        channels = self.load_new_media_channels()
        #channels that the user is not already subscribing to and has not yet been analyzed
        sr_filter = lambda sr: (not sr["already_subscribed"]) and not self.exists_in_logs(sr["name"], ItemStatus.ANALYZED)   

        return list(filter(sr_filter, channels))
    
    def get_channels_to_short_list(self):
        channels = self.load_new_media_channels()
        interesting = self.get_names_of_status(ItemStatus.INTERESTING)        
        items = list(filter(lambda ch: ch['name'] in interesting, channels ))
        return items

    # this is expected return an array of posts with self contents
    # it will filter out links, images and videos for now
    def get_new_media_posts(self):
        with open(self.new_posts, encoding='utf-8') as f:
            rec_posts = json.load(f)["posts"]
        
        user_name = self.get_user_details()["user_name"]   
        # TODO: filter out posts for which there is already a user response
        # posts that has some content, is not self authored and has not already been analyzed
        post_filter = lambda p: p["post_content"] != "" and p["author"] != user_name and not self.exists_in_logs(p["name"], ItemStatus.ANALYZED)

        return list(filter(post_filter, rec_posts))

    #all user action log related functions
    def load_logs(self):
        if os.path.exists(self.logfile):            
            self.user_logs = pd.read_csv(self.logfile)
        else:
            self.user_logs = pd.DataFrame()  
        return self.user_logs          

    def get_names_of_status(self, status: ItemStatus):
        if self.user_logs.empty:
            return self.user_logs
        else:
            return self.user_logs[self.user_logs['status'] == status.value]['name'].unique()

    #check if an item with 'name' already has 'status'
    def exists_in_logs(self, name: str, status: ItemStatus) -> bool:        
        if self.user_logs.empty: #no need to search if there is no log
            return False        
        try:
            return not self.user_logs[(self.user_logs["name"] == name) & (self.user_logs["status"] == status.value)].empty            
        except KeyError: #this is when the log file is empty
            return False

    def save_status(self, items: list[str], status: ItemStatus):   
        if len(items) == 0: #do nothing for empty list            
            return 
        viewed_names = pd.DataFrame({
            "name": items,
            "status": [status.value]*len(items)
            # TODO: add interesting, short-listed, acted-on fields
        })
        viewed_names.to_csv(
            self.logfile, 
            mode = 'a', 
            header = not os.path.exists(self.logfile), #if file does not exist write the header or else skip
            index = False)






    