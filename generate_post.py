import os
import requests
from datetime import datetime
import re
import random
from pathlib import Path

# Obter a chave da API do ambiente
api_key = os.getenv("GEMINI_API_KEY")


def get_last_post_content():
    """Recupera o conteúdo do último post para contexto"""
    posts_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "_posts"
    post_files = list(posts_dir.glob("*.md"))

    if not post_files:
        return None

    # Ordena por data de modificação (mais recente primeiro)
    last_post_file = sorted(post_files, key=lambda p: p.stat().st_mtime, reverse=True)[
        0
    ]

    try:
        with open(last_post_file, "r", encoding="utf-8") as f:
            content = f.read()
            return {"filename": last_post_file.name, "content": content}
    except Exception as e:
        print(f"Erro ao ler o último post: {e}")
        return None


# Prompt para a IA gerar o post
def create_prompt(last_post=None):
    base_prompt = """
Create a complete blog post in Markdown format about a random programming-related topic, following the instructions below.
Start by writing a captivating title in Portuguese for the post in raw format without any formatting.
On the next line, write suggested categories in Portuguese for the post, separated by commas, based on the topic. Just write the categories (e.g., a,b,c)
On the following line, write relevant tags in Portuguese for the post, also separated by commas, based on the topic. Just write the tags (e.g., a,b,c)
Leave a blank line, then begin the body of the post.
Write the body of the post in Portuguese, using an informal and conversational tone in the first person. Format the entire body in Markdown, using the correct syntax for headers, lists, and emphasis. Whenever including a link, use the format [TEXT](URL){:target="_blank"} to ensure it opens in a new tab.
Structure the post with an engaging introduction, a detailed body exploring the topic, and a conclusion summarizing your reflections. Include personal anecdotes, opinions, or experiences to make it authentic and relatable.
Ensure the final result includes the title, categories, tags, and body of the post. just write the content without any additional explanations or comments.
"""  # noqa

    if last_post:
        context_prompt = f"""
For reference, this was the last post you generated:
Title: {last_post['filename']}
url: https://cleissonbarbosa.github.io/posts/{last_post['filename'].replace('.md', '')[10:]}

{last_post['content']}

Please create a new post on a different topic. Don't repeat the same subject or approach as the previous post, but reference it in a subtle way.
"""
        return base_prompt + context_prompt

    return base_prompt


# Recupera o último post para contexto
last_post = get_last_post_content()
prompt = create_prompt(last_post)

print(f"Ultimo post: {last_post['filename'] if last_post else 'nenhum'}")

# Preparar o JSON da requisição
req_json = {
    "systemInstruction": {
        "parts": [
            {
                "text": "Your name is R. Daneel Olivaw and you are a programming, technology and software development expert who regularly posts on Cleisson Barbosa's blog, cleissonbarbosa.github.io"  # noqa
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
        "maxOutputTokens": 6000,
        "topP": 0.8,
        "topK": 10,
    },
}

model = random.choice(
    [
        "gemini-1.5-flash-001",
        "gemini-2.0-flash-001",
        "gemini-2.0-pro-exp-02-05",
        "gemini-2.0-flash-thinking-exp-01-21",
    ]
)
print(f"Modelo: {model}")

# Chamar a API do Gemini
response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
    json=req_json,
)

# Obter a resposta da IA
data = response.json()
try:
    generated_text = data["candidates"][0]["content"]["parts"][0]["text"]
    print(f"Texto gerado completo: {len(generated_text)} caracteres")

    # Separar título, categorias, tags e conteúdo de forma mais robusta
    lines = generated_text.strip().split("\n")
    title = (
        lines[0]
        .strip()
        .replace('"', "")
        .replace("#", "")
        .replace("title:", "")
        .replace("Title:", "")
        .strip()
    )

    # Encontra a primeira linha não vazia após o título para categorias
    line_index = 1
    while line_index < len(lines) and not lines[line_index].strip():
        line_index += 1

    categories = (
        lines[line_index]
        .strip()
        .lower()
        .replace("categorias:", "")
        .replace("categories:", "")
        .replace("[", "")
        .replace("]", "")
        .strip()
        if line_index < len(lines)
        else ""
    )
    line_index += 1

    # Encontra a primeira linha não vazia após categorias para tags
    while line_index < len(lines) and not lines[line_index].strip():
        line_index += 1

    tags = (
        lines[line_index]
        .strip()
        .lower()
        .replace("tags:", "")
        .replace("[", "")
        .replace("]", "")
        .strip()
        if line_index < len(lines)
        else ""
    )
    line_index += 1

    # Restante é conteúdo, excluindo linhas vazias iniciais
    while line_index < len(lines) and not lines[line_index].strip():
        line_index += 1

    content = "\n".join(lines[line_index:]).strip() if line_index < len(lines) else ""

    print(f"Título: {title}")
    print(f"Categorias: {categories}")
    print(f"Tags: {tags}")
    print(f"Tamanho do conteúdo: {len(content)} caracteres")

except KeyError as e:
    print(f"Erro ao processar resposta da API: {e}")
    print(f"Dados recebidos: {data}")
    raise

# Criar um slug simples para o título
slug = re.sub(r"\W+", "-", title.lower()).strip("-")

# Obter a data atual no formato YYYY-MM-DD
date = datetime.now().strftime("%Y-%m-%d")

# Nome do arquivo no formato padrão
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

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post.py){:target="_blank"}
"""
# Escrever o arquivo Markdown
with open(filename, "w") as f:
    f.write(front_matter + content + "\n\n---" + generated_by)

print(f"Post gerado: {filename}")

if "GITHUB_OUTPUT" in os.environ:
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(
            f"""post_title={title}
            post_slug={slug}
            post_categories={categories}
            post_tags={tags}
            post_filename={filename}
            """
        )
