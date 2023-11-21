import tiktoken
import openai
import os
import retryutils as retry
import re
import redditutils as reddit
import datastoreutils as ds
import json
from openai.types.chat.completion_create_params import ResponseFormat
import envassist

POST_EDITOR_MODEL = "gpt-4-1106-preview"
CONTENT_FILTER_MODEL = "gpt-3.5-turbo-1106"
MAX_TOKENS = 3000

def ratelimiterror_handler(err: openai.RateLimitError):
    retry_after = (err.response.headers["x-ratelimit-reset-requests"], err.response.headers["x-ratelimit-reset-tokens"])
    print("we tried but hit rate limit. Retry after %s of type %s" % (retry_after, type(retry_after)))
    #TODO: in future make it derived from "x-ratelimit-reset-tokens"
    return 62

class OpenAIClient:    
    
    INITIALIZATION_MSG = "you are text search agent. You look into a bulk of given text and match what is asked"

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization=os.getenv("OPENAI_ORG_ID")
        )
        # TODO: only temporarily. remove this
        self.thread = [OpenAIClient.create_message("system", OpenAIClient.INITIALIZATION_MSG)]
        self.search_files = {}
        self.model = CONTENT_FILTER_MODEL        
        self.max_tokens = MAX_TOKENS

    def reset_context_window(self):
        self.thread = [OpenAIClient.create_message("system", self.INITIALIZATION_MSG)]

    def add(self, what: str):
        self.thread.append(OpenAIClient.create_message("user", what))    
        
    @retry.retry_after_func_wait(
        max_retries=3,
        errors = (openai.RateLimitError),
        wait_time_func=ratelimiterror_handler
    )
    def add_and_run(self, what: str, save_to_thread:bool = True) -> str:        
        msgs_to_send = self.thread + [OpenAIClient.create_message("user", what)]
        completion = self.client.chat.completions.create(
            model = self.model,
            messages = msgs_to_send,
            temperature=0.0,
            seed=4
        )        
        resp = completion.choices[0].message
        if save_to_thread: #remember the thread
            self.thread = msgs_to_send + [OpenAIClient.create_message(resp.role, resp.content)]
        return resp.content        
     
    @retry.retry_after_random_wait(min_wait=61, max_wait=120, max_retries=20, errors=(openai.RateLimitError))
    def upload_file(self, path: str, topic: str) -> str:
        with open(path, "rb") as f:
            file_id = self.client.files.create(file = f, purpose="assistants").id
        self.search_files[topic] = file_id        
        return file_id
    
    # this is a generic function that is not specific to a client instance
    def create_message(who: str, what:str) -> dict[str, str]:
        return {
            "role": who,
            "content": what
        }
    
class ContentFilterClient:

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.openai_client = OpenAIClient(user_id)
        self.ds_client = ds.SocialMediaDataStore(user_id)
   
    def filter_interesting_new_channels(self):  
        return self.filter_interesting_items(
            "subreddits",
            list(map(
                    lambda sr: ContentFilterClient.truncate_media_channel(sr, self.openai_client.model, self.openai_client.max_tokens>>2), #reduce the token length for descritption
                    self.ds_client.get_channels_to_analyze()
                )
            )
        )
    
    def filter_interesting_new_posts(self):
        return self.filter_interesting_items(
            "posts",
            list(map(
                    lambda p: ContentFilterClient.truncate_media_post(p, self.openai_client.model, self.openai_client.max_tokens>>1), #reduce the token length for post_content
                    self.ds_client.get_new_media_posts()
                )
            )
        )
        
    def filter_interesting_items(self, item_type: str, items: list[str]):
        if len(items) == 0: #do nothing for empty list
            print("nothing new")
            return        

        prompt = """My areas of interests are %s.
            The following are a list of reddit %s. 
            Each post metadata is formatted as json blob.
            Provide me a list of %s that matches my interests.
            Output format: 'name' values (that matches regex pattern r'\&gt;|\&lt;|[#\*\s]+' )'. If there is no match respond 'None'. 
            Do NOT additional text before or after the response.""" % (", ".join(self.ds_client.get_areas_of_interest()), item_type, item_type)
        self.openai_client.add_and_run(prompt)

        for m in ContentFilterClient.combine_in_same_message(items, self.openai_client.model, self.openai_client.max_tokens):
            try:
                resp = self.openai_client.add_and_run(m, False)
                print(resp)

                #if the call succeeds mark the this batch as analyzed  
                analyzed = reddit.parse_all_reddit_names(m)  
                self.ds_client.save_status(analyzed, ds.ItemStatus.ANALYZED)

                #from the response extract the name ids and mark them as interesting
                interests = reddit.parse_all_reddit_names(resp)
                self.ds_client.save_status(interests, ds.ItemStatus.INTERESTING) 
                yield resp
            except Exception as e:
                #just print a warning and move on. but do not stop the rest of the execution
                print("We tried but hit %s" % e)
        
        #reset context window regardless
        self.openai_client.reset_context_window()

    def short_list_interesting_channels(self):
        # TODO: temp code. for now just filter on subscriber
        filter_func = lambda ch: ch['subscriber'] > 500
        channels = list(filter(filter_func, self.ds_client.get_channels_to_short_list()))[0:10] # getting top 10 to review        
        self.ds_client.save_status(list(map(lambda ch: ch["name"] ,channels)), ds.ItemStatus.SHORT_LISTED)
        return channels


    # all text operation related functions to NOT cross the rate limit
    # these are general function that are NOT specific to a client instance
    def truncate_media_channel(ch :dict[str, any], model: str, max_tokens: int) -> str:
        blob = {
            "title": ch["title"],
            "name": ch["name"],
            "description": "dummy text" #for buffer
        }
        initial_tcount = ContentFilterClient.count_tokens(json.dumps(blob), model)        
        blob["description"] = ContentFilterClient.truncate_string(
            str(ch["public_description_html"])+ "\n"+ str(ch["description_html"]), 
            model, 
            max_tokens - initial_tcount) #100 is a safety margin
        res = json.dumps(blob)
        return res

    # this is done to truncate message to fit within token size. usually the post_content is large
    def truncate_media_post(p :dict[str, any], model: str, max_tokens: int) -> str:
        blob = {            
            "url": p["url"],
            "name": p["name"],            
            "subreddit": p["subreddit"],
            "title": p["title"],
            "post_content": "dummy text" #for buffer
        }
        initial_tcount = ContentFilterClient.count_tokens(json.dumps(blob), model)
        blob["post_content"] = ContentFilterClient.truncate_string(
            p["selftext_html"], 
            model, 
            max_tokens - initial_tcount) #100 is a safety margin

        return json.dumps(blob)
    
    # this function can truncate a string
    def truncate_string(content: str, model: str, token_length: int) -> str:            
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(content)
        return encoding.decode(tokens[:token_length])
    
    #this function counts the number of tokens in a string
    def count_tokens(content: str, model: str) -> int:    
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(content)
        return len(tokens)
    
    # this is done to combine multiple messages into one request so that RPM and RPD is maintained
    def combine_in_same_message(contents: list[str], model: str, token_length: int):
        combined_msg = ""    
        combined_tcount = 0
        current_content_counter = 0 # TODO: remove this code. this is only for debugging    

        for msg in contents:        
            tcount = ContentFilterClient.count_tokens(msg, model)
            if tcount + combined_tcount < token_length:
                combined_msg = combined_msg + ",\n"+msg            
                combined_tcount += tcount
                current_content_counter += 1 # TODO: remove this line. it is for debug ONLY
            else:
                res = combined_msg            
                # reset                        
                combined_msg = ""
                combined_tcount = 0
                # print("# of digested messages in this batch %d" % current_content_counter) # TODO: remove this line. it is only for debugging
                # current_content_counter = 0 # TODO: remove this line. it is only for debugging            

                yield res
        yield combined_msg 

def main():
    envassist.load_env()
    filter_client = ContentFilterClient("soumitsr@gmail.com")

    """
    for r in filter_client.filter_interesting_new_channels():
        print(r)
    """
    for r in filter_client.filter_interesting_new_posts():
       print(r)
    """


    for r in filter_client.short_list_interesting_channels():
        print(r["name"])
    """
   
    

# run the program
main()