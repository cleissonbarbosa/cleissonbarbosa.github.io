---
title: "Como Integrar Rust com Python para Desenvolvimento de Aplicações"
author: cleissonb
date: 2024-07-05 00:00:00 -0300
image: 
    path: /assets/img/posts/fdbf30f6-6058-4b20-bc4b-4c1558dacbc8.png
    alt: "Como Integrar Rust com Python para Desenvolvimento de Aplicações"
categories: [Rust, Python]
tags: [rust, python, backend, integracao, desenvolvimento, aplicacoes]
pin: true
---

## Introdução

Integrar Rust com Python pode unir o desempenho do Rust com a simplicidade do Python. Usando ferramentas como [maturin](https://github.com/PyO3/maturin){:target="_blank"} e [pyo3](https://docs.rs/pyo3/latest/pyo3/){:target="_blank"}, é possível criar extensões em Rust que podem ser chamadas diretamente de um código Python. Neste artigo, veremos como fazer essa integração com exemplos práticos.

## Passo 1: Configurar o Ambiente

Primeiro, precisamos instalar o [maturin](https://github.com/PyO3/maturin){:target="_blank"}. Ele facilita a construção e publicação de pacotes Python escritos em Rust.

```bash
pip install maturin
```

### Crie um novo projeto Rust:

```bash
cargo new --lib my_rust_lib
cd my_rust_lib
```

### Adicione as dependências no Cargo.toml:

```toml
[package]
name = "my_rust_lib"
version = "0.1.0"
edition = "2021"

[dependencies]
pyo3 = { version = "0.22.0", features = ["extension-module"] }

[lib]
crate-type = ["cdylib"]

[package.metadata.maturin]
name = "my_rust_lib"
```

## Passo 2: Escrever o Código Rust

No arquivo src/lib.rs, escreva o seguinte código:

```rust
use pyo3::prelude::*;

/// Função que será chamada a partir do Python
#[pyfunction]
#[pyo3(signature = (a, b))]
fn sum_as_string(a: i64, b: i64) -> PyResult<String> {
    Ok((a + b).to_string())
}

/// Módulo Python
#[pymodule]
fn my_rust_lib(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_as_string, m)?)?;
    Ok(())
}
```

## Passo 3: Compilar e Testar

Compile o pacote usando maturin:

```bash
maturin develop
```

Isso irá compilar a biblioteca Rust e instalá-la no ambiente Python atual. Agora, você pode testar a integração criando um script Python:

```python
import my_rust_lib

result = my_rust_lib.sum_as_string(5, 3)
print(result)  # Output: 8
```

> Veja o projeto completo [aqui](https://github.com/cleissonbarbosa/integration-rust-python){:target="_blank"}.

## Entendendo os componentes utilizados

- `pyo3::prelude::*`: Importa os itens necessários para a integração com Python.
- `#[pyfunction]`: Anota a função para que ela possa ser chamada do Python.
- `#[pymodule]`: Define um módulo Python que expõe funções ou estruturas Rust.
- `maturin develop`: Compila e instala a biblioteca Rust como um módulo Python.

## Conclusão

Integrar Rust com Python pode melhorar significativamente o desempenho de aplicações críticas, enquanto mantém a simplicidade e a flexibilidade do Python. Usando maturin e pyo3, esse processo torna-se simples e eficiente. Experimente essa integração no seu próximo projeto para aproveitar o melhor dos dois mundos!

## Links

- [Maturin](https://github.com/PyO3/maturin){:target="_blank"}
- [PyO3](https://docs.rs/pyo3/latest/pyo3/){:target="_blank"}
- [Rust](https://www.rust-lang.org/){:target="_blank"}
- [Python](https://www.python.org/){:target="_blank"}
- [Exemplo utilizado neste artigo](https://github.com/cleissonbarbosa/integration-rust-python){:target="_blank"}