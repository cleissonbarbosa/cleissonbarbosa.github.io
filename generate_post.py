import os
import requests
import base64
from datetime import datetime
import re
import random
import sys
from pathlib import Path
import uuid
import json
import time
from functools import wraps
from requests.exceptions import RequestException

# Obter as chaves da API do ambiente
api_key = os.getenv("GEMINI_API_KEY")
cf_api_token = os.getenv("CF_AI_API_KEY")
cf_account_id = os.getenv("CF_ACCOUNT_ID")

# Diretório de assets para posts
ASSETS_DIR = (
    Path(os.path.dirname(os.path.abspath(__file__))) / "assets" / "img" / "posts"
)

# Configuração de retries
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos


def retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY):
    """Decorator para implementar retry em funções"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            last_exception = None

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    wait_time = delay * (2 ** (attempts - 1))  # Exponential backoff
                    print(
                        f"Tentativa {attempts}/{max_attempts} falhou: {str(e)}. Aguardando {wait_time}s..."
                    )
                    time.sleep(wait_time)

            print(
                f"Todas as {max_attempts} tentativas falharam. Último erro: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


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
url: https://cleissonbarbosa.github.io/posts/{last_post['filename'].replace('.md', '')[11:]}

{last_post['content']}

Please create a new post on a different topic. Don't repeat the same subject or approach as the previous post, but reference it in a subtle way.
"""
        return base_prompt + context_prompt

    return base_prompt


def create_image_prompt(title, categories, tags, content_preview):
    """Cria um prompt para a IA gerar uma imagem relacionada ao post"""
    prompt = f"""Create a detailed, visually appealing illustration that represents the following blog post topic:
Title: {title}
Categories: {categories}
Tags: {tags}
Content preview: {content_preview[:500]}...

The image should be a professional, high-quality digital artwork that captures the essence of the programming/technology topic.
Include relevant symbols, code elements, and visual metaphors related to the technical concepts mentioned.
Style: Modern, clean, with a tech aesthetic. Use vibrant colors that complement each other.
Make it visually engaging for a programming blog.
use the reference image as background
"""
    return prompt


def get_base_image_path():
    """Obtém o caminho para uma imagem base aleatória"""
    base_images_dir = ASSETS_DIR / "base"
    if not base_images_dir.exists():
        os.makedirs(base_images_dir, exist_ok=True)

    # Selecionar uma imagem base aleatória
    base_images = list(base_images_dir.glob("*.png")) + list(
        base_images_dir.glob("*.jpg")
    )
    if not base_images:
        return get_base_image_path()  # Chamada recursiva para criar imagem base padrão

    return random.choice(base_images)


@retry(max_attempts=3, delay=3)
def generate_image(title, categories, tags, content_preview):
    """Gera uma imagem relacionada ao post usando Cloudflare Workers AI com retry"""
    if not cf_api_token or not cf_account_id:
        print("Chaves da API Cloudflare não encontradas. Pulando geração de imagem.")
        return None

    # Obter imagem base
    base_image_path = get_base_image_path()
    print(f"Usando imagem base: {base_image_path}")

    # Ler a imagem base
    with open(base_image_path, "rb") as f:
        image_data = f.read()
        image_b64 = base64.b64encode(image_data).decode("utf-8")

    # Criar prompt para a imagem
    prompt = create_image_prompt(title, categories, tags, content_preview)
    print(f"Prompt da imagem: {prompt[:100]}...")

    # Preparar o JSON para a chamada da API
    req_json = {
        "prompt": prompt,
        "image_b64": image_b64,
        "negative_prompt": "poor quality, low resolution, bad anatomy, text, watermark, signature",
        "num_steps": 20,
        "guidance": 8.5,
        "strength": 0.5,
        "width": 630,
        "height": 1200,
    }

    # Chamar a API do Cloudflare Workers AI
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/@cf/runwayml/stable-diffusion-v1-5-img2img"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json",
    }

    print(f"Fazendo requisição para: {url}")
    response = requests.post(url, headers=headers, json=req_json, timeout=120)

    # Verificar resposta
    if response.status_code != 200:
        error_msg = f"Erro ao gerar imagem. Status code: {response.status_code}, Resposta: {response.text[:500]}"
        print(error_msg)
        raise RequestException(error_msg)

    # Verificar o tipo de conteúdo da resposta
    content_type = response.headers.get("Content-Type", "")
    print(f"Tipo de conteúdo da resposta: {content_type}")

    # Gerar um UUID único para o arquivo
    image_uuid = str(uuid.uuid4())
    image_filename = f"{image_uuid}.png"
    image_path = ASSETS_DIR / image_filename

    # Criar diretório se não existir
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Se a resposta já for uma imagem direta (conteúdo binário)
    if (
        "image/png" in content_type
        or "image/jpeg" in content_type
        or response.content.startswith(b"\x89PNG")
        or response.content.startswith(b"\xff\xd8\xff")
    ):
        with open(image_path, "wb") as f:
            f.write(response.content)
        print(f"Imagem binária recebida e salva: {image_path}")
        return f"/assets/img/posts/{image_filename}"

    # Caso seja JSON, tentar processar
    try:
        data = response.json()

        if not data.get("success", False):
            error_msg = f"Erro na resposta da API: {data}"
            print(error_msg)
            raise RequestException(error_msg)

        # Verificar se result existe
        if "result" not in data:
            error_msg = f"Campo 'result' não encontrado na resposta: {data}"
            print(error_msg)
            raise RequestException(error_msg)

        image_data = data["result"]

        # Salvar imagem decodificada de base64
        with open(image_path, "wb") as f:
            decoded_image = base64.b64decode(image_data)
            f.write(decoded_image)
            print(f"Imagem JSON decodificada e salva: {image_path}")
            return f"/assets/img/posts/{image_filename}"

    except json.JSONDecodeError:
        # Se não for JSON nem imagem reconhecível, salvar resposta bruta como fallback
        print(f"Resposta não é JSON. Salvando como imagem direta.")
        with open(image_path, "wb") as f:
            f.write(response.content)
        print(f"Conteúdo da resposta salvo como imagem: {image_path}")
        return f"/assets/img/posts/{image_filename}"


@retry(max_attempts=3, delay=5)
def generate_post_content(prompt, model_name):
    """Gera o conteúdo do post usando a API Gemini com retry"""
    if not api_key:
        raise ValueError("Chave da API Gemini não encontrada")

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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    print(f"Fazendo requisição para o modelo: {model_name}")

    response = requests.post(url, json=req_json, timeout=120)

    if response.status_code != 200:
        error_msg = f"Falha ao gerar post. Status: {response.status_code}, Resposta: {response.text[:500]}"
        print(error_msg)
        raise RequestException(error_msg)

    data = response.json()
    if (
        "candidates" not in data
        or not data["candidates"]
        or "content" not in data["candidates"][0]
    ):
        error_msg = f"Formato de resposta inválido: {data}"
        print(error_msg)
        raise ValueError(error_msg)

    return data["candidates"][0]["content"]["parts"][0]["text"]


def parse_post_content(generated_text):
    """Extrai título, categorias, tags e conteúdo do texto gerado"""
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

    return {"title": title, "categories": categories, "tags": tags, "content": content}


def main():
    """Função principal para gerar o post"""
    try:
        # Recupera o último post para contexto
        last_post = get_last_post_content()
        prompt = create_prompt(last_post)

        print(f"Ultimo post: {last_post['filename'] if last_post else 'nenhum'}")

        # Selecionar modelo aleatório
        model = random.choice(
            [
                "gemini-1.5-flash-001",
                "gemini-2.0-flash-001",
                "gemini-2.0-pro-exp-02-05",
                "gemini-2.0-flash-thinking-exp-01-21",
            ]
        )
        print(f"Modelo selecionado: {model}")

        # Gerar conteúdo do post com retry
        generated_text = generate_post_content(prompt, model)
        print(f"Texto gerado completo: {len(generated_text)} caracteres")

        # Extrair informações
        post_data = parse_post_content(generated_text)
        title = post_data["title"]
        categories = post_data["categories"]
        tags = post_data["tags"]
        content = post_data["content"]

        print(f"Título: {title}")
        print(f"Categorias: {categories}")
        print(f"Tags: {tags}")
        print(f"Tamanho do conteúdo: {len(content)} caracteres")

        # Criar um slug simples para o título
        slug = re.sub(r"\W+", "-", title.lower()).strip("-")

        # Obter a data atual no formato YYYY-MM-DD
        date = datetime.now().strftime("%Y-%m-%d")

        # Gerar imagem para o post com retry
        image_path = generate_image(title, categories, tags, content)
        image_rel_path = (
            image_path if image_path else "/assets/img/posts/ia-generated.png"
        )

        # Nome do arquivo no formato padrão
        filename = f"_posts/{date}-{slug}.md"

        # Front matter para o post
        front_matter = f"""---
title: "{title}"
author: ia
date: {date} 00:00:00 -0300
image:
  path: {image_rel_path}
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
        print(f"Imagem do post: {image_rel_path}")

        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(
                    f"""post_title={title}
post_slug={slug}
post_categories={categories}
post_tags={tags}
post_filename={filename}
post_image={image_rel_path}
"""
                )

        return True

    except Exception as e:
        print(f"Erro durante a geração do post: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
