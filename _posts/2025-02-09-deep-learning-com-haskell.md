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

Neste artigo, vamos explorar um projeto de [deep learning](https://www.ibm.com/br-pt/topics/deep-learning){:target="_blank"} utilizando Haskell. O objetivo é demonstrar como podemos implementar e treinar uma [rede neural](https://aws.amazon.com/pt/what-is/neural-network){:target="_blank"} simples para resolver problemas de regressão linear. Utilizaremos a biblioteca [`massiv`](https://hackage.haskell.org/package/massiv){:target="_blank"} para manipulação de arrays e a biblioteca [`hspec`](https://hspec.github.io/){:target="_blank"} para testes.

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

Para começar, precisamos configurar nosso ambiente de desenvolvimento. Certifique-se de ter o [Haskell Stack](https://docs.haskellstack.org/en/stable){:target="_blank"} instalado. Em seguida, crie um novo projeto com o comando:

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

### Testes

Para garantir que nossa implementação está correta, escrevemos testes utilizando a biblioteca `hspec`. No arquivo `test/Spec/MainSpec.hs`, adicionamos os seguintes testes mais importantes:

#### Teste de Inicialização do Modelo

Verifica se o modelo é inicializado corretamente com pesos e bias.

```haskell
describe "Model Initialization" $ do
    it "should initialize model with weights and bias" $ do
        model <- initModel
        size (weights model) `shouldNotBe` Sz1 0
        bias model `shouldSatisfy` (\b -> b >= -1 e <= 1)
```

#### Teste de Forward Pass

Verifica se o forward pass é realizado corretamente com valores simples.

```haskell
describe "Forward Pass" $ do
    it "should perform forward pass correctly with simple values" $ do
        let model = Model (fromLists' Seq [0.5]) 0.1
            input = fromLists' Seq [1.0]
            output = forward model input
        output `shouldBe` 0.6
```

#### Teste de Cálculo de Loss

Verifica se o cálculo de MSE loss é realizado corretamente.

```haskell
describe "Loss Calculation" $ do
    it "should calculate MSE loss correctly" $ do
        let y_pred = fromLists' Seq [2.0, 3.0]
            y_true = fromLists' Seq [1.0, 2.0]
            l = loss y_pred y_true
        l `shouldBe` 1.0
```

#### Teste de Treinamento do Modelo

Verifica se o modelo é treinado corretamente e se a loss é reduzida.

```haskell
describe "Model Training" $ do
    it "should train the model and reduce loss" $ do
        arrList <- replicateM 100 (randomRIO (-10,10))
        let x = fromLists' Seq (Prelude.map (:[]) arrList) :: Array U Ix2 Double
            y = compute @U $ A.map (\v -> 2*v + 1) (compute @U $ flatten x)
        model <- initModel
        trained <- train model x y 1000 0.01
        let y_pred = A.singleton $ forward trained (compute @U $ flatten x)
            final_loss = loss y_pred y
        final_loss `shouldSatisfy` (< 1.0)
```

### Executando o Projeto

Para executar o projeto, utilize o comando:

```bash
stack run
```

Para rodar os testes, utilize o comando:

```bash
stack test
```

## Conclusão

Este projeto demonstra como podemos utilizar Haskell para implementar e treinar uma rede neural simples. A linguagem Haskell, com sua forte tipagem e imutabilidade, oferece uma abordagem interessante e segura para o desenvolvimento de algoritmos de machine learning. Experimente expandir este projeto adicionando novas camadas à rede neural ou implementando diferentes funções de ativação e loss.

## Links

- [Repositório do Projeto](https://github.com/cleissonbarbosa/deep-learning-haskell){:target="_blank"}
- [Documentação do Massiv](https://hackage.haskell.org/package/massiv){:target="_blank"}
- [Documentação do Hspec](https://hspec.github.io/){:target="_blank"}

---

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/deep-learning-haskell){:target="_blank"}. Pull requests são bem-vindas!_