import logging
import requests
from pathlib import PurePosixPath
from typing import Dict, Optional
from urllib.parse import quote

from generate_post.core.domain.interfaces.content_generator_service import (
    ContentGeneratorServiceInterface,
)
from generate_post.adapters.api import gemini_client
from generate_post.config.env_config import EnvConfig
from generate_post.utils.content_parser import parse_generated_content
from generate_post.utils.model_fallback import first_successful

logger = logging.getLogger(__name__)

# Ordem de preferência; os seguintes só entram se o anterior falhar.
# gemini-2.5-* ficou restrito a quem já usava: fica por último como reserva.
_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
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
            # Extract the stem (no dir, no .md) then strip YYYY-MM-DD- date prefix
            name = PurePosixPath(filename).stem
            slug = name[11:] if len(name) > 11 else name
            slug_url = quote(slug, safe="-")
            base_prompt += f"""
## CONTEXTO: ÚLTIMO POST PUBLICADO
Título: {last_post.get('title', name)}
URL: https://cleissonbarbosa.github.io/posts/{slug_url}/

Resumo do conteúdo anterior:
{last_post.get('content', '')[:1000]}

## INSTRUÇÕES ADICIONAIS
- Escolha um tópico DIFERENTE do post anterior
- Pode fazer referência sutil ao post anterior como conexão natural entre os conteúdos
- Varie a abordagem: se o anterior foi tutorial, faça uma análise; se foi teórico, seja mais prático
"""

        return base_prompt

    def generate_content(self, prompt: str) -> str:
        """Gera conteúdo a partir de um prompt usando a API Gemini"""
        self._env.validate_gemini()
        return first_successful(
            _MODELS, lambda model: self._generate_with_model(model, prompt)
        )

    def _generate_with_model(self, model_name: str, prompt: str) -> str:
        req_json = {
            "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                }
            ],
            # Gemini 3 recomenda manter temperature no padrão (1.0): valores
            # menores causam loops. O limite cobre também os tokens de thinking.
            "generationConfig": {"maxOutputTokens": 32768},
        }

        candidate = gemini_client.generate_content(
            self._session,
            self._env.gemini_api_key,
            model_name,
            req_json,
            timeout=180,
        )
        return "".join(text for _, text in gemini_client.text_parts(candidate))

    def parse_generated_content(self, generated_text: str) -> Dict:
        """Extrai título, categorias, tags e conteúdo do texto gerado"""
        return parse_generated_content(
            generated_text, default_categories="programação", default_tags="programação"
        )
