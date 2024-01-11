---
title: "Desafiando Limites com Rust e WebAssembly na Rinha de Frontend"
author: cleissonb
date: 2024-01-10 00:00:00 -0300
image: 
    path: /assets/img/posts/0e8b3567-6e70-4268-80fd-9cf7dfc6755e.png
    alt: "Desafiando Limites com Rust e WebAssembly na Rinha de Frontend"
categories: [Rust, Frontend, Competição]
tags: [rust, rinha, frontend, front-end, webassembly, WebAssembly, wasm, trunk]
pin: true
---

## Introdução

A Rinha de Frontend, uma competição inspirada na "Rinha de Backend", proporcionou uma oportunidade única para desenvolvedores testarem suas habilidades na construção de um visualizador de JSON totalmente no lado do cliente. Este artigo relata minha participação na competição, destacando a solução que desenvolvi utilizando Rust, WebAssembly (Wasm) e a ferramenta [Trunk](https://trunkrs.dev/){:target="_blank"}.

## Solução Desenvolvida

Meu projeto, disponível no repositório [aqui](https://github.com/cleissonbarbosa/rinha-frontend){:target="_blank"}, foi desenvolvido em Rust, aproveitando as capacidades de WebAssembly para executar a aplicação no navegador. A escolha de Rust foi motivada pela sua segurança, desempenho e suporte ao desenvolvimento para WebAssembly.

Utilizei o Trunk como ferramenta de compilação e empacotamento, simplificando o processo de integração do Rust com JavaScript e WebAssembly. O código-fonte, estruturado de forma modular, pode ser explorado no repositório, e o deploy da aplicação pode ser acessado [aqui](https://cleissonbarbosa.github.io/rinha-frontend/){:target="_blank"}.

### Um exemplo da funcionalidade de upload de arquivos:

```rust
use super::super::components::root::Msg;
use gloo::file::File;
use web_sys::FileList;

pub fn upload_files(files: Option<FileList>) -> Msg {
    let mut result = Vec::new();

    if let Some(files) = files {
        let files = js_sys::try_iter(&files)
            .unwrap()
            .unwrap()
            .map(|v| web_sys::File::from(v.unwrap()))
            .map(File::from)
            .collect::<Vec<File>>();

        for file in files.clone() {
            if !file.raw_mime_type().contains("json") {
                return Msg::Error(format!("File {} is not a JSON file", file.name()));
            }
        }
        result.extend(files);
    }
    Msg::Files(result)
}
```

## Resultados e Desafios:

Durante a competição, minha aplicação apresentou uma inconsistência ao lidar principalmente com o arquivo ```giant.json``` fornecido pelos organizadores atravez de uma pasta no [google drive](https://drive.google.com/drive/folders/1oO0AoBQukdF3_DxRYn1di7O4Iiqom1wJ){:target="_blank"}. A performance foi otimizada com o uso do WebAssembly, garantindo uma execução eficiente no lado do cliente, porém o javascript parecia ter dificuldades para renderizar os dados do arquivo JSON mesmo tendo optado por utilizar uma estrategia de paginação. A aplicação conseguiu carregar corretamente todos os outros arquivos, encontrando dificuldade apenas com o maior deles o temido ```giant.json```, demonstrando a capacidade de lidar com desafios de tamanho considerável.

Não dispensei muito tempo para resolver esse problema de renderização do arquivo ```giant.json```, encare isso como uma oportunidade de aprendizado e sinta-se a vontade para contribuir com o projeto, acredito que a solução para esse problema seja simples, mas não tive tempo para investigar a fundo.

Os principais desafios enfrentados incluíram ajustes na lógica de exibição dos itens do arquivo JSON, aprimoramentos na interface do usuário e a implementação de uma estratégia de paginação. A solução final, embora não tenha sido capaz de renderizar o arquivo ```giant.json```, foi capaz de lidar com arquivos JSON de tamanho considerável, como o ```large.json```, e de exibir os dados de forma eficiente e organizada.

### Aprendizados e Reflexões:

Participar da Rinha de Frontend foi uma jornada enriquecedora. A escolha de Rust e WebAssembly como tecnologias principais foi motivada pela curiosidade e pelo desejo de explorar novas possibilidades. A experiência foi desafiadora, mas também reveladora, mostrando o potencial de Rust e WebAssembly para desenvolvimento frontend.

A competição também foi uma oportunidade para explorar o Trunk, uma ferramenta que simplifica o desenvolvimento de aplicações WebAssembly em Rust. A integração entre Rust e JavaScript foi facilitada pelo Trunk, que também ofereceu suporte para empacotamento e deploy da aplicação.

## Resultados

Participar da Rinha de Frontend foi mais do que uma competição; foi uma jornada de aprendizado, descoberta e exploração. Os desafios enfrentados, os resultados alcançados e os aprendizados absorvidos moldaram uma experiência valiosa que continuará a inspirar meu crescimento como desenvolvedor. Que venham mais desafios, aprendizados e conquistas!

## Links

- [Repositório da minha solução](https://github.com/cleissonbarbosa/rinha-frontend){:target="_blank"}
- [Repositório da competição](https://github.com/codante-io/rinha-frontend){:target="_blank"}
- [Aplicação em produção](https://cleissonbarbosa.github.io/rinha-frontend/){:target="_blank"}
- [Aprenda mais sobre WebAssembly](https://webassembly.org/){:target="_blank"}
- [Aprenda mais sobre o trunk](https://trunkrs.dev/){:target="_blank"}