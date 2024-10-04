---
title: "Desenvolvendo Aplicações Web com Rust e WebAssembly: Criando uma SPA do Zero"
author: cleissonb
date: 2024-09-27 00:00:00 -0300
image:
  path: /assets/img/posts/60b4b236-21f8-4e45-92d1-db360b470807.png
  alt: "Desenvolvendo Aplicações Web com Rust e WebAssembly: Criando uma SPA do Zero"
categories: [Rust, Frontend]
tags: [rust, desenvolvimento, frontend, front-end, webassembly, WebAssembly, wasm, trunk]
pin: false
---

## Introdução

O desenvolvimento de aplicações web modernas tem evoluído rapidamente, e a combinação de Rust com WebAssembly (Wasm) oferece uma nova abordagem para construir Single Page Applications (SPA) altamente performáticas e seguras. Neste artigo, exploraremos como desenvolver uma SPA utilizando Rust e compilá-la para WebAssembly, aproveitando o máximo desempenho no navegador.

## Vantagens de usar Rust e Wasm para SPAs

Rust é uma linguagem conhecida por seu desempenho e segurança de memória, enquanto o WebAssembly é um formato binário que permite executar código de alto desempenho em navegadores web. Juntos, eles possibilitam escrever aplicações web rápidas, seguras e eficientes.

- *Desempenho*: Código em Rust compilado para Wasm é executado em velocidade próxima ao código nativo.
- *Segurança*: Rust previne erros comuns de programação, como ponteiros nulos ou vazamentos de memória.
- *Reutilização de Código*: Possibilidade de compartilhar lógica entre frontend e backend se ambos forem escritos em Rust.

## Configurando o Ambiente

Para começar, precisamos configurar nosso ambiente de desenvolvimento.

#### Pré-requisitos

1. Rust instalado. Se ainda não tem, instale via [rustup](https://www.rust-lang.org/tools/install){:target="blank"}.
1. *Trunk*: Uma ferramenta para build e bundling de aplicações Rust para Wasm.
1. *wasm-bindgen*: Ferramenta para gerar bindings entre Rust e JavaScript.

### Instalando o Trunk e o wasm-bindgen-cli

```bash
cargo install trunk
cargo install wasm-bindgen-cli
```

## Criando o Projeto

Usaremos a crate `yew`, um framework Rust para desenvolvimento web em Wasm, semelhante ao React.

#### Passo 1: Criar um novo projeto

```sh
cargo new rust-wasm-spa
cd rust-wasm-spa
```

#### Passo 2: Configurar o `Cargo.toml`

Adicione as dependências no `Cargo.toml`:

```toml
[dependencies]
yew = { version = "0.20", features = ["csr"] }
wasm-bindgen = "0.2.84"
```

#### Passo 3: Escrever o Código

No arquivo `src/main.rs`, vamos escrever um componente básico.

```rust
use yew::prelude::*;

struct App;

impl Component for App {
    type Message = ();
    type Properties = ();

    fn create(_ctx: &Context<Self>) -> Self {
        App
    }

    fn view(&self, _ctx: &Context<Self>) -> Html {
        html! {
            <div>
                <h1>{ "Olá, mundo!" }</h1>
                <p>{ "Bem-vindo à sua primeira SPA em Rust e WebAssembly." }</p>
            </div>
        }
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
```

#### Passo 4: Configurar o Trunk

Crie um arquivo `index.html` na raiz do projeto:

```html
<!DOCTYPE html>
<html>

<head>
    <meta charset="UTF-8" />
    <title>Rust Wasm SPA</title>
</head>

<body>
    <div id="root"></div>
    <!-- O Trunk irá inserir os scripts necessários aqui -->
</body>

</html>
```

#### Passo 5: Executar a Aplicação

Utilize o Trunk para compilar e servir a aplicação:

```sh
trunk serve
```

Agora, acesse `http://127.0.0.1:8080` no seu navegador, e você verá a mensagem "Olá, mundo!".

## Adicionando Interatividade

Vamos adicionar um contador simples para demonstrar interatividade.

Atualize o `src/main.rs`:

```rust
use yew::prelude::*;

struct App {
    counter: i32,
}

enum Msg {
    Increment,
    Decrement,
}

impl Component for App {
    type Message = Msg;
    type Properties = ();

    fn create(_ctx: &Context<Self>) -> Self {
        App { counter: 0 }
    }

    fn update(&mut self, _ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            Msg::Increment => {
                self.counter += 1;
                true
            }
            Msg::Decrement => {
                self.counter -= 1;
                true
            }
        }
    }

    fn view(&self, ctx: &Context<Self>) -> Html {
        let link = ctx.link();
        html! {
            <div style="text-align: center; margin-top: 50px;">
                <h1>{ "Contador" }</h1>
                <p>{ self.counter }</p>
                <button onclick={link.callback(|_| Msg::Increment)}>{ "Incrementar" }</button>
                <button onclick={link.callback(|_| Msg::Decrement)}>{ "Decrementar" }</button>
            </div>
        }
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
```

Agora você tem um contador funcional!

## Consumo de APIs

Para tornar nossa SPA mais dinâmica, podemos consumir uma API. Vamos utilizar a crate `reqwasm` para fazer requisições HTTP.

#### Passo 1: Adicionar Dependência

Atualize o `Cargo.toml`:

```toml
[dependencies]
yew = { version = "0.20", features = ["csr"] }
wasm-bindgen = "0.2.84"
reqwasm = "0.2.0"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
wasm-bindgen-futures = "0.4"
web-sys = { version = "0.3", features = ["Window"] }
```

#### Passo 2: Consumir uma API

Vamos consumir a API pública do JSONPlaceholder para obter uma lista de posts.

Atualize o `src/main.rs`:

```rust
use yew::prelude::*;
use reqwasm::http::Request;
use serde::Deserialize;

struct App {
    posts: Vec<Post>,
    loading: bool,
}

enum Msg {
    FetchPosts,
    ReceiveResponse(Result<Vec<Post>, reqwasm::Error>),
}

#[derive(Deserialize, Debug, Clone, PartialEq)]
struct Post {
    id: u32,
    title: String,
    body: String,
}

impl Component for App {
    type Message = Msg;
    type Properties = ();

    fn create(ctx: &Context<Self>) -> Self {
        ctx.link().send_message(Msg::FetchPosts);
        App {
            posts: vec![],
            loading: true,
        }
    }

    fn update(&mut self, ctx: &Context<Self>, msg: Self::Message) -> bool {
        match msg {
            Msg::FetchPosts => {
                let link = ctx.link().clone();
                wasm_bindgen_futures::spawn_local(async move {
                    let response = Request::get("https://jsonplaceholder.typicode.com/posts")
                        .send()
                        .await
                        .unwrap()
                        .json::<Vec<Post>>()
                        .await;
                    link.send_message(Msg::ReceiveResponse(response));
                });
                false
            }
            Msg::ReceiveResponse(response) => {
                match response {
                    Ok(posts) => {
                        self.posts = posts;
                    }
                    Err(_) => {
                        web_sys::window()
                            .unwrap()
                            .alert_with_message("Erro ao carregar posts")
                            .unwrap();
                    }
                }
                self.loading = false;
                true
            }
        }
    }

    fn view(&self, _ctx: &Context<Self>) -> Html {
        if self.loading {
            html! { <p>{ "Carregando..." }</p> }
        } else {
            html! {
                <div>
                    <h1>{ "Lista de Posts" }</h1>
                    <ul>
                        { for self.posts.iter().map(|post| self.view_post(post)) }
                    </ul>
                </div>
            }
        }
    }
}

impl App {
    fn view_post(&self, post: &Post) -> Html {
        html! {
            <li key={post.id}>
                <h3>{ &post.title }</h3>
                <p>{ &post.body }</p>
            </li>
        }
    }
}

fn main() {
    yew::Renderer::<App>::new().render();
}
```

Agora, quando você executar a aplicação, ela irá exibir uma lista de posts obtidos da API.

## Conclusão

Desenvolver aplicações web utilizando Rust e WebAssembly é uma excelente maneira de construir SPAs rápidas e seguras. Com ferramentas como Yew e Trunk, o processo se torna semelhante ao desenvolvimento com frameworks JavaScript tradicionais, mas com as vantagens oferecidas pelo Rust.

## Próximos Passos

- Estilização: Integrar CSS ou utilizar crates para estilos, como [yew-style](https://github.com/dancespiele/yew_styles){:target="\_blank"}.
- Gerenciamento de Estado: Utilizar crates como [yewdux](https://github.com/intendednull/yewdux){:target="\_blank"} para gerenciamento global de estado.
- Roteamento: Implementar navegação entre páginas com [yew_router](https://yew.rs/docs/concepts/router){:target="\_blank"}.
- Formulários e Validações: Criar formulários interativos e validar entradas do usuário.

## Referências

- [Rust e WebAssembly](https://rustwasm.github.io/){:target="\_blank"} 
- [Yew Framework](https://yew.rs/){:target="\_blank"}
- [Trunk](https://trunkrs.dev/){:target="\_blank"}
- [wasm-bindgen](https://github.com/rustwasm/wasm-bindgen){:target="\_blank"}
- [reqwasm](https://github.com/ranile/reqwasm){:target="\_blank"}

---

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/wasm-spa){:target="\_blank"}. Pull requests são bem-vindos!_
