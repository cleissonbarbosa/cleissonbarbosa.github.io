import os
import requests
from datetime import datetime
import re

# Obter a chave da API do ambiente
api_key = os.getenv("GEMINI_API_KEY")

# Prompt para a IA gerar o post
prompt = """
Create a complete blog post in Markdown format about a random programming-related topic, following the instructions below.
Start by writing a captivating title in Portuguese for the post in raw format without any formatting.
On the next line, write suggested categories in Portuguese for the post, separated by commas, based on the topic. Just write the categories (e.g., a,b,c)
On the following line, write relevant tags in Portuguese for the post, also separated by commas, based on the topic. Just write the tags (e.g., a,b,c)
Leave a blank line, then begin the body of the post.
Write the body of the post in Portuguese, using an informal and conversational tone in the first person. Format the entire body in Markdown, using the correct syntax for headers, lists, and emphasis. Whenever including a link, use the format [<TEXT>](<URL>){:target="_blank"} to ensure it opens in a new tab.
Structure the post with an engaging introduction, a detailed body exploring the topic, and a conclusion summarizing your reflections. Include personal anecdotes, opinions, or experiences to make it authentic and relatable.
Ensure the final result includes the title, categories, tags, and body of the post.
"""  # noqa

# Chamar a API da OpenAI
response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
    json={
        "systemInstruction": {
            "parts": [
                {
                    "text": "You are an expert in programming, technology, and software development."  # noqa
                }
            ]
        },
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH",
            }
        ],
        "generationConfig": {
            "stopSequences": ["Title"],
            "temperature": 1.0,
            "maxOutputTokens": 800,
            "topP": 0.8,
            "topK": 10,
        },
    },
)

# Obter a resposta da IA
data = response.json()
generated_text = data["candidates"][0]["content"]["parts"][0]["text"]

# Separar título (primeira linha) e conteúdo (resto)
lines = generated_text.split("\n")
title = lines[0].strip()
categories = lines[2].strip() if lines[1].strip() == "" else lines[1].strip()
tags = lines[3].strip() if lines[1].strip() == "" else lines[2].strip()
content = (
    "\n".join(lines[4:]).strip()
    if lines[1].strip() == ""
    else "\n".join(lines[3:]).strip()
)

# Criar um slug simples para o título
slug = re.sub(r"\W+", "-", title.lower()).strip("-")

# Obter a data atual no formato YYYY-MM-DD
date = datetime.now().strftime("%Y-%m-%d")

# Nome do arquivo no formato Jekyll
filename = f"_posts/{date}-{slug}.md"

# Front matter para o post
front_matter = f"""---
title: "{title}"
author: ia
date: {date} 00:00:00 -0300
image:
  path: /assets/img/posts/ia-generated.png
  alt: "{title}"
categories: [{categories}]
tags: [{tags}, ai-generated]
---

"""

generated_by = """
_Este post foi gerado totalmente por uma IA_
"""
# Escrever o arquivo Markdown
with open(filename, "w") as f:
    f.write(front_matter + content + "\n\n---" + generated_by)

print(f"Post gerado: {filename}")

if "GITHUB_OUTPUT" in os.environ:
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"post_title={title}\n")
        f.write(f"post_slug={slug}\n")
        f.write(f"post_categories={categories}\n")
        f.write(f"post_tags={tags}\n")
        f.write(f"post_filename={filename}\n")
