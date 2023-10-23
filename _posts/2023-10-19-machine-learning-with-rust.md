---
title: Machine Learning with Rust (🦀+🤖=😍)
author: cleissonb
date: 2023-10-19 00:00:00 -0300
image: 
    path: /assets/img/posts/d6372536-31b5-4f2a-9de7-e1c4bc3f2069.png
    alt: Machine Learning with Rust
categories: [Rust, Machine Learning]
tags: [rust, ml, machine learning, ai, artificial intelligence]
pin: true
---

## Introduction to Machine Learning with Rust

This article will provide a brief introduction to machine learning with Rust. We will cover the basics of machine learning, and we will show you how to get started with some of the most popular machine learning algorithms in Rust.

---

### What is machine learning?

Machine learning is a field of computer science that gives computers the ability to learn without being explicitly programmed. In other words, machine learning algorithms can learn from data and improve their performance over time without being explicitly told what to do.

### Why rust for machine learning?

Rust is a modern programming language that is well-suited for machine learning. It is fast, safe, and expressive, and it has a growing ecosystem of machine learning libraries.

#### There are three main types of machine learning:

1. **Supervised learning:** Supervised learning algorithms learn from a set of labeled data. This means that the data is already labeled with the correct output, and the algorithm learns to predict the output for new data.
1. **Unsupervised learning:** Unsupervised learning algorithms learn from a set of unlabeled data. This means that the data is not labeled with the correct output, and the algorithm must learn to find patterns in the data.
1. **Reinforcement learning:** Reinforcement learning algorithms learn from trial and error. The algorithm is rewarded for taking actions that lead to desired outcomes, and penalized for taking actions that lead to undesirable outcomes.
Getting started with machine learning in Rust

## Getting started with machine learning in Rust

To get started with machine learning in Rust, create a new project with the following command:

```bash
cargo new my-project
```

and you will need to install the following dependencies:

```bash
cargo add ndarray linfa linfa-linear
```

[**ndarray**](https://docs.rs/ndarray/latest/ndarray/){:target="_blank"} is a library for scientific computing, and [**linfa**](https://docs.rs/linfa/latest/linfa/){:target="_blank"} is a library for machine learning in Rust.

Once you have installed the dependencies, you can start writing machine learning code in Rust. The following code shows a simple example of a linear regression algorithm in Rust:

> **Note:** If you don't know what linear regression is, see [this article](https://en.wikipedia.org/wiki/Linear_regression){:target="_blank"}.


```rust
extern crate linfa;
extern crate ndarray;

use linfa::prelude::*;
use linfa::{traits::Fit, DatasetBase};
use linfa_linear::LinearRegression;
use ndarray::prelude::*;

fn main() {
    // Example data
    let x = arr2(&[[1.0], [2.0], [3.0], [4.0], [5.0]]);
    let y = arr1(&[2.0, 4.0, 5.5, 7.0, 8.5]);

    // Create a DatasetBase from the data
    let dataset = DatasetBase::new(x, y);

    // Create a linear regression model
    let model = LinearRegression::default();

    // Fit the model to the data
    let trained_model = model.fit(&dataset).expect("Error fitting the model");

    // Make predictions using the trained model
    let x_pred = arr2(&[[6.0]]);
    let y_pred = trained_model.predict(&x_pred);

    println!("Forecast: {:.2}", y_pred[0]);
}
```

This code will train a linear regression model on some data and then make a prediction. To run the code, save it as a file called `main.rs` and run the following command:

```bash
cargo run
```
This will print the prediction to the console, which should be `10.20`.

## Conclusion

---

This article has provided a brief introduction to machine learning with Rust. We have covered the basics of machine learning, and we have shown you how to get started with some of the most popular machine learning algorithms in Rust.

If you want to learn more about machine learning with Rust, there are a number of resources available online and in books. We recommend the following resources:

- [The Rust Machine Learning Book](https://www.amazon.com/Practical-Machine-Learning-Rust-Applications/dp/1484251202){:target="_blank"}
- [Machine Learning for Rust Programmers](https://www.freecodecamp.org/news/how-to-build-a-machine-learning-model-in-rust/){:target="_blank"}
- [Linear Regression in Rust](https://medium.com/swlh/machine-learning-in-rust-linear-regression-edef3fb65f93){:target="_blank"}

see the code for this project on [github](https://github.com/cleissonbarbosa/ml-linear-regression){:target="_blank"}

We hope this article has been helpful. Happy coding!