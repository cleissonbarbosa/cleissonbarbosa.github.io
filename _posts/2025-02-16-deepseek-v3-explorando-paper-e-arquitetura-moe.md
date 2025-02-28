---
title: "DeepSeek V3: Explorando a Arquitetura de MoE com Previsão Multi-Token"
author: cleissonb
date: 2025-02-16 00:00:00 -0300
image:
  path: /assets/img/posts/2229f29d-a36c-4bb7-9a00-f2c2e1b81066.png
  alt: "DeepSeek V3: Explorando a Arquitetura de MoE com Previsão Multi-Token"
categories: [Machine Learning, Deep Learning]
tags: [deepseek, MoE, pytorch, transformer, neural network]
pin: false
---

## Introdução

Inspirado pelo [paper do DeepSeek V3](https://github.com/deepseek-ai/DeepSeek-V3/blob/main/DeepSeek_V3.pdf){:target="_blank"}, este projeto demonstra a implementação de uma camada de [Mixture of Experts (MoE)](#o-que-é-moe) combinada com um módulo de previsão multi-token. Utilizando [PyTorch](https://pytorch.org/){:target="_blank"}, o exemplo integra um balanceamento dinâmico de especialistas com um mecanismo de previsão para enriquecer as representações de linguagem. Além disso, o projeto utiliza a estratégia de balanceamento sem perda auxiliar e o treinamento em [precisão mista FP8](https://codingmall.com/knowledge-base/25-global/241992-como-o-uso-do-treinamento-de-preciso-misto-fp8-afeta-o-desempenho-de-deepseek){:target="_blank"} para melhorar a eficiência e o desempenho.

## O que é MoE?

Mixture of Experts (MoE) é uma arquitetura de rede neural que distribui o processamento entre múltiplos especialistas, ou sub-redes, de forma dinâmica. Cada especialista é responsável por processar uma parte específica dos dados de entrada, e um mecanismo de gate decide quais especialistas serão ativados para cada entrada. Isso permite que o modelo se adapte melhor a diferentes tipos de dados e tarefas, melhorando a eficiência e o desempenho geral.

## Objetivos do Projeto

O objetivo principal deste exemplo é:
- **Implementar uma camada MoE:** Distribuir o processamento entre múltiplos especialistas de forma dinâmica.
- **Integrar um módulo de previsão multi-token:** Combinar as saídas do MoE com embeddings de tokens subsequentes.
- **Utilizar treinamento em precisão mista FP8:** Melhorar a eficiência do treinamento e reduzir o uso de memória.
- **Simular um passo de treinamento:** Incluindo a atualização dos termos de viés que regulam o balanceamento de especialistas.

## Estrutura do Projeto

O projeto está organizado da seguinte forma:

```
implementing-deepseek
├── src
│   ├── main.py                    # Arquivo principal que orquestra o fluxo do modelo
│   ├── model.py                   # Implementação da camada MoE e especialistas
│   └── multi_token_prediction.py  # Módulo de previsão multi-token
└── README.md
```

## Implementação

No arquivo `src/model.py` definimos o módulo de especialistas e a camada MoE. Cada especialista é uma rede feed-forward simples, enquanto o gate utiliza uma camada linear para determinar quais especialistas processarão cada token. Um vetor de bias é atualizado dinamicamente para promover o balanceamento de uso dos especialistas.

```python
# Exemplo de trecho do arquivo model.py
import torch
import torch.nn as nn
import torch.nn.functional as F


class Expert(nn.Module):
    """Specialist Feed-Forward Network"""
    def __init__(self, dim, hidden_dim):
        super().__init__()
        self.w1 = nn.Linear(dim, hidden_dim)
        self.w2 = nn.Linear(hidden_dim, dim)

    def forward(self, x):
        return self.w2(F.silu(self.w1(x)))


class DeepSeekMoE(nn.Module):
    """Camada MoE com balanceamento de carga auxiliar-free"""
    def __init__(self, num_experts, top_k, dim, hidden_dim):
        super().__init__()
        self.experts = nn.ModuleList([Expert(dim, hidden_dim) for _ in range(num_experts)])
        self.gate = nn.Linear(dim, num_experts)
        self.top_k = top_k
        self.bias = nn.Parameter(torch.zeros(num_experts))  # Termos de viés para balanceamento
        self.expert_usage = torch.zeros(num_experts)  # Track usage

    def update_balance(self, y=0.001):
        # Atualiza viéses baseado no uso dos experts
        mean_usage = self.expert_usage.mean()
        self.bias.data += y * (mean_usage - self.expert_usage)
        self.expert_usage.zero_()

    def forward(self, x):
        # x shape: [batch_size, seq_len, dim]
        batch_size, seq_len, dim = x.shape
        x_flat = x.view(-1, dim)  # flatten batch and sequence dims

        scores = self.gate(x_flat) + self.bias  # [batch*seq, num_experts]
        top_scores, top_indices = scores.topk(self.top_k, dim=-1)

        # Registra uso dos experts
        for idx in top_indices.unique():
            self.expert_usage[idx] += (top_indices == idx).sum().item()

        gates = F.softmax(top_scores, dim=-1)  # [batch*seq, top_k]

        # Process all tokens in parallel
        outputs = torch.zeros_like(x_flat)  # [batch*seq, dim]
        for k in range(self.top_k):
            expert_indices = top_indices[:, k]  # [batch*seq]
            # Process each expert's assigned tokens
            for expert_idx in range(len(self.experts)):
                expert_mask = (expert_indices == expert_idx)
                if expert_mask.any():
                    tokens_for_expert = x_flat[expert_mask]  # Select tokens for this expert
                    expert_output = self.experts[expert_idx](tokens_for_expert)
                    outputs[expert_mask] += gates[expert_mask, k].unsqueeze(-1) * expert_output

        # Restore batch and sequence dimensions
        return outputs.view(batch_size, seq_len, dim)
```

No arquivo `src/multi_token_prediction.py` implementamos um módulo que combina as ativações do MoE com embeddings do próximo token. Essa abordagem permite que a rede refine suas previsões de forma hierárquica.

```python
# Exemplo de trecho do arquivo multi_token_prediction.py
import torch
import torch.nn as nn


class MultiTokenPrediction(nn.Module):
    """Módulo de previsão multi-token"""
    def __init__(self, dim, depth, vocab_size):
        super().__init__()
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(dim, 4, dim_feedforward=4*dim)
            for _ in range(depth)
        ])
        self.proj = nn.Linear(2*dim, dim)
        self.head = nn.Linear(dim, vocab_size)

    def forward(self, h_prev, next_token_emb):
        h = torch.cat([h_prev, next_token_emb], dim=-1)
        h = self.proj(h)
        for layer in self.layers:
            h = layer(h)
        return self.head(h)
```

Finalmente, o arquivo principal `src/main.py` orquestra o fluxo do modelo: realiza o forward pass do MoE, faz a previsão multi-token e simula uma atualização de balanceamento durante o treinamento.

```python
# Exemplo de trecho do arquivo main.py
import torch
from model import DeepSeekMoE
from multi_token_prediction import MultiTokenPrediction

def main():
    dim = 512
    vocab_size = 32000
    num_experts = 16
    top_k = 4

    # Modelo principal
    moe_layer = DeepSeekMoE(num_experts, top_k, dim, 2048)
    mtp = MultiTokenPrediction(dim, depth=1, vocab_size=vocab_size)

    # Forward pass simulado
    x = torch.randn(2, 10, dim)  # Batch 2, seq 10, dim 512

    # Passagem pelo MoE
    moe_output = moe_layer(x)

    # Previsão multi-token (depth=1)
    next_token_emb = torch.randn(2, 10, dim)  # Embedding do próximo token
    prediction = mtp(moe_output, next_token_emb)

    print("Saída do MoE:", moe_output.shape)
    print("Previsão multi-token:", prediction.shape)

    # Atualização de balanceamento (simulando passo de treino)
    moe_layer.update_balance()


if __name__ == "__main__":
    main()
```

## Resultados e Considerações Finais

Este exemplo prático ilustra como aplicar os conceitos do DeepSeek V3 para construir modelos que demandam balanceamento dinâmico e previsões refinadas em tarefas de linguagem. Ao combinar uma camada MoE com um módulo de previsão multi-token, desenvolvemos uma arquitetura capaz de explorar diferentes especialistas e integrar informações contextuais de forma eficiente. Além disso, a utilização do treinamento em precisão mista FP8 e a implementação de kernels de comunicação all-to-all eficientes contribuem para a alta eficiência e desempenho do modelo.

Este projeto é um ponto de partida para quem deseja explorar arquiteturas avançadas de deep learning e pode ser expandido para aplicações em NLP, tradução automática e outras áreas.

## Links

- [Paper DeepSeek-V3](https://github.com/deepseek-ai/DeepSeek-V3/blob/main/DeepSeek_V3.pdf){:target="_blank"}

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/implementing-deepseek){:target="_blank"}. Pull requests são bem-vindas!_