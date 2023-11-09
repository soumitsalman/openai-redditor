import json

location_dir = "C:\\Users\\soumi\\go-stuff\\reddit_data_dump\\"
joined_subreddits = location_dir+"joined_subreddits.json"
recommened_subreddits = location_dir+"recommended_subreddits.json"
posts = location_dir+"posts.json"
config = location_dir+"config.json"

def get_user_details():         
    with open(config, encoding = "utf-8") as f:
        blob = json.load(f)
    return blob

# this is expected to return an arreay
def get_areas_of_interest():
    # TODO: pull in from a database for the specific user
    return ["cyber security", "new software products", "software development", "api integration", "generative ai", "software product management", "software program management", "autonomous vehicle", "cloud infrastructure", "information security"]


# this is expected to return an array
def get_subscribed_channels():
    # TODO: pull in from a database for the specific user
    with open(joined_subreddits, encoding='utf-8') as f:
        joined_sr = json.load(f)

    return joined_sr

# this is expected to return an array
def get_recommended_channels() -> list[dict[str, any]]:    
    # TODO: pull in from a database for the specific user
    with open(recommened_subreddits, encoding='utf-8') as f:
        rec_sr = json.load(f)["subreddits"]

    return list(filter(lambda sr: not sr["already_subscribed"], rec_sr))

# this is expected return an array of posts with self contents
# it will filter out links, images and videos for now
def get_recommended_posts():
    with open(posts, encoding='utf-8') as f:
        rec_posts = json.load(f)["posts"]
    # TODO: filter out posts for which there is already a user response
    user_name = get_user_details()["user_name"]
    post_filter = lambda p: p["post_content"] != "" and p["author"] != user_name

    return list(filter(post_filter, rec_posts))
    