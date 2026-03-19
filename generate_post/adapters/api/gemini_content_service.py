import logging
import random
import re
import requests
from typing import Dict, Optional

from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
]

_SYSTEM_INSTRUCTION = (
    "Você é R. Daneel Olivaw, um engenheiro de software sênior "
    "com mais de 15 anos de experiência em diversas linguagens e "
    "frameworks. Você escreve posts técnicos autorais para o blog "
    "de Cleisson Barbosa (cleissonbarbosa.github.io). Seu estilo é "
    "direto, prático e envolvente — você compartilha experiências "
    "reais de projetos, erros que cometeu, soluções que descobriu "
    "e opiniões fundamentadas sobre tecnologia. Escreva sempre em "
    "português brasileiro com tom informal mas tecnicamente preciso. "
    "Você nunca menciona que é uma IA — você é um autor humano do blog."
)

# Regex compilado para limpeza do título
_TITLE_CLEAN_RE = re.compile(r'["#]|(?:title:|Title:)')
_LABEL_CLEAN_RE = re.compile(r"(?:categorias:|categories:|tags:|\[|\])", re.IGNORECASE)


class GeminiContentService(ContentGeneratorServiceInterface):
    """Implementação do serviço de geração de conteúdo usando a API Gemini"""

    def __init__(self, env_config: Optional[EnvConfig] = None):
        self._env = env_config or EnvConfig.from_env()
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def create_prompt(self, last_post: Optional[Dict] = None) -> str:
        """Cria um prompt para geração de conteúdo"""
        base_prompt = """
## TAREFA
Crie um post completo para blog de programação em formato Markdown.

## FORMATO DE SAÍDA (siga exatamente esta estrutura)
Linha 1: Título criativo e envolvente em português (texto puro, sem formatação, sem aspas, sem #)
Linha 2: Categorias em português, separadas por vírgula (ex: programação,rust,web)
Linha 3: Tags em português, separadas por vírgula (ex: rust,webassembly,performance)
Linha 4: (em branco)
Linha 5 em diante: Corpo do post em Markdown

## REGRAS DO CONTEÚDO
- Idioma: português brasileiro
- Tom: informal, conversacional, primeira pessoa — como um dev experiente explicando para colegas
- Extensão: entre 1500 e 3000 palavras no corpo
- Inclua experiências pessoais, opiniões e analogias para tornar o conteúdo autêntico
- Use exemplos de código quando relevante (com syntax highlighting via ```) 
- Links devem usar o formato: [TEXTO](URL){:target="_blank"}
- Use headers (##, ###), listas, **negrito** e *itálico* adequadamente
- NÃO inclua front matter YAML — apenas título, categorias, tags e corpo
- NÃO adicione explicações, comentários ou metadados fora do formato especificado

## ESTRUTURA DO CORPO
1. **Introdução envolvente**: Hook que prenda a atenção, contextualize o problema ou tema
2. **Desenvolvimento**: Explore o tema em profundidade com seções claras, código de exemplo e explicações práticas
3. **Conclusão**: Reflexões finais, aprendizados e próximos passos para o leitor

## RESTRIÇÕES
- Escolha um tópico específico e atual de programação/tecnologia (não seja genérico)
- Evite clichês como "no mundo cada vez mais digital" ou "nos dias de hoje"
- Não repita frases ou parágrafos
- Não use emojis em excesso
"""

        if last_post:
            filename = last_post.get("filename", "")
            slug = filename.replace(".md", "")[11:] if len(filename) > 11 else ""
            base_prompt += f"""
## CONTEXTO: ÚLTIMO POST PUBLICADO
Título: {filename}
URL: https://cleissonbarbosa.github.io/posts/{slug}

Resumo do conteúdo anterior:
{last_post.get('content', '')[:1000]}

## INSTRUÇÕES ADICIONAIS
- Escolha um tópico DIFERENTE do post anterior
- Pode fazer referência sutil ao post anterior como conexão natural entre os conteúdos
- Varie a abordagem: se o anterior foi tutorial, faça uma análise; se foi teórico, seja mais prático
"""

        return base_prompt

    @retry(max_attempts=3, delay=5)
    def generate_content(self, prompt: str) -> str:
        """Gera conteúdo a partir de um prompt usando a API Gemini"""
        self._env.validate_gemini()

        model_name = random.choice(_MODELS)
        logger.info("Modelo selecionado: %s", model_name)

        req_json = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 8192,
                "topP": 0.95,
                "topK": 40,
            },
        }

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model_name}:generateContent"
        )

        response = self._session.post(
            url,
            headers={"x-goog-api-key": self._env.gemini_api_key},
            json=req_json,
            timeout=120,
        )

        if response.status_code != 200:
            raise requests.RequestException(
                f"Falha ao gerar post. Status: {response.status_code}, "
                f"Resposta: {response.text[:500]}"
            )

        data = response.json()
        candidates = data.get("candidates")
        if not candidates or "content" not in candidates[0]:
            raise ValueError(f"Formato de resposta inválido: {data}")

        return candidates[0]["content"]["parts"][0]["text"]

    def parse_generated_content(self, generated_text: str) -> Dict:
        """Extrai título, categorias, tags e conteúdo do texto gerado"""
        lines = generated_text.strip().split("\n")

        title = _TITLE_CLEAN_RE.sub("", lines[0]).strip()

        # Avança para a próxima linha não-vazia (categorias)
        idx = _next_non_empty(lines, 1)
        categories = (
            _LABEL_CLEAN_RE.sub("", lines[idx]).strip().lower()
            if idx < len(lines)
            else ""
        )

        # Avança para a próxima linha não-vazia (tags)
        idx = _next_non_empty(lines, idx + 1)
        tags = (
            _LABEL_CLEAN_RE.sub("", lines[idx]).strip().lower()
            if idx < len(lines)
            else ""
        )

        # Restante é conteúdo
        idx = _next_non_empty(lines, idx + 1)
        content = "\n".join(lines[idx:]).strip() if idx < len(lines) else ""

        return {
            "title": title,
            "categories": categories,
            "tags": tags,
            "content": content,
        }


def _next_non_empty(lines: list[str], start: int) -> int:
    """Retorna o índice da próxima linha não-vazia a partir de start."""
    idx = start
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx
