---
title: "Criando um scanner de rede com Haskell"
author: cleissonb
date: 2025-01-19 00:00:00 -0300
image: 
    path: /assets/img/posts/5cc8a2a3-48a6-4525-9b1b-400bfdd18335.png
    alt: "Criando um scanner de rede com Haskell"
categories: [Haskell, Segurança]
tags: [haskell, segurança, auditoria, desenvolvimento, ferramentas, scanner, rede]
pin: false
---

## Introdução

A segurança da informação é uma área crítica que exige ferramentas robustas e precisas para identificar vulnerabilidades e monitorar atividades suspeitas. Haskell, uma linguagem funcional conhecida por sua precisão e capacidade de lidar com grandes volumes de dados, é uma excelente escolha para a criação de ferramentas de auditoria de segurança. Neste artigo, discutiremos a implementação de um scanner de rede em Haskell, destacando suas vantagens e capacidades.

## Por que Haskell?

Haskell oferece várias vantagens para o desenvolvimento de ferramentas:

- **Imutabilidade**: Reduz erros e facilita o raciocínio sobre o código.
- **Concorrência**: Suporte robusto para programação concorrente, essencial para processar grandes volumes de dados.
- **Precisão**: Tipagem forte e inferência de tipos ajudam a evitar erros comuns.
- **Bibliotecas**: Um ecossistema crescente de bibliotecas para manipulação de dados e redes.

## Implementação de um Scanner de Rede simples

Um scanner de rede é uma ferramenta essencial para identificar dispositivos e serviços em uma rede. Vamos implementar um scanner simples em Haskell usando a biblioteca `network`.

### Configuração do Ambiente

Primeiro, crie um novo projeto Haskell:

```bash
stack new network-scanner
cd network-scanner
```

Adicione as dependências no arquivo `package.yaml`:

```yaml
dependencies:
- base >= 4.7 && < 5
- network
- bytestring
```

### Código do Scanner de Rede

No arquivo `src/app/Main.hs`, escreva o seguinte código:

```haskell
{-# LANGUAGE OverloadedStrings #-}

module Main (main) where

import Network.Socket
import qualified Data.ByteString.Char8 as B
import Control.Exception (try, IOException)

-- Função para escanear uma porta específica
scanPort :: HostName -> PortNumber -> IO ()
scanPort host port = do
    addr <- resolve host port
    sock <- openSocket' addr
    result <- tryConnect sock addr
    case result of
        Just _  -> putStrLn $ "Port " ++ show port ++ " is open"
        Nothing -> putStrLn $ "No connection to port " ++ show port
    close sock

-- Resolver o endereço do host
resolve :: HostName -> PortNumber -> IO AddrInfo
resolve host port = do
    let hints = defaultHints { addrSocketType = Stream }
    addr:_ <- getAddrInfo (Just hints) (Just host) (Just $ show port)
    return addr

-- Abrir um socket
openSocket' :: AddrInfo -> IO Socket
openSocket' addr = socket (addrFamily addr) (addrSocketType addr) (addrProtocol addr)

-- Tentar conectar ao socket
tryConnect :: Socket -> AddrInfo -> IO (Maybe ())
tryConnect sock addr = do
    result <- try (connect sock (addrAddress addr)) :: IO (Either IOException ())
    return $ either (const Nothing) Just result

main :: IO ()
main = do
    let host = "127.0.0.1"
    let ports = [80, 443, 8080]
    mapM_ (scanPort host) ports
```

Este código cria um scanner de rede simples que verifica se as portas 80, 443 e 8080 estão abertas no host `127.0.0.1`.

### Executando o Scanner

Para executar o scanner, use o comando:

```bash
stack run
```

## Próximos Passos

Este scanner de rede simples pode ser expandido para incluir mais funcionalidades, como:

1. Scanning Concorrente
    - Para melhorar a performance, podemos usar concorrência com `async`
2. Adicionando Suporte para Intervalos de Portas
    - Podemos escanear um intervalo de portas em vez de portas específicas.
3. Adicionando Detecção de Serviços
    - Podemos identificar serviços que estão rodando nas portas abertas.
4. Logging e Relatórios
    - Adicionar logging e geração de relatórios para os resultados do scanner.

### Recursos Avançados
- Fingerprinting de SO: Análise de TTL e comportamento de pacotes
- Script Engine: Suporte a scripts personalizados para testes
- Exportação de Relatórios: Formatos JSON, CSV, HTML etc.
- Interface Web: Dashboard para visualização de resultados em tempo real
- Integração com Vulnerabilities DB: CVE checking

### Boas Práticas de Segurança
- Implemente rate limiting
- Adicione suporte a proxy
- Inclua verificações de permissões
- Implemente timeouts configuráveis
- Adicione suporte a autenticação

## Conclusão

Haskell é uma linguagem poderosa e eficiente. Sua capacidade de lidar com grandes volumes de dados e garantir precisão torna-a uma excelente escolha para desenvolvedores que buscam criar soluções robustas e confiáveis. Neste artigo, mostramos como implementar um scanner de rede simples em Haskell, destacando suas vantagens e capacidades.

## Links

- [Haskell](https://www.haskell.org/){:target="_blank"}
- [Network Library](https://hackage.haskell.org/package/network){:target="_blank"}
- [Repositório do Scanner de Rede](https://github.com/cleissonbarbosa/network-scanner){:target="_blank"}
