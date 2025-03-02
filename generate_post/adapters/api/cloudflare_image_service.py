import os
import random
import requests
import base64
import json
import uuid
from typing import Optional
from pathlib import Path

from generate_post.core.domain.interfaces.image_generator_service import (
    ImageGeneratorServiceInterface,
)
from generate_post.config.env_config import EnvConfig
from generate_post.config.constants import ASSETS_DIR
from generate_post.utils.retry_decorator import retry


class CloudflareImageService(ImageGeneratorServiceInterface):
    """Implementação do serviço de geração de imagens usando a API Cloudflare AI"""  # noqa

    def create_image_prompt(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> str:
        """Cria um prompt para a IA gerar uma imagem relacionada ao post"""
        return f"""Create a detailed, visually appealing illustration that represents the following blog post topic:
Title: {title}
Categories: {categories}
Tags: {tags}
Content preview: {content_preview[:500]}...

The image should be a professional, high-quality digital artwork that captures the essence of the programming/technology topic.
Include relevant symbols, code elements, and visual metaphors related to the technical concepts mentioned.
Style: Modern, clean, with a tech aesthetic. Use vibrant colors that complement each other.
Make it visually engaging for a programming blog.
use the reference image as background
"""  # noqa

    def _get_base_image_path(self) -> Path | None:
        """Obtém o caminho para uma imagem base aleatória"""
        base_images_dir = ASSETS_DIR / "base"
        if not base_images_dir.exists():
            os.makedirs(base_images_dir, exist_ok=True)

        # Selecionar uma imagem base aleatória
        base_images = list(base_images_dir.glob("*.png")) + list(
            base_images_dir.glob("*.jpg")
        )
        if not base_images:
            # Para uma implementação mais robusta, seria necessário criar uma imagem padrão aqui  # noqa
            # por simplicidade, vamos retornar uma lista vazia que causará um erro controlado  # noqa
            return None

        return random.choice(base_images)

    @retry(max_attempts=3, delay=3)
    def generate_image(
        self, title: str, categories: str, tags: str, content_preview: str
    ) -> Optional[str]:
        """Gera uma imagem relacionada ao post usando Cloudflare Workers AI"""
        cf_api_token = EnvConfig.get_cf_api_token()
        cf_account_id = EnvConfig.get_cf_account_id()

        if not cf_api_token or not cf_account_id:
            print(
                "Chaves da API Cloudflare não encontradas. Pulando geração de imagem."  # noqa
            )
            return None

        # Obter imagem base
        base_image_path = self._get_base_image_path()
        if not base_image_path:
            print("Nenhuma imagem base encontrada. Pulando geração de imagem.")
            return None

        print(f"Usando imagem base: {base_image_path}")

        # Ler a imagem base
        with open(base_image_path, "rb") as f:
            image_data = f.read()
            image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Criar prompt para a imagem
        prompt = self.create_image_prompt(
            title, categories, tags, content_preview
        )  # noqa
        print(f"Prompt da imagem: {prompt[:100]}...")

        # Preparar o JSON para a chamada da API
        req_json = {
            "prompt": prompt,
            "image_b64": image_b64,
            "negative_prompt": "poor quality, low resolution, bad anatomy, text, watermark, signature",  # noqa
            "num_steps": 20,
            "guidance": 8.5,
            "strength": 0.85,
            "width": 630,
            "height": 1200,
        }

        model = random.choice(["runwayml/stable-diffusion-v1-5-img2img"])
        print(f"Modelo de imagem selecionado: {model}")

        # Chamar a API do Cloudflare Workers AI
        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/@cf/{model}"  # noqa
        headers = {
            "Authorization": f"Bearer {cf_api_token}",
            "Content-Type": "application/json",
        }

        print(f"Fazendo requisição para: {url}")
        response = requests.post(
            url, headers=headers, json=req_json, timeout=120
        )  # noqa

        # Verificar resposta
        if response.status_code != 200:
            error_msg = f"Erro ao gerar imagem. Status code: {response.status_code}, Resposta: {response.text[:500]}"  # noqa
            print(error_msg)
            raise requests.RequestException(error_msg)

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
                raise requests.RequestException(error_msg)

            # Verificar se result existe
            if "result" not in data:
                error_msg = f"Campo 'result' não encontrado na resposta: {data}"  # noqa
                print(error_msg)
                raise requests.RequestException(error_msg)

            image_data = data["result"]

            # Salvar imagem decodificada de base64
            with open(image_path, "wb") as f:
                decoded_image = base64.b64decode(image_data)
                f.write(decoded_image)
                print(f"Imagem JSON decodificada e salva: {image_path}")
                return f"/assets/img/posts/{image_filename}"

        except json.JSONDecodeError:
            # Se não for JSON nem imagem reconhecível, salvar resposta bruta como fallback  # noqa
            print(f"Resposta não é JSON. Salvando como imagem direta.")  # noqa
            with open(image_path, "wb") as f:
                f.write(response.content)
            print(f"Conteúdo da resposta salvo como imagem: {image_path}")
            return f"/assets/img/posts/{image_filename}"
