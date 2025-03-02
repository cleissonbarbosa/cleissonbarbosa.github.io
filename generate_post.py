#!/usr/bin/env python3
"""
Script wrapper para manter compatibilidade com o fluxo anterior.
Simplesmente redireciona a execução para o módulo generate_post reestruturado.
"""

import os
import sys

# Adiciona o diretório atual ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa e executa o módulo generate_post
from generate_post.main import main  # noqa

if __name__ == "__main__":
    main()
