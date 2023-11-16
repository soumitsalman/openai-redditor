import time
import openai
import json

ASSIST_ID = "asst_vxIDX2v9qcAwhB9B5inBbBEs"
MESSAGE_EXAMPLE = {
      "contained_url": "https://www.reddit.com/r/ProductManagement/comments/17qpi4a/have_you_ever_taken_extended_time_away_to_cure/",
      "container_sr_subscribers": 133664,
      "created": "2023-11-08T12:32:29-04:00",      
      "num_comments": 100,
      "post_content": "Asking because Im considering taking 3 - 6 months off from work/PM to reset.\n\nIve been doing the PM thing for 7+ years now, and at this point, Im just tired of the grind. Lately, I wake up every day with this feeling of dread, which is the total opposite of how I felt as little as a year ago.\n\nI do think my current situation sucks (unsupportive manager, several quarters of company missing revenue targets, needlessly hectic environment, very political organization), but I dont think just moving to a new company will fix things. I also dont think taking a sabbatical/long vacation will work, since I would go back to the same working situation that I am currently in.\n\nHave any of you ever been in this situation before? What did you do?\n\nE: Have any of you NOT burnt out? How have you handled your career as a PM to avoid burning out?",
      "subreddit": "ProductManagement",
      "title": "Have you ever taken extended time away to cure burnout?",
      "url": "https://www.reddit.com/r/ProductManagement/comments/17qpi4a/have_you_ever_taken_extended_time_away_to_cure/"
    }

def show_json(content):
    print(json.loads(content.model_dump_json()))

def wait_on_run(client, run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id = thread.id,
            run_id = run.id
        )
        time.sleep(10)
    return run

def print_messages(messages):
    for m in messages:
        print("%s: %s" % (m.role, m.content[0].text.value))

def main():
    client = openai.OpenAI()

    # assistant = client.beta.assistants.create(
    #     name = "coco-wave-3",
    #     instructions="You are a social media assistant. You provide suggested response for reddit posts",
    #     model = "gpt-3.5-turbo-1106"
    # )
    # show_json(assistant)

    thread = client.beta.threads.create()
    message = client.beta.threads.messages.create(
        thread_id = thread.id,
        role = "user",
        content = "Create a response for the following reddit post: " + json.dumps(MESSAGE_EXAMPLE)

    )
    #show_json(message)
    run = client.beta.threads.runs.create(
        thread_id = thread.id,
        assistant_id=ASSIST_ID,
    )
    run = wait_on_run(client, run, thread)
    #show_json(run)
    resp = client.beta.threads.messages.list(thread_id = thread.id)
    print_messages(resp)

main()
