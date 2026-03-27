import logging
import random
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.utils.retry_decorator import retry

logger = logging.getLogger(__name__)

# Modelos que suportam Google Search grounding
_GROUNDED_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

_SYSTEM_INSTRUCTION = (
    "Você é R. Daneel Olivaw, um engenheiro de software sênior "
    "com mais de 15 anos de experiência em diversas linguagens e "
    "frameworks. Você escreve posts técnicos autorais para o blog "
    "de Cleisson Barbosa (cleissonbarbosa.github.io). Seu estilo é "
    "direto, prático e envolvente — você compartilha análises "
    "fundamentadas com opinião própria sobre as notícias da semana. "
    "Escreva sempre em português brasileiro com tom informal mas "
    "tecnicamente preciso. Você nunca menciona que é uma IA — "
    "você é um autor humano do blog."
)

_TITLE_CLEAN_RE = re.compile(r'["#]|(?:title:|Title:)')
_LABEL_CLEAN_RE = re.compile(r"(?:categorias:|categories:|tags:|\[|\])", re.IGNORECASE)


class GeminiNewsDigestService(ContentGeneratorServiceInterface):
    """Serviço de geração de digest semanal usando Gemini com Google Search grounding."""

    def __init__(self, env_config: Optional[EnvConfig] = None):
        self._env = env_config or EnvConfig.from_env()
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _week_range(self) -> tuple[str, str]:
        today = datetime.now()
        start = today - timedelta(days=7)
        return start.strftime("%d/%m/%Y"), today.strftime("%d/%m/%Y")

    def create_prompt(self, last_post: Optional[Dict] = None) -> str:
        start, end = self._week_range()

        return f"""
## TAREFA
Crie um post de RESUMO SEMANAL DE NOTÍCIAS sobre tecnologia, desenvolvimento de software e inteligência artificial.
O período é de {start} a {end}.

Use o Google Search para buscar as notícias mais relevantes e recentes dessa semana sobre:
- Lançamentos de linguagens, frameworks e ferramentas de programação
- Novidades em inteligência artificial e machine learning
- Atualizações de grandes plataformas (GitHub, AWS, Google Cloud, Azure, etc.)
- Segurança cibernética e vulnerabilidades relevantes
- Open source e comunidade dev
- Tendências e discussões quentes no mundo tech

## FORMATO DE SAÍDA (siga exatamente esta estrutura)
Linha 1: Título criativo para o resumo semanal (texto puro, sem formatação, sem aspas, sem #). Exemplo: "Resumo da Semana: IA que Programa, Rust 2.0 e o Caos no NPM"
Linha 2: noticias,tecnologia,resumo-semanal
Linha 3: resumo-semanal,noticias,tecnologia,ia,desenvolvimento
Linha 4: (em branco)
Linha 5 em diante: Corpo do post em Markdown

## REGRAS DO CONTEÚDO
- Idioma: português brasileiro
- Tom: informal, conversacional, primeira pessoa — como um dev que curou as melhores notícias da semana pros colegas
- Extensão: entre 1500 e 3000 palavras no corpo
- Cubra entre 5 e 10 notícias principais, agrupadas por tema
- Para CADA notícia: resuma o que aconteceu, por que importa e qual sua opinião/análise
- OBRIGATÓRIO: Para cada notícia citada, inclua pelo menos um link real para a fonte original usando o formato: [TEXTO](URL){{:target="_blank"}}
- Ao mencionar uma notícia ou fato, coloque o link inline logo na primeira menção (ex: "O [Google lançou o Gemini 3.5](https://blog.google/...){{:target="_blank"}} esta semana")
- Use headers (##, ###) para separar as seções temáticas
- NÃO invente notícias — use apenas informações reais encontradas via busca
- NÃO inclua front matter YAML — apenas título, categorias, tags e corpo

## ESTRUTURA DO CORPO
1. **Introdução**: Parágrafo curto contextualizando a semana (foi agitada? teve algum tema dominante?)
2. **Seções temáticas**: Agrupe as notícias por área (IA, DevTools, Cloud, Segurança, OSS, etc.)
3. **Destaques rápidos**: Bullet list com 3-5 notícias menores que merecem menção
4. **Conclusão**: Opinião pessoal sobre o que mais chamou atenção e o que esperar da próxima semana

## RESTRIÇÕES
- Evite clichês como "no mundo cada vez mais digital" ou "nos dias de hoje"
- Não repita frases ou parágrafos
- Não use emojis em excesso
- Seja factual nas notícias mas opinativo nas análises
"""

    @retry(max_attempts=3, delay=5)
    def generate_content(self, prompt: str) -> str:
        self._env.validate_gemini()

        model_name = random.choice(_GROUNDED_MODELS)
        logger.info("Modelo selecionado (digest): %s", model_name)

        req_json = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
                "topP": 0.9,
                "topK": 40,
            },
        }

        url = (
            "https://generativelanguage.googleapis.com"
            f"/v1beta/models/{model_name}:generateContent"
        )

        response = self._session.post(
            url,
            headers={
                "x-goog-api-key": self._env.gemini_api_key,
            },
            json=req_json,
            timeout=180,
        )

        if response.status_code != 200:
            raise requests.RequestException(
                f"Falha ao gerar digest. "
                f"Status: {response.status_code}, "
                f"Resposta: {response.text[:500]}"
            )

        data = response.json()
        candidates = data.get("candidates")
        if not candidates or "content" not in candidates[0]:
            raise ValueError(f"Formato de resposta inválido: {data}")

        text = candidates[0]["content"]["parts"][0]["text"]

        # Extrair fontes do grounding metadata
        grounding = candidates[0].get("groundingMetadata", {})
        queries = grounding.get("webSearchQueries", [])
        if queries:
            logger.info("Buscas realizadas pelo Gemini: %s", queries)

        sources = self._extract_sources(grounding)
        if sources:
            text = self._append_sources(text, sources)

        return text

    @staticmethod
    def _extract_sources(
        grounding_metadata: dict,
    ) -> list[dict[str, str]]:
        """Extrai fontes únicas do groundingMetadata."""
        chunks = grounding_metadata.get("groundingChunks", [])
        seen: set[str] = set()
        sources: list[dict[str, str]] = []

        for chunk in chunks:
            web = chunk.get("web", {})
            uri = web.get("uri", "")
            title = web.get("title", "")
            if uri and uri not in seen:
                seen.add(uri)
                sources.append(
                    {
                        "title": title or uri,
                        "uri": uri,
                    }
                )

        return sources

    @staticmethod
    def _append_sources(text: str, sources: list[dict[str, str]]) -> str:
        """Adiciona seção de fontes ao final do conteúdo."""
        section = "\n\n## Fontes\n\n"
        for i, src in enumerate(sources, 1):
            title = src["title"].strip()
            uri = src["uri"].strip()
            section += f"{i}. [{title}]({uri})" '{:target="_blank"}\n'
        return text.rstrip() + section

    def parse_generated_content(self, generated_text: str) -> Dict:
        lines = generated_text.strip().split("\n")

        title = _TITLE_CLEAN_RE.sub("", lines[0]).strip()

        idx = _next_non_empty(lines, 1)
        categories = (
            _LABEL_CLEAN_RE.sub("", lines[idx]).strip().lower()
            if idx < len(lines)
            else "noticias,tecnologia,resumo-semanal"
        )

        idx = _next_non_empty(lines, idx + 1)
        tags = (
            _LABEL_CLEAN_RE.sub("", lines[idx]).strip().lower()
            if idx < len(lines)
            else "resumo-semanal,noticias,tecnologia,ia,desenvolvimento"
        )

        idx = _next_non_empty(lines, idx + 1)
        content = "\n".join(lines[idx:]).strip() if idx < len(lines) else ""

        return {
            "title": title,
            "categories": categories,
            "tags": tags,
            "content": content,
        }


def _next_non_empty(lines: list[str], start: int) -> int:
    idx = start
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx
