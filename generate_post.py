import os
import requests
import json
from datetime import datetime
import re
from pathlib import Path

# Obter a chave da API do ambiente
api_key = os.getenv("GEMINI_API_KEY")

# Arquivo para armazenar metadados do cache
CACHE_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / ".cache_metadata.json"


def get_cache_info():
    """Recupera informações sobre o cache atual"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None


def save_cache_info(cache_info):
    """Salva informações sobre o cache atual"""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_info, f)


def create_or_update_cache(content, ttl="3600s"):
    """Cria ou atualiza o cache de contexto"""
    cache_info = get_cache_info()

    # Se já existe um cache, tenta deletar antes de criar um novo
    if cache_info and "name" in cache_info:
        try:
            delete_cache(cache_info["name"])
        except Exception as e:
            print(f"Aviso: não foi possível deletar o cache anterior: {e}")

    # Cria um novo cache
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/cachedContents?key={api_key}",
        json={
            "model": "models/gemini-1.5-flash-001",
            "contents": [{"parts": [{"text": content}], "role": "user"}],
            "ttl": ttl,
        },
    )

    if response.status_code != 200:
        print(f"Erro ao criar cache: {response.text}")
        return None

    cache_data = response.json()
    save_cache_info(cache_data)
    return cache_data


def delete_cache(cache_name):
    """Deleta um cache existente"""
    response = requests.delete(
        f"https://generativelanguage.googleapis.com/v1beta/{cache_name}?key={api_key}"
    )
    if response.status_code not in (200, 204):
        print(f"Erro ao deletar cache: {response.status_code} - {response.text}")
        raise Exception(f"Falha ao deletar cache: {response.status_code}")
    return True


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
Ensure the final result includes the title, categories, tags, and body of the post.
"""  # noqa

    if last_post:
        context_prompt = f"""
For reference, this was the last post you generated:
Title: {last_post['filename']}

{last_post['content']}

Please create a new post on a different topic. Don't repeat the same subject or approach as the previous post, but reference it in a subtle way.
"""
        return base_prompt + context_prompt

    return base_prompt


# Recupera o último post para contexto
last_post = get_last_post_content()
prompt = create_prompt(last_post)

print(f"Ultimo post: {last_post['filename'] if last_post else 'nenhum'}")

# Verifica se existe um cache para usar
cache_info = get_cache_info()
cache_name = cache_info["name"] if cache_info and "name" in cache_info else None

# Preparar o JSON da requisição
req_json = {
    "systemInstruction": {
        "parts": [
            {
                "text": "Your name is R. Daneel Olivaw and you are a programming, technology and software development expert who regularly posts on Cleisson Barbosa's blog, Cleissonbarbosa.github.io"  # noqa
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

# Adiciona o cache se existir
if cache_name:
    req_json["cachedContent"] = cache_name

# Chamar a API do Gemini
response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-001:generateContent?key={api_key}",
    json=req_json,
)

# Obter a resposta da IA
data = response.json()
try:
    generated_text = data["candidates"][0]["content"]["parts"][0]["text"]
    print(f"Texto gerado completo: {len(generated_text)} caracteres")

    # Separar título, categorias, tags e conteúdo de forma mais robusta
    lines = generated_text.strip().split("\n")
    title = lines[0].strip().replace('"', "").replace("#", "").strip()

    # Encontra a primeira linha não vazia após o título para categorias
    line_index = 1
    while line_index < len(lines) and not lines[line_index].strip():
        line_index += 1

    categories = (
        lines[line_index].strip().lower().replace("categorias:", "").strip()
        if line_index < len(lines)
        else ""
    )
    line_index += 1

    # Encontra a primeira linha não vazia após categorias para tags
    while line_index < len(lines) and not lines[line_index].strip():
        line_index += 1

    tags = (
        lines[line_index].strip().lower().replace("tags:", "").strip()
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

_Este post foi gerado totalmente por uma IA autonoma, sem intervenção humana._
"""
# Escrever o arquivo Markdown
with open(filename, "w") as f:
    f.write(front_matter + content + "\n\n---" + generated_by)

print(f"Post gerado: {filename}")

# Depois de gerar um novo post, atualiza o cache com ele
full_post_content = front_matter + content + "\n\n---" + generated_by
create_or_update_cache(
    f"Este é o post mais recente que você gerou:\n{full_post_content}"
)

if "GITHUB_OUTPUT" in os.environ:
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"post_title={title}\n")
        f.write(f"post_slug={slug}\n")
        f.write(f"post_categories={categories}\n")
        f.write(f"post_tags={tags}\n")
        f.write(f"post_filename={filename}\n")
