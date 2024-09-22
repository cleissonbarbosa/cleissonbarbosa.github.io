---
title: "Construindo um banco de dados inspirado no SQLite em Rust - Parte 1"
author: cleissonb
date: 2024-09-21 00:00:00 -0300
image:
  path: /assets/img/posts/a1925176-61b6-41d3-9fdb-bee59b994127.png
  alt: "Construindo um banco de dados inspirado no SQLite em Rust - Parte 1"
categories: [Rust]
tags: [rust, database, desenvolvimento, sqlite, ferrousdb]
pin: true
---

## Introdução

Você já se perguntou como funciona um banco de dados relacional por baixo dos panos? Embora muitos desenvolvedores utilizem bancos como SQLite, MySQL ou PostgreSQL diariamente, entender a mecânica interna desses sistemas pode ser um desafio. Mesmo com uma certa experiência em desenvolvimento de software, ainda considero que muitos aspectos desses bancos são uma caixa preta.
Foi com esse espírito de curiosidade que decidi embarcar em um projeto ambicioso: construir um banco de dados similar ao SQLite, mas escrito em Rust, o que estou chamando de __FerrousDB__ (eu sei, a escolha do nome é duvidosa).

> "O que não posso criar, não entendo." – Richard Feynman

## Objetivos do Projeto

Este projeto é, acima de tudo, uma jornada de aprendizado. Quero responder perguntas como:

- Em que formato os dados são armazenados, tanto em memória quanto em disco?
- Como ocorre a transição de dados da memória para o disco?
- Por que há apenas uma chave primária por tabela?
- Como funciona o rollback de uma transação?
- Como os índices são estruturados e funcionam?
- Quando e como ocorre um full table scan?
- Qual estrutura de dados é mais eficiente para armazenar os indices?

## Passos Iniciais

Nesta primeira parte, vamos nos concentrar em:

1. Configuração do Ambiente: Criação do projeto Rust e estrutura básica.
1. Implementação de um REPL (Read-Eval-Print Loop): Uma interface de linha de comando simples para interagir com o banco.
1. Parsing de Comandos SQL e Metacomandos: Diferenciar e interpretar comandos para futura execução.

### 1. Configuração do Ambiente

Criamos um novo projeto Rust utilizando o cargo:

```bash
cargo new ferrous_db --bin
cd ferrous_db
```

Estrutura inicial básica do banco de dados:

```rust
#[derive(Serialize, Deserialize, Clone, PartialEq)]
/// Represents the FerrousDB database.
pub struct FerrousDB {
    pub tables: HashMap<String, Table>,
    pub indexs: HashMap<String, BPTree>,
    is_loaded: bool,
}

impl FerrousDB {
    pub fn create_table(
        &mut self,
        name: &str,
        columns: Vec<ColumnSchema>,
    ) -> Result<(), FerrousDBError> {
        if self.tables.contains_key(name) {
            return Err(FerrousDBError::TableExists(name.to_string()));
        }

        let table = Table {
            name: name.to_string(),
            schema: columns,
            rows: Vec::new(),
        };
        self.tables.insert(name.to_string(), table);
        self.save_to_file("data.ferrous")
            .expect("Falha ao salvar no arquivo");
        Ok(())
    }

    ///...
}
```

- Utilizamos a crate [serde](https://docs.rs/serde/latest/serde/){:target="\_blank"} para serialização e desserialização de dados.
- Utilizamos a estrutura `Table` para representar uma tabela no banco de dados (para ver a implementação completa, consulte o código em [`src/core/table.rs`](https://github.com/cleissonbarbosa/ferrousDB/tree/main/src/core/table.rs){:target="\_blank"})
- Utilizamos a estrutura __BPTree__ para representar um índice B+ (para ver a implementação completa, consulte o código em [`src/core/bptree.rs`](https://github.com/cleissonbarbosa/ferrousDB/tree/main/src/core/bptree.rs){:target="\_blank"}).
    - _Índices são estruturas de dados que melhoram a velocidade das operações de recuperação de dados em uma tabela. O B+ Tree é uma das estruturas mais comuns utilizadas para esse fim, devido à sua eficiência em operações de busca, inserção e remoção._

## 2. Implementação do REPL

Para interagir com o banco de dados, implementamos um REPL simples.

```rust
/// src/bin/repl.rs
use std::io::{self, Write};

use ferrous_db::FerrousDB;

/// Starts a Read-Eval-Print Loop (REPL) for interacting with FerrousDB.
pub fn repl() {
    let mut db = FerrousDB::new();
    loop {
        print!("sql> ");
        io::stdout().flush().unwrap();

        let mut input = String::new();
        io::stdin().read_line(&mut input).unwrap();
        let input = input.trim();

        if input.eq_ignore_ascii_case("exit") {
            break;
        }

        match db.execute_sql(input) {
            Ok(result) => {
                println!("{}", result);
            }
            Err(err) => {
                println!("Error parsing SQL: {:?}", err);
            }
        }
    }
}

fn main() {
    repl();
}

```

## 3. Parsing de Comandos SQL e Metacomandos

Utilizamos a crate [sqlparser](https://docs.rs/sqlparser/latest/sqlparser/){:target="\_blank"} para interpretar os comandos SQL.

```rust
use sqlparser::ast::{Statement, Expr, Offset};
use sqlparser::dialect::GenericDialect;
use sqlparser::parser::Parser;
use crate::core::error_handling::FerrousDBError;
use crate::core::parser::command::SQLCommand;

pub fn parse_sql(sql: &str) -> Result<SQLCommand, FerrousDBError> {
    let dialect = GenericDialect {};
    let ast = Parser::parse_sql(&dialect, sql).map_err(|e| FerrousDBError::ParseError(e.to_string()))?;

    if ast.len() != 1 {
        return Err(FerrousDBError::ParseError("Apenas uma instrução SQL é suportada".to_string()));
    }

    match &ast[0] {
        Statement::CreateTable(create_table) => {
            // veja o código completo no github
        }
        Statement::Insert(insert) => {
            // veja o código completo no github
        }
        Statement::Query(query) => {
            // veja o código completo no github
        }
        _ => Err(FerrousDBError::ParseError(
            "Unsupported SQL command".to_string(),
        )),
    }
}
```

## Estrutura do Projeto

O código está organizado da seguinte forma:

- `src/core/db.rs`: Implementa as operações principais do banco de dados, como criação de tabelas e inserção de dados.
- `src/core/parser/`: Contém os módulos para parsing de comandos.
- `src/core/table.rs`: Define a estrutura da tabela e operações relacionadas.
- `src/core/row.rs`: Representa uma linha no banco de dados.
- `src/core/bptree.rs`: Implementação inicial de uma árvore B+ para índices.

## Referências

- [What would SQLite look like if written in Rust?](https://medium.com/the-polyglot-programmer/what-would-sqlite-look-like-if-written-in-rust-part-1-4a84196c217d){:target="\_blank"} por João Henrique Machado Silva.
- [Building a Database From Scratch in Rust](https://medium.com/@paolorechia/building-a-database-from-scratch-in-rust-part-1-6dfef2223673){:target="\_blank"} por Paolo Rechia.
- [Database of databases](https://dbdb.io/){:target="\_blank"}: Explore diferentes bancos de dados e seus recursos.
- [Introduction to SQLite](https://www.geeksforgeeks.org/introduction-to-sqlite/){:target="\_blank"}: Uma introdução ao SQLite.

Esses artigos fornecem insights valiosos sobre a construção de bancos de dados e são ótimas leituras complementares.

## O Caminho à Frente

Nos próximos artigos, abordaremos:

- Implementação Completa do Parser SQL: Suporte a mais comandos e cláusulas.
- Gerenciamento de Armazenamento: Persistência em disco e serialização de dados.
- Implementação de Índices com Árvore B+: Melhorar a performance nas consultas.
- Transações e Controle de Concorrência: Garantir a integridade dos dados.
- Otimizador de Consultas: Estratégias para otimizar a execução de queries.

## Conclusão

Este projeto é uma excelente oportunidade para mergulhar nos detalhes de como um banco de dados funciona. Utilizando Rust, ganhamos não apenas performance, mas também segurança ao lidar com memória e threads.
Acompanhe os próximos artigos para continuar explorando o desenvolvimento do __FerrousDB__!

---

_Você pode encontrar o código completo no nosso [repositório do GitHub](https://github.com/cleissonbarbosa/ferrousDB){:target="\_blank"}. Pull requests são bem-vindos!_