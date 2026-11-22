---
title: "Conheça o AEGIS, um Cloud Security Digital Twin"
author: cleissonb
date: 2026-11-22 00:00:00 -0300
description: "Acompanhe uma decisão de acesso na Helios Commerce e volte ao instante em que o roteador começa a filtrar o tráfego de um DDoS."
image:
  path: /assets/img/posts/aegis-visao-geral.png
  alt: "Visão geral da Helios Commerce em quatro camadas, com os três gateways de API agrupados em uma peça e suas conexões destacadas em azul."
categories: [arquitetura, sistemas distribuídos]
pin: true
tags: [rust, webassembly, cedar, simulação, open-source]
audio: /assets/audio/posts/conheca-o-aegis.webm
---

O **AEGIS** é um simulador de infraestrutura em nuvem. Criei o projeto para acompanhar o caminho de uma requisição e entender como uma falha em um serviço afeta os que dependem dele. Se o banco de pedidos demora a responder, por exemplo, posso ver onde as requisições se acumulam. Depois, repito o incidente com mais capacidade no banco e comparo o tempo de recuperação.

A plataforma de exemplo que modelei se chama Helios Commerce. É uma loja fictícia com 51 serviços distribuídos por três regiões e uma borda global. Na tela, ela aparece como uma maquete em 3D. Os pontos que percorrem os fios mostram o tráfego entre os serviços.

## Analisando uma requisição

As quatro placas do mapa separam entrada, identidade, computação e dados. Em cada placa, as peças agrupam serviços do mesmo tipo. Quando abro um dos gateways, vejo de quais serviços ele depende e consulto a latência, a taxa de erros e o volume de requisições daquela instância.

Em **Testar uma autorização**, escolho Alice, analista financeira da Acme, e tento consultar o livro contábil da empresa. A requisição passa pela autenticação, chega ao autorizador e segue até o recurso. Depois escolho Mallory, de outra empresa, e tento exportar o mesmo livro. Dessa vez, o motor de políticas Cedar nega o pedido. O trajeto termina no autorizador e o cartão mostra a regra `forbid-cross-tenant`.

<figure>
  <video class="d-block w-100 rounded-2" controls playsinline preload="none" aria-labelledby="legenda-autorizacao" poster="{{ '/assets/img/posts/aegis-autorizacao-poster.jpg' | relative_url }}">
    <source src="{{ '/assets/video/aegis-autorizacao.mp4' | relative_url }}" type="video/mp4">
    <a href="{{ '/assets/video/aegis-autorizacao.mp4' | relative_url }}">Abrir o vídeo da autorização</a>
  </video>
  <figcaption class="small text-muted mt-2" id="legenda-autorizacao">Siga as duas rotas no mapa. A de Alice chega ao livro contábil. A de Mallory termina no autorizador.</figcaption>
</figure>

## Um DDoS visto da borda

No cenário *DDoS Surge*, o tráfego satura o gateway principal. Abro **Explorar um incidente** e acompanho o fluxo em magenta desde o roteador de borda até os gateways. O painel do incidente lista 17 serviços afetados.

Aos 36 segundos, o roteador de borda começa a barrar parte do tráfego suspeito. O gateway sai do estado crítico e a taxa de erros cai. Pauso a simulação, volto alguns segundos na linha do tempo e sigo o fluxo até o gateway. Quando avanço de novo, vejo a marca de bloqueio uma etapa antes, no roteador.

<figure>
  <video class="d-block w-100 rounded-2" controls playsinline preload="none" aria-labelledby="legenda-incidente" poster="{{ '/assets/img/posts/aegis-incidente-poster.jpg' | relative_url }}">
    <source src="{{ '/assets/video/aegis-incidente.mp4' | relative_url }}" type="video/mp4">
    <a href="{{ '/assets/video/aegis-incidente.mp4' | relative_url }}">Abrir o vídeo do incidente</a>
  </video>
  <figcaption class="small text-muted mt-2" id="legenda-incidente">No painel à esquerda, +0:36 marca o início da filtragem. No mapa, o X vermelho indica onde o tráfego foi barrado. <a href="{{ '/assets/img/posts/aegis-ddos.png' | relative_url }}">Ampliar a captura dos 17 serviços afetados</a>.</figcaption>
</figure>

## O que muda com mais capacidade?

A opção **Comparar uma intervenção** repete o incidente com a mesma topologia e a mesma semente. Na segunda execução, escolho o serviço que vai receber mais capacidade e o momento da mudança. Com as curvas de latência e de erros lado a lado, vejo quais serviços responderam à intervenção e se a plataforma se recuperou mais cedo.

<figure>
  <video class="d-block w-100 rounded-2" controls playsinline preload="none" aria-labelledby="legenda-intervencao" poster="{{ '/assets/img/posts/aegis-intervencao-poster.jpg' | relative_url }}">
    <source src="{{ '/assets/video/aegis-intervencao.mp4' | relative_url }}" type="video/mp4">
    <a href="{{ '/assets/video/aegis-intervencao.mp4' | relative_url }}">Abrir o vídeo da intervenção</a>
  </video>
  <figcaption class="small text-muted mt-2" id="legenda-intervencao">Aos 21 segundos, multiplico por seis a capacidade do banco de pedidos. O pico de latência p95 cai de 655 para 318 ms e a plataforma se recupera 14 segundos antes.</figcaption>
</figure>

O motor que escrevi em Rust é determinístico. Até eu mudar a capacidade, as duas execuções recebem os mesmos comandos e passam pelos mesmos estados. Na demonstração pública, o motor roda no navegador, compilado para WebAssembly.

Escolha o gateway que recebe mais requisições e siga uma das conexões para descobrir qual serviço ele chama.

Para experimentar com a sua própria arquitetura, abra o menu **Mais (...)**. Em **Desenhar uma plataforma nova**, você monta a topologia e conecta os serviços. Se já tiver uma topologia em arquivo, use **Importar ou exportar arquivos** para carregá-la. Um `docker-compose.yml` também serve. Com o mapa pronto, você pode rodar todas as simulações disponíveis para essa topologia e comparar o efeito de uma intervenção nos seus serviços.

[Experimentar o AEGIS](https://cleissonbarbosa.github.io/csdt/) · [Ver o código no GitHub](https://github.com/cleissonbarbosa/csdt)
