import tiktoken
import openai
import os
import backoff
import re
import redditutils
import json
from openai.types.chat.completion_create_params import ResponseFormat

POST_EDITOR_MODEL = "gpt-4-1106-preview"
CONTENT_FILTER_MODEL = "gpt-3.5-turbo-1106"
MAX_TOKENS = 3000


class OpenAIRedditorClient:
    
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization=os.getenv("OPENAI_ORG_ID")
        )
        # TODO: only temporarily. remove this
        self.thread = [create_message("system", "you are text search agent. You look into given a bulk of given text and match what is asked")]
        self.model = CONTENT_FILTER_MODEL
        self.search_files = {}
        self.max_tokens = MAX_TOKENS

    def add(self, what: str):
        self.thread.append(create_message("user", what))
    
    @backoff.on_exception(
            wait_gen=backoff.constant, 
            interval = 90, 
            max_time = 120, 
            max_tries = 5,            
            exception=openai.RateLimitError)
    def add_and_run(self, what: str, forget:bool = False) -> str:
        
        msgs_to_send = self.thread + [create_message("user", what)]
        completion = self.client.chat.completions.create(
            model = self.model,
            messages = msgs_to_send,
            temperature=0.1,            
            seed = 4
        )
        msg = completion.choices[0].message
        if not forget: #remember the thread
            self.thread = msgs_to_send + [create_message(msg.role, msg.content)]
        return msg.content
     
    @backoff.on_exception(
            wait_gen = backoff.constant, 
            interval = 90, 
            max_time = 120, 
            max_tries = 5,
            exception = openai.RateLimitError)
    def upload_file(self, path: str, topic: str) -> str:
        with open(path, "rb") as f:
            file_id = self.client.files.create(file = f, purpose="assistants").id
        self.search_files[topic] = file_id
        return file_id

 
def create_message(who: str, what:str) -> dict[str, str]:
    return {
        "role": who,
        "content": what
    }

def scrub_markdown(text: str):
    # removing &gt; &lt; # * and whitespace
    text = re.sub(r'\&gt;|\&lt;|[#\*\s]+',' ', text, flags = re.M)
    return text

def count_tokens(content: str, model: str) -> int:    
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(content)
    return len(tokens)

def truncate_string(content: str, model: str, max_tokens: int) -> str:    
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(content)
    return encoding.decode(tokens[:max_tokens])

def truncate_subreddit(sr : dict[str, any], model: str, max_tokens: int) -> str:
    return json.dumps({
        "title": sr["title"],
        "display_name": sr["display_name"],
        "description": truncate_string(scrub_markdown(str(sr["public_description"])+ " "+ str(sr["description"])), model, max_tokens)
    })

def truncate_post(p :dict[str, any], model: str, max_tokens: int) -> str:
    return json.dumps({
        "contained_url": p["contained_url"],
        "url": p["url"],
        "name": p["name"],
        "post_content": truncate_string(scrub_markdown(p["post_content"]), model, max_tokens),
        "subreddit": p["subreddit"],
        "title": p["title"]
    })
    

def combine_in_same_message(prompt: str, contents: list[str], model: str, max_tokens: int):
    
    prompt_tcount = count_tokens(prompt, model)
    
    current_msg = prompt    
    current_tcount = prompt_tcount
    current_titles = "" # TODO: remove this code. this is only for debugging    

    for msg in contents:        
        tcount = count_tokens(msg, model)
        if tcount + current_tcount < max_tokens:
            current_msg = current_msg + ",\n"+msg
            current_titles = current_titles + ", " + json.loads(msg)["name"] # TODO: remove this line. it is for debug ONLY
            current_tcount += tcount
        else:
            res = current_msg
            print("this batch includes %s-->" % current_titles)
            # reset                        
            current_msg = prompt
            current_titles = ""
            current_tcount = prompt_tcount

            yield res
    yield current_msg 

def bulk_prompt_add_run_and_forget(client: OpenAIRedditorClient, prompt: str, messages: list[str]):        
    for msg in combine_in_same_message(prompt, messages, client.model, client.max_tokens):                      
        #resp = ""
        resp = client.add_and_run(msg, True)
        yield resp

def filter_new_subreddits(client: OpenAIRedditorClient):   

    # another option is to add multiple messages
    #client.add("my areas of interests are %s" % ", ".join(redditutils.get_areas_of_interest()))

    prompt = """my areas of interests are %s.
The following are a list of subreddits' metadata. 
Each subreddit metadata is formatted as json blob. 
Provide me a rank ordered list of subreddits that match my interests
Output format: 'display_name' ONLY. If there is no match respond None. 
Do not additional text before or after the response.""" % (", ".join(redditutils.get_areas_of_interest()))
    #subreddits = redditutils.get_recommended_channels()
    sr_digests = list(map(
        lambda sr: truncate_subreddit(sr, client.model, client.max_tokens - count_tokens(prompt, client.model) - 30), #reducing the number of tokens based prompt length and json padding
        redditutils.get_recommended_channels()))
    return bulk_prompt_add_run_and_forget(client, prompt, sr_digests)

def filter_new_posts(client: OpenAIRedditorClient):
    #another option is to add multiple messages
    #client.add("my areas of interests are %s" % ", ".join(redditutils.get_areas_of_interest()))

    prompt = """My areas of interests are %s.
The following are a list of subreddit posts. 
Each post metadata is formatted as json blob.
Provide me a rank ordered list of posts that matches my interests.
Output format: ['subreddit'] 'title' ONLY. If there is no match respond None. 
Do not additional text before or after the response.""" % ", ".join(redditutils.get_areas_of_interest())
    #posts = redditutils.get_recommended_posts()
    post_digests = list(map(
        lambda p: truncate_post(p, client.model, client.max_tokens - count_tokens(prompt, client.model) - 30), #reducing the number of tokens based prompt length and json padding
        redditutils.get_recommended_posts()))
    return bulk_prompt_add_run_and_forget(client, prompt, post_digests)



def main():
    msger = OpenAIRedditorClient()
    # filter_new_subreddits(msger)
    for r in filter_new_posts(msger):
        print(r)
    



# run the program
main()