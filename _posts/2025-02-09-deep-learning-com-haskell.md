---
title: "Deep Learning com Haskell: Explorando Redes Neurais"
author: cleissonb
date: 2025-01-25 00:00:00 -0300
image:
  path: /assets/img/posts/67a8bf10-7980-8007-8b29-0daba4118d7f.png
  alt: "Deep Learning com Haskell"
categories: [Haskell, Deep Learning]
tags: [haskell, deep learning, machine learning, redes neurais, desenvolvimento]
pin: false
---

## Introdução

Você já se perguntou como seria implementar redes neurais usando uma linguagem funcional? Neste artigo, vou compartilhar minha experiência desenvolvendo um projeto de [deep learning](https://www.ibm.com/br-pt/topics/deep-learning){:target="_blank"} usando Haskell. A ideia surgiu da minha curiosidade em explorar como conceitos de programação funcional podem se aplicar ao desenvolvimento de [redes neurais](https://aws.amazon.com/pt/what-is/neural-network){:target="_blank"}, especialmente para problemas de regressão linear.

O que torna essa abordagem interessante é que Haskell, com sua forte tipagem e pureza funcional, nos força a pensar diferente sobre como estruturar uma rede neural. Vamos usar a biblioteca [`massiv`](https://hackage.haskell.org/package/massiv){:target="_blank"} para manipulação eficiente de arrays e a [`hspec`](https://hspec.github.io/){:target="_blank"} para garantir a qualidade do nosso código através de testes.

## Estrutura do Projeto

O projeto está organizado da seguinte forma:

```
deep-learning-haskell
├── app
│   ├── Main.hs
├── src
│   ├── Lib.hs
├── test
│   ├── Spec
│   │   └── MainSpec.hs
│   └── Spec.hs
├── stack.yaml
└── package.yaml
```

### Configuração do Ambiente

Antes de mergulharmos no código, vamos preparar nosso ambiente de desenvolvimento. Se você ainda não tem o [Haskell Stack](https://docs.haskellstack.org/en/stable){:target="_blank"} instalado, este é o momento. O Stack vai facilitar muito nossa vida gerenciando dependências e builds do projeto.

crie um novo projeto com o comando:

```bash
stack new deep-learning-haskell
cd deep-learning-haskell
```

Adicione as dependências no arquivo `package.yaml`:

```yaml
dependencies:
- base >= 4.7 && < 5
- bytestring
- massiv
- random
- hspec
```

### Implementação da Rede Neural

No arquivo `src/Lib.hs`, implementamos a estrutura da rede neural e as funções de inicialização, [forward pass](https://www.deeplearningbook.com.br/algoritmo-backpropagation-parte-2-treinamento-de-redes-neurais){:target="_blank"}, cálculo de [loss](https://mariofilho.com/guia-completo-da-log-loss-perda-logaritmica-em-machine-learning){:target="_blank"} e treinamento.

#### Estrutura do Modelo de Rede Neural

A estrutura do modelo de rede neural é definida pela data type `Model`, que contém os pesos (`weights`) e o bias (`bias`).

```haskell
data Model = Model 
    { weights :: Array U Ix1 Double
    , bias :: Double 
    } deriving Show
```

#### Função de Inicialização do Modelo

A função `initModel` inicializa o modelo com pesos e bias aleatórios.

```haskell
initModel :: IO Model
initModel = do
    randW <- randomRIO (-1,1)
    let w = fromLists' Seq [randW]
    b <- randomRIO (-1,1)
    return $ Model w b
```

#### Função de Forward Pass

A função `forward` realiza o [forward pass](https://www.deeplearningbook.com.br/algoritmo-backpropagation-parte-2-treinamento-de-redes-neurais){:target="_blank"}, calculando a saída da rede neural para uma entrada `x`.

```haskell
forward :: Model -> Array U Ix1 Double -> Double
forward (Model w b) x = dot w x + b
```

#### Função de Cálculo de Loss

A função `loss` calcula o [erro quadrático médio (MSE)](https://mariofilho.com/rmse-raiz-do-erro-quadratico-medio-em-machine-learning){:target="_blank"} comparando a saída prevista com a saída real.

```haskell
loss :: Array U Ix1 Double -> Array U Ix1 Double -> Double
loss y_pred y_true =
  let diff = compute @U $ A.zipWith (-) y_pred y_true
      squared = compute @U $ A.map (^2) diff
   in sum squared / fromIntegral (unSz $ size squared)
```

#### Função de Treinamento do Modelo

A função `train` atualiza os pesos e bias do modelo usando gradiente descendente.

```haskell
train :: Model -> Array U Ix2 Double -> Array U Ix1 Double -> Int -> Double -> IO Model
train model x y epochs lr = do
    let xFlat = compute @U $ flatten x
    foldM (\m e -> do
        let y_pred = A.singleton $ forward m xFlat
            current_loss = loss y_pred y
            diff = compute @U $ A.zipWith (-) y_pred y
            grad_w = dot (A.singleton $ 2 * sum diff) xFlat
            grad_b = 2 * sum diff
            new_w = fromLists' Seq [index' (weights m) 0 - lr * grad_w]
            new_b = bias m - lr * grad_b
        when (e `mod` 100 == 0) $
            putStrLn $ "Epoch " ++ show e ++ " Loss: " ++ show current_loss
        return $ Model new_w new_b) model [1..epochs]
```

## Executando o Projeto

Para executar o projeto, utilize o comando:

```bash
stack run
```

Para rodar os testes, utilize o comando:

```bash
stack test
```

## Testes: Aprendendo com os Erros

Durante o desenvolvimento, aprendi da maneira mais difícil que testar redes neurais não é trivial. Aqui estão alguns dos testes mais importantes que implementei, depois de vários ciclos de tentativa e erro:

```haskell
describe "Model Training" $ do
    it "should train the model and reduce loss" $ do
        -- Esse teste me salvou várias vezes durante refatorações
        arrList <- replicateM 100 (randomRIO (-10,10))
        let x = fromLists' Seq (Prelude.map (:[]) arrList) :: Array U Ix2 Double
            y = compute @U $ A.map (\v -> 2*v + 1) (compute @U $ flatten x)
        model <- initModel
        trained <- train model x y 1000 0.01
        let y_pred = A.singleton $ forward trained (compute @U $ flatten x)
            final_loss = loss y_pred y
        final_loss `shouldSatisfy` (< 1.0)
```

Uma dica que aprendi na prática: sempre teste com diferentes conjuntos de dados. No início, eu testava apenas com um conjunto fixo e perdi horas debugando problemas que só apareciam com dados diferentes.

## Próximos Passos

Depois de implementar essa versão inicial, já tenho algumas ideias para expandir o projeto:

- Implementar diferentes funções de ativação (ReLU foi minha primeira escolha, mas quero experimentar outras)
- Adicionar suporte a redes neurais convolucionais
- Otimizar o treinamento com processamento paralelo

## Conclusão

Este projeto demonstra como podemos utilizar Haskell para implementar e treinar uma rede neural simples. A linguagem Haskell, com sua forte tipagem e imutabilidade, oferece uma abordagem interessante e segura para o desenvolvimento de algoritmos de machine learning. Experimente expandir este projeto adicionando novas camadas à rede neural ou implementando diferentes funções de ativação e loss.

## Links

- [Repositório do Projeto](https://github.com/cleissonbarbosa/deep-learning-haskell){:target="_blank"}
- [Documentação do Massiv](https://hackage.haskell.org/package/massiv){:target="_blank"}
- [Documentação do Hspec](https://hspec.github.io/){:target="_blank"}

---

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/deep-learning-haskell){:target="_blank"}. Pull requests são bem-vindas!_