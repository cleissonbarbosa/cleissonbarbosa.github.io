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
# Nota: gemini-2.5-flash-lite removido pois não activa consistentemente o grounding
_GROUNDED_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

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
- NÃO inclua URLs ou links inline no corpo do texto — as fontes serão adicionadas automaticamente ao final
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
            # camelCase é o formato correto para o JSON da API Gemini (proto JSON encoding)
            "tools": [{"googleSearch": {}}],
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
        chunks = grounding.get("groundingChunks", [])
        supports = grounding.get("groundingSupports", [])

        logger.info(
            "Grounding: %d queries, %d chunks, %d supports",
            len(queries),
            len(chunks),
            len(supports),
        )
        if queries:
            logger.info("Buscas realizadas pelo Gemini: %s", queries)
        if not chunks:
            logger.warning(
                "groundingChunks vazio — o modelo pode não ter realizado buscas. "
                "Verifique se o modelo suporta google_search grounding."
            )

        # IMPORTANTE: injetar citações ANTES de qualquer limpeza, pois os byte
        # offsets do groundingSupports são relativos ao texto original da API.
        text = self._inject_inline_citations(text, grounding)
        # Só depois remover links alucinados (preserva [N](url) que injetamos).
        text = self._remove_hallucinated_links(text)

        sources = self._extract_sources(grounding)
        if sources:
            text = self._append_sources(text, sources)

        return text

    @staticmethod
    def _remove_hallucinated_links(text: str) -> str:
        """Remove links inline alucinados pelo modelo, mantendo apenas o texto de exibição.

        Preserva citações numéricas [N](url) que foram injetadas via groundingSupports.
        """
        # Remove [texto descritivo](url) mas preserva [1](url), [12](url), etc.
        return re.sub(
            r"\[(?!\d+\])([^\]]+)\]\([^)]+\)(?:\{[^}]*\})?",
            r"\1",
            text,
        )

    @staticmethod
    def _inject_inline_citations(
        text: str,
        grounding_metadata: dict,
    ) -> str:
        """Insere citações reais inline usando groundingSupports + groundingChunks.

        A API retorna 'groundingSupports' mapeando segmentos do texto (por byte offset)
        aos índices de 'groundingChunks'. Isso permite inserir [n](url) imediatamente
        após cada trecho fundamentado, com URLs verificados pelo Google.
        """
        chunks = grounding_metadata.get("groundingChunks", [])
        supports = grounding_metadata.get("groundingSupports", [])

        if not chunks or not supports:
            return text

        # Trabalhar com bytes para respeitar os offsets da API (são byte offsets UTF-8)
        text_bytes = text.encode("utf-8")

        # Ordenar por endIndex decrescente para não deslocar índices ao inserir
        sorted_supports = sorted(
            supports,
            key=lambda s: s.get("segment", {}).get("endIndex", 0),
            reverse=True,
        )

        for support in sorted_supports:
            segment = support.get("segment", {})
            end_index = segment.get("endIndex", 0)
            chunk_indices = support.get("groundingChunkIndices", [])

            if not chunk_indices or end_index <= 0:
                continue

            citations = []
            for i in chunk_indices:
                if i < len(chunks):
                    web = chunks[i].get("web", {})
                    uri = web.get("uri", "").strip()
                    if uri:
                        citations.append(f"[{i + 1}]({uri})")

            if not citations:
                continue

            citation_bytes = (" " + " ".join(citations)).encode("utf-8")
            text_bytes = (
                text_bytes[:end_index] + citation_bytes + text_bytes[end_index:]
            )

        return text_bytes.decode("utf-8")

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
