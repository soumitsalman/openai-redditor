import re

def parse_all_reddit_names(text: str):
    pattern = "t\d_\w{2,10}"
    return re.findall(pattern, text)

def scrub_markdown(text: str):
    # removing &gt; &lt; # * and whitespace
    text = re.sub(r'\&gt;|\&lt;|[#\*\s]+',' ', text, flags = re.M)
    return text  