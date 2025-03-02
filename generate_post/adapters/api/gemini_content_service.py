import random
import requests
from typing import Dict, Optional

from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.utils.retry_decorator import retry


class GeminiContentService(ContentGeneratorServiceInterface):
    """Implementação do serviço de geração de conteúdo usando a API Gemini"""

    def create_prompt(self, last_post: Optional[Dict] = None) -> str:
        """Cria um prompt para geração de conteúdo"""
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
Title: {last_post.get('filename', '')}
url: https://cleissonbarbosa.github.io/posts/{last_post.get('filename', '').replace('.md', '')[11:]} 

{last_post.get('content', '')}

Please create a new post on a different topic. Don't repeat the same subject or approach as the previous post, but reference it in a subtle way.
"""  # noqa
            return base_prompt + context_prompt

        return base_prompt

    @retry(max_attempts=3, delay=5)
    def generate_content(self, prompt: str) -> str:
        """Gera conteúdo a partir de um prompt usando a API Gemini"""
        api_key = EnvConfig.get_gemini_api_key()
        if not api_key:
            raise ValueError("Chave da API Gemini não encontrada")

        # Seleção de modelo
        model_name = random.choice(
            [
                "gemini-1.5-flash-001",
                "gemini-2.0-flash-001",
                "gemini-2.0-pro-exp-02-05",
                "gemini-2.0-flash-thinking-exp-01-21",
            ]
        )

        print(f"Modelo selecionado: {model_name}")

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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"  # noqa
        print(f"Fazendo requisição para o modelo: {model_name}")

        response = requests.post(url, json=req_json, timeout=120)

        if response.status_code != 200:
            error_msg = f"Falha ao gerar post. Status: {response.status_code}, Resposta: {response.text[:500]}"  # noqa
            print(error_msg)
            raise requests.RequestException(error_msg)

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

    def parse_generated_content(self, generated_text: str) -> Dict:
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

        content = (
            "\n".join(lines[line_index:]).strip()
            if line_index < len(lines)
            else ""  # noqa
        )

        return {
            "title": title,
            "categories": categories,
            "tags": tags,
            "content": content,
        }
