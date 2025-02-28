---
title: "Desenvolvendo o Jogo Pac-Man com Python e Pygame"
author: cleissonb
date: 2025-02-28 00:00:00 -0300
image:
  path: /assets/img/posts/2c16296f-3883-45dd-9b33-de789c3eed31.png
  alt: "Desenvolvendo um Jogo Pac-Man com Python e Pygame"
categories: [Python, Jogos]
tags: [python, pygame, desenvolvimento, jogos, pacman, tutorial]
pin: false
---

## Introdução

Muita gente acha que precisa de engines complexas ou ser um mestre da programação pra criar jogos, mas vou provar que dá pra fazer algo bem legal com ferramentas simples e acessíveis. Hoje vou mostrar como desenvolvi uma versão do clássico Pac-Man usando Python e Pygame. 

O Pac-Man é um dos jogos mais icônicos de todos os tempos, e "recriá-lo" foi uma ótima maneira de relembrar alguns conceitos de programação de jogos, estruturas de dados e lógica de colisão. Além disso, esse projeto é uma introdução prática aos princípios básicos de desenvolvimento de jogos, como loops de jogo, renderização e controle de estado.

<div align="center">
    <video src="https://github.com/user-attachments/assets/9a2c5738-874a-4b65-a3ba-b39d994d772b" width="560" height="auto" frameborder="0" allowfullscreen></video>
</div>

## Estrutura do Projeto

O projeto está organizado de forma modular para facilitar a manutenção e compreensão:

```
pacman-py/
├── src/
│   ├── game.py         # Lógica principal do jogo
│   ├── ghost.py        # Comportamento dos fantasmas
│   ├── main.py         # Ponto de entrada do jogo
│   ├── maze.py         # Criação do labirinto e dos pontos
│   ├── player.py       # Lógica do Pac-Man
│   └── settings.py     # Configurações do jogo
└── README.md           # Documentação
```

Essa estrutura modular me permitiu isolar diferentes componentes do jogo, deixando o código mais organizado e fácil de entender.

## Configurações Iniciais

No arquivo `settings.py`, defino as constantes básicas que serão usadas em todo o jogo:

```python
# Configurações da tela
WIDTH = 800
UI_BAR_HEIGHT = 50

# Labirinto (matriz 14x14 onde 1 representa paredes e 0 espaços vazios)
LABYRINTH_GRID = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    # ... resto da matriz ...
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

# Cálculo de dimensões baseado no tamanho do labirinto
NUM_ROWS = len(LABYRINTH_GRID)
NUM_COLS = len(LABYRINTH_GRID[0])
CELL_SIZE = WIDTH // NUM_COLS
HEIGHT = CELL_SIZE * NUM_ROWS + UI_BAR_HEIGHT

# Cores
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
PINK = (255, 105, 180)
CYAN = (0, 255, 255)
ORANGE = (255, 165, 0)

# Configurações do jogo
VELOCITY = 5
POWER_PELLET_DURATION = 5000  # em milissegundos
```

## Desenvolvendo o Labirinto

A implementação do labirinto no arquivo `maze.py` foi um dos primeiros desafios. Utilizei uma matriz bidimensional onde `1` representa paredes e `0` representa espaços vazios onde o Pac-Man e os fantasmas podem se mover:

```python
def draw_labyrinth(surface):
    for y, row in enumerate(LABYRINTH_GRID):
        for x, cell in enumerate(row):
            if cell == 1:
                # Desenha paredes
                pygame.draw.rect(
                    surface,
                    BLUE,
                    (
                        x * CELL_SIZE,
                        y * CELL_SIZE + UI_BAR_HEIGHT,
                        CELL_SIZE,
                        CELL_SIZE,
                    ),
                )
```

Para os pontos e power pellets (pílulas de poder), criei funções específicas:

```python
def create_points():
    points = []
    power_pellets = []
    for y, row in enumerate(LABYRINTH_GRID):
        for x, cell in enumerate(row):
            if cell == 0:
                # Cria pontos nos espaços vazios
                point = (
                    x * CELL_SIZE + CELL_SIZE // 2,
                    y * CELL_SIZE + CELL_SIZE // 2 + UI_BAR_HEIGHT,
                )
                points.append(point)
                # Coloca power pellets em posições específicas
                if (x, y) in [(1, 1), (12, 1), (1, 12), (12, 12)]:
                    power_pellets.append(point)
    return points, power_pellets
```

## Implementando o Pac-Man

O jogador (Pac-Man) é implementado na classe `Pacman` no arquivo `player.py`. Algumas características interessantes:

1. **Movimento Fluido**: O movimento é suave e contínuo, não confinado à grade.
2. **Animação da Boca**: O Pac-Man abre e fecha a boca enquanto se move, utilizando funções trigonométricas.
3. **Detecção de Colisão**: Evita que o Pac-Man atravesse paredes.

```python
def draw(self, surface, current_time):
    # Anima a abertura e fechamento da boca
    mouth_open = math.sin(current_time / 200) > 0
    if mouth_open:
        angles = {
            "right": (0.2 * math.pi, 1.8 * math.pi),
            "left": (1.2 * math.pi, 0.8 * math.pi),
            "up": (0.7 * math.pi, 0.3 * math.pi),
            "down": (1.7 * math.pi, 1.3 * math.pi),
        }
        start_angle, end_angle = angles.get(
            self.direction, (0.2 * math.pi, 1.8 * math.pi)
        )
        pygame.draw.arc(
            surface,
            YELLOW,
            (
                self.x - self.radius,
                self.y - self.radius,
                self.radius * 2,
                self.radius * 2,
            ),
            start_angle,
            end_angle,
            20,
        )
    else:
        pygame.draw.circle(surface, YELLOW, (self.x, self.y), self.radius)
```

## Comportamento dos Fantasmas

Uma das partes mais interessantes deste projeto foi a implementação dos fantasmas no arquivo `ghost.py`. Cada fantasma tem um comportamento distinto:

- **Movimentação**: Os fantasmas se movem aleatoriamente pelo labirinto até colidirem com uma parede.
- **Animação**: Implementei animações de flutuação, piscada de olhos e ondulação na base.
- **Estados**: Os fantasmas podem estar normais, assustados (quando o Pac-Man consome uma power pellet), morrendo ou respawnando.

```python
def draw(self, surface):
    if self.is_dying:
        # Animação de morte - gira e encolhe
        # ...código da animação de morte...
    elif self.respawning:
        # Animação de respawn - crescendo do centro
        # ...código da animação de respawn...
    else:
        # Desenho normal do fantasma
        ghost_color = (0, 0, 255) if self.frightened else self.color
        # ...código de renderização do fantasma...
        
        # Animação de piscar olhos
        blink = (pygame.time.get_ticks() % 3000) < 100
        if not blink:
            # Desenha olhos abertos
            # ...código dos olhos abertos...
        else:
            # Desenha olhos fechados
            # ...código dos olhos fechados...
```

## Controlando o Fluxo do Jogo

O arquivo `game.py` é o coração do jogo, gerenciando o loop principal e integrando todos os outros componentes:

1. **Loop de Jogo**: Processamento de eventos, atualização de estados e renderização.
2. **Colisões**: Detecção de colisões entre o Pac-Man e os pontos, power pellets e fantasmas.
3. **Estados do Jogo**: Gerencia os estados como "jogando", "game over" e "vitória".
4. **Interface do Usuário**: Exibe pontuação, vidas e mensagens de fim de jogo.

```python
def update(self):
    if not (self.game_over or self.won):
        keys = pygame.key.get_pressed()
        self.pacman.move(keys, self.collision)

        # Atualiza fantasmas
        for ghost in self.ghosts:
            ghost.update(self.collision)

        # Verifica colisões com pontos
        for point in self.points[:]:
            if math.hypot(self.pacman.x - point[0], self.pacman.y - point[1]) < self.pacman.radius:
                self.points.remove(point)
                self.score += 10

        # Verifica outras colisões e condições...
```

## Desafios e Aprendizados

Durante o desenvolvimento deste jogo, enfrentei alguns desafios interessantes:

1. **Detecção de Colisão**: Implementar colisões precisas em um ambiente de movimento contínuo foi um desafio, especialmente considerando que o labirinto é baseado em uma grade mas o movimento não é.

2. **Animações Fluidas**: Criar animações suaves para o Pac-Man e os fantasmas exigiu o uso de funções matemáticas como seno e cosseno para ciclos de animação.

3. **Gerenciamento de Estado**: Manter o estado do jogo organizado entre múltiplos componentes exigiu um bom design de código.

4. **UI Responsiva**: Implementar uma interface que mostrasse claramente a pontuação, vidas e mensagens sem interferir na jogabilidade.

## Conclusão

Desenvolver este jogo em Python com Pygame foi uma experiência super gratificante. O projeto mostra que é possível criar jogos clássicos com ferramentas simples, sem precisar de engines complexas ou conhecimentos avançados de programação de jogos.

Algumas melhorias que planejo implementar no futuro:

1. **Adicionar mais níveis** com labirintos diferentes e dificuldade crescente.
2. **Melhorar a "IA dos fantasmas"** para que cada um tenha um comportamento único.
3. **Implementar efeitos sonoros** para tornar a experiência mais imersiva.
4. **Adicionar um sistema de high scores** para salvar as melhores pontuações.

## Links

- [Repositório do Projeto](https://github.com/cleissonbarbosa/pacman-py){:target="_blank"}
- [Pygame Documentation](https://www.pygame.org/docs/){:target="_blank"}
- [Tutorial de Pygame](https://realpython.com/pygame-a-primer/){:target="_blank"}
- [História do Pac-Man](https://en.wikipedia.org/wiki/Pac-Man){:target="_blank"}

---

_Você pode encontrar o código completo no [repositório do GitHub](https://github.com/cleissonbarbosa/pacman-py){:target="_blank"}. Pull requests são bem-vindas!_