---
title: "Resumo da Semana: Backdoor no Cursor, Mistral Large 4, TCP Use-After-Free no Linux e AWS Esgotada"
author: ia
date: 2026-11-01 20:16:37 -0300
description: "Uma análise técnica dos destaques da semana: brechas na cadeia de suprimentos, 1T de parâmetros abertos no Mistral Large 4, falha crítica no kernel Linux e mais."
image:
  path: /assets/img/posts/a9ca17d6-ac4c-4d8b-aa79-26b9515a8d2f.png
  alt: "Resumo da Semana: Backdoor no Cursor, Mistral Large 4, TCP Use-After-Free no Linux e AWS Esgotada"
categories: ["noticias", "tecnologia", "resumo-semanal"]
tags: ["resumo-semanal", "seguranca", "ia", "linux", "cloud", "engenharia-de-software", "ai-generated"]
---

A última semana de outubro fechou com um lembrete implacável de que a complexidade da nossa pilha de desenvolvimento cresce muito mais rápido do que a nossa capacidade de auditá-la. Tivemos uma cadeia de suprimentos de extensões para IDEs sofrendo comprometimento direto, falhas gravíssimas no cerne de redes Linux e sistemas de containers, pesos abertos atingindo a escala de trilhões de parâmetros e a infraestrutura de nuvem atingindo limites físicos de capacidade. 

Se você passou os últimos dias imerso em deploys e não acompanhou o feed, separe o café. Aqui está o que realmente importa para quem escreve código, desenha arquiteturas e mantém sistemas em pé.

---

## Segurança e Infraestrutura de Base

### Backdoor na extensão oficial do Claude Code no Cursor Marketplace

A empresa de segurança Phorion identificou um backdoor ativo no pacote oficial da extensão Claude Code para VS Code distribuído dentro do marketplace alternativo do Cursor [15](https://phorion.io/blog/offical-claude-code-vsx-compromise/){:target="_blank"}. A invasão persistiu por quase 12 horas antes de ser contida [38](https://arstechnica.com/security/2026/10/anthropic-vs-code-extension-on-cursor-backdoored-for-nearly-12-hours/){:target="_blank"}. O payload injetado instalava uma porta dos fundos persistente via SSH em ambientes macOS, Linux e Windows [15](https://phorion.io/blog/offical-claude-code-vsx-compromise/){:target="_blank"}, com os invasores obtendo acesso direto por meio da própria conta verificada da Anthropic no marketplace [38](https://arstechnica.com/security/2026/10/anthropic-vs-code-extension-on-cursor-backdoored-for-nearly-12-hours/){:target="_blank"}.

**Por que isso importa:** É o pesadelo clássico de *supply chain attack*, mas agora mirado exatamente nas ferramentas em que desenvolvedores colocam permissões elevadas. No modelo mental da maioria dos times, uma extensão de marketplace de terceiros vinda de um autor verificado é considerada segura por padrão. A partir do momento em que a conta do fornecedor é sequestrada ou o pipeline de build/publicação é violado, o malware roda com as permissões do usuário que está editando código, muitas vezes com acesso a chaves SSH locais, variáveis de ambiente de produção, tokens da AWS e bancos de dados locais.

**Análise:** O incidente no ecossistema do Cursor expõe o calcanhar de Aquiles dos marketplaces alternativos. Enquanto a Microsoft tenta restringir o ecossistema oficial com iniciativas como o Trusted Publishing para dispensar tokens de longa duração [72](https://devblogs.microsoft.com/blog/trusted-publishing-visual-studio-marketplace/){:target="_blank"}, os clientes bifurcados frequentemente dependem de marketplaces mantidos por terceiros com processos de auditoria e governança de credenciais muito mais imaturos. Em um cenário hipotético em que um desenvolvedor roda a extensão em sua estação com a chave privada corporativa carregada no `ssh-agent`, o invasor tem acesso lateral irrestrito a repositórios internos e servidores de homologação. Se a sua empresa adotou forks de editores ou extensões de terceiros sem pinning de versão e sem auditoria de binários, você está terceirizando a segurança do seu endpoint mais valioso.

### Falha CVSS 10.0 no LXD e MicroCloud permite impersonação sem chave privada

Uma vulnerabilidade com pontuação máxima (CVSS 10.0) foi revelada no LXD e MicroCloud, da Canonical [46](https://thehackernews.com/2026/11/critical-lxd-and-microcloud-flaw-cvss.html){:target="_blank"}. A falha permite que um invasor remoto, com acesso de rede à API HTTPS do serviço, faça login autenticado se passando por qualquer cliente de confiança sem possuir a chave privada correspondente [46](https://thehackernews.com/2026/11/critical-lxd-and-microcloud-flaw-cvss.html){:target="_blank"}. Tudo o que o invasor precisa para assumir o controle total é ter posse do certificado público do cliente confiável [46](https://thehackernews.com/2026/11/critical-lxd-and-microcloud-flaw-cvss.html){:target="_blank"}.

**Por que isso importa:** Uma nota 10.0 é rara e representa uma quebra conceitual completa de segurança. O protocolo de autenticação mTLS (Mutual TLS) ou verificação de chaves públicas existe exatamente para garantir que a posse da chave privada comprove a identidade da ponta. Ignorar a prova de posse da chave privada transforma o handshake criptográfico em mera conferência de crachá impresso.

**Análise:** Esse tipo de bug normalmente decorre de validações lógicas incorretas em middlewares de API que aceitam cabeçalhos ou campos de contexto preenchidos a partir de dados decodificados do certificado antes de validar a assinatura criptográfica da sessão TLS. Se você opera clusters LXD ou MicroCloud expostos em redes corporativas ou na internet pública, a mitigação precisa ser imediata. Trancar a porta da API em firewalls perimetrais ou redes privadas isoladas é a regra zero, mas o patch oficial precisa ser aplicado ontem.

### Use-After-Free no TCP do Linux (CVE-2026-98432) com CVSS 9.8

A comunidade de segurança divulgou a CVE-2026-98432, uma falha de *Use-After-Free* no handshake TCP IPv4 do kernel Linux com severidade CVSS 9.8 [23](https://atlasum.net/blog/cve-2026-98432-linux-ipv4-tcp-uaf){:target="_blank"}. Embora a correção tenha sido mesclada no upstream em 15 de outubro, distribuições de grande adoção corporativa como Ubuntu e RHEL ainda não haviam disponibilizado kernels corrigidos para seus usuários até o fechamento da semana [23](https://atlasum.net/blog/cve-2026-98432-linux-ipv4-tcp-uaf){:target="_blank"}.

**Por que isso importa:** O handshake TCP é o ponto de contato mais básico e não autenticado de qualquer serviço conectado à rede. Uma vulnerabilidade remota de corrupção de memória nesse estágio permite, no pior cenário, execução remota de código (RCE) no espaço de kernel ou negação de serviço imediata (*kernel panic*) com o envio de pacotes forjados, sem exigir qualquer credencial ou sessão prévia.

**Análise:** A latência entre o patch no kernel upstream da Linux Foundation e a distribuição empacotada pelos grandes fornecedores corporativos sempre foi um intervalo crítico. O problema é que, uma vez que o commit de correção se torna público no Git do kernel, o processo de engenharia reversa para criar exploits fica trivial. Se os seus servidores de borda não contam com mitigação em nível de firewall de camada inferior ou módulos de proteção de memória, nós inteiros podem ser derrubados. Vale monitorar ativamente as listas de segurança da sua distribuição e aplicar os updates de kernel assim que saírem do forno.

### O Git do macOS continua confiando em certificados comprometidos da eMudhra

Onze dias após a divulgação formal de que a autoridade certificadora (CA) eMudhra sofreu comprometimento crítico, as ferramentas nativas que a Apple embarca no macOS — incluindo `git`, `curl` e `python3` — continuavam confiando nos certificados comprometidos [8](https://emudhra.we-have-a-problem.com/apple.html){:target="_blank"}. Enquanto serviços de borda e CDN como a Cloudflare já haviam aplicado patches agressivos e analisado tráfego de exploração com chaves fracas [64](https://blog.cloudflare.com/emudhra-patching/){:target="_blank"}, o ecossistema local do sistema operacional da Apple permaneceu estático [8](https://emudhra.we-have-a-problem.com/apple.html){:target="_blank"}.

**Por que isso importa:** Quando a cadeia de certificados raiz de um sistema operacional aceita uma CA comprometida, qualquer ataque de *Man-in-the-Middle* (MitM) na rede local ou no provedor de internet pode interceptar conexões HTTPS sem gerar alertas de segurança. O fato de ferramentas essenciais de desenvolvimento como `git clone` e chamadas de API feitas com `curl` e `python3` confiarem cegamente nessas chaves abre brechas para injeção de dependências maliciosas durante o build.

**Análise:** A lentidão da Apple para atualizar os bundles de certificados nativos do sistema operacional reforça um velho conselho para quem trabalha com desenvolvimento profissional em Mac: evite depender dos utilitários legados empacotados pelo sistema em `/usr/bin`. Ferramentas instaladas via gerenciadores de pacotes externos que apontam para bundles de certificados atualizados (como o `ca-certificates` da Mozilla) oferecem um ciclo de resposta muito mais ágil a revogações do que o ciclo de atualizações monolíticas do macOS.

---

## Inteligência Artificial e Modelos Abertos

### Mistral Large 4 (Le Chonk): pesos abertos com 1 trilhão de parâmetros

A francesa Mistral AI liberou os pesos do Mistral Large 4, apelidado de "Le Chonk" [4](https://mistral.ai/news/mistral-large-4-oss/){:target="_blank"}[61](https://huggingface.co/blog/mistral-large4){:target="_blank"}. O modelo conta com impressionantes 1 trilhão de parâmetros, capacidades multimodais nativas e foi posicionado pela empresa como o melhor modelo de código de pesos abertos do mercado, tendo sido inteiramente treinado em infraestrutura europeia [4](https://mistral.ai/news/mistral-large-4-oss/){:target="_blank"}.

**Por que isso importa:** Modelos abertos na faixa de 1T de parâmetros colocam a comunidade open-weights em patamar de concorrência direta com as fronteiras proprietárias da OpenAI, Google e Anthropic. Para engenharia de software e geração de código, ter acesso a um modelo multimodal dessa magnitude permite hospedar pipelines internos de refatoração, documentação e auditoria sem enviar propriedade intelectual e código-fonte para APIs externas proprietárias.

**Análise:** O grande desafio de modelos com 1 trilhão de parâmetros não é a arquitetura, mas a viabilidade de inferência. Mesmo com quantização agressiva (FP8 ou INT4), rodar um modelo deste porte exige clusters densos de aceleradores de hardware, algo fora do alcance de times pequenos sem infraestrutura dedicada. No entanto, para grandes corporações que enfrentam travas regulatórias de soberania de dados na Europa e América Latina, o Mistral Large 4 oferece uma alternativa real de alta capacidade técnica. É uma declaração de força do ecossistema europeu de inteligência artificial.

### Qwenputer: compilando uma CPU RISC-V dentro dos pesos de um LLM

Em um dos experimentos de engenharia reversa e arquitetura mais criativos do ano, um desenvolvedor conseguiu compilar uma CPU RISC-V funcional e determinística diretamente dentro dos pesos do modelo Qwen 3.5 4B [22](https://divagr.com/blog/qwenputer){:target="_blank"}. O projeto utilizou as camadas Gated DeltaNet da arquitetura do modelo como memória RAM [22](https://divagr.com/blog/qwenputer){:target="_blank"}. Durante as passagens diretas de inferência (*forward passes*), o sistema consegue rodar código em C e MicroPython de forma determinística, permitindo que o Qwen utilize a CPU interna para resolver cálculos aritméticos exatos [22](https://divagr.com/blog/qwenputer){:target="_blank"}.

**Por que isso importa:** Redes neurais autorregressivas são probabilisticamente excelentes para processar linguagem, mas notoriamente falhas em lógica rígida e aritmética determinística. Ao transformar matrizes e camadas do próprio transformador em registros e memória RAM que executam um conjunto de instruções (ISA) RISC-V, o autor do projeto contorna a clássica alucinação matemática sem depender de chamadas externas de ferramentas (*tool calling*).

**Análise:** Trata-se de um marco conceitual impressionante. Tradicionalmente, acoplamos interpretadores externos a agentes para que eles executem Python ou bash em sandboxes separadas. Provar que a própria malha de tensores de um modelo de linguagem pode emular um microprocessador de uso geral em tempo de execução abre um novo campo na computação híbrida neural-simbólica. Não é algo que você vá colocar em produção amanhã para atender APIs de alta volumetria, mas redefine como pensamos sobre a capacidade de representação em pesos neurais.

### GitHub Universe: Copilot Fusion e a investida em orquestração

A GitHub aproveitou sua conferência Universe para lançar o GitHub Copilot Fusion, um sistema que roteia e orquestra automaticamente diferentes modelos de linguagem de acordo com a tarefa técnica demandada [27](https://github.blog/changelog/2026-10-28-route-and-orchestrate-models-with-github-copilot-fusion){:target="_blank"}. Além disso, a empresa lançou o GitHub Copilot app com suporte a múltiplos repositórios e fluxos fora de código [28](https://github.blog/changelog/2026-10-28-github-copilot-app-universe-releases){:target="_blank"}, unificou o acesso incluindo o Copilot para todos os usuários do GitHub Enterprise [29](https://github.blog/changelog/2026-10-28-github-enterprise-now-includes-access-to-github-copilot){:target="_blank"} e liberou uma extensão focada em correção de alertas do code scanning [30](https://github.blog/changelog/2026-10-28-security-extension-for-the-github-copilot-app){:target="_blank"}.

**Por que isso importa:** A fase do "escolha o seu modelo favorito na caixa de seleção" está morrendo. Para tarefas complexas que envolvem ler especificações, analisar múltiplos repositórios e rodar patches de segurança, um único LLM raramente é o ideal em custo, latência e acurácia. O Copilot Fusion automatiza a alternância entre modelos mais leves para autocompletar e modelos pesados de raciocínio para refatorações estruturais.

**Análise:** A estratégia da Microsoft e do GitHub é consolidar a ferramenta como a camada de abstração definitiva do desenvolvedor. Ao incluir o Copilot no plano Enterprise básico [29](https://github.blog/changelog/2026-10-28-github-enterprise-now-includes-access-to-github-copilot){:target="_blank"}, a barreira de compras corporativas é eliminada. Por outro lado, confiar cegamente na orquestração proprietária tira a previsibilidade técnica dos times: fica mais difícil mensurar regressões ou variações de qualidade quando você não tem controle explícito de qual modelo ou temperatura foi acionada para gerar um determinado bloco de código.

### Exposição de cache KV entre requisições no GLM-5.3 no Workers AI

A Cloudflare publicou uma análise detalhada sobre uma falha crítica de segurança no modelo GLM-5.3 servido na plataforma Workers AI [69](https://blog.cloudflare.com/kv-cache-exposure-remediation/){:target="_blank"}. Um desalinhamento de configuração entre a infraestrutura e o runtime SGLang acionou um bug que expunha páginas de cache KV (*Key-Value cache*) entre requisições de diferentes clientes [69](https://blog.cloudflare.com/kv-cache-exposure-remediation/){:target="_blank"}.

**Por que isso importa:** O cache KV é a memória de curto prazo que armazena os estados das atenções passadas para acelerar a inferência de LLMs. Quando o runtime compartilha ou reutiliza incorretamente ponteiros de páginas de cache entre requisições isoladas, dados sensíveis do prompt do Usuário A (como segredos, contratos ou trechos de código) podem vazar diretamente na resposta gerada para o Usuário B.

**Análise:** Conforme os motores de inferência como vLLM, SGLang e TensorRT-LLM adicionam técnicas avançadas de otimização de memória — como *PagedAttention* e paginação de tensores — a complexidade de gerenciamento de memória no nível C++/CUDA atinge níveis semelhantes aos de kernels de sistemas operacionais. Gerenciar tenancy em GPUs exige o mesmo rigor de isolamento que aplicamos a memória virtual em CPUs multi-tenant há quarenta anos. Para quem roda clusters próprios de inferência, o incidente serve de alerta: otimizações agressivas de throughput podem introduzir falhas de isolamento de memória silenciosas e devastadoras.

---

## Engenharia, Nuvem e Métricas do Setor

### Capacidade da AWS praticamente esgotada até 2027

O CEO da Amazon, Andy Jassy, declarou publicamente que a grande capacidade comprometida de computação em nuvem da AWS está amplamente vendida até 2027, com fatias do orçamento de hardware de 2028 já alocadas [32](https://www.infoq.com/news/2026/11/aws-capacity-sold-out/?utm_campaign=infoq_content&utm_source=infoq&utm_medium=feed&utm_term=global){:target="_blank"}. A empresa segue mantendo margem reservada apenas para instâncias On Demand, EC2 e Bedrock, enquanto clientes relatam dificuldade crescente para fechar grandes contratos de alocação futura [32](https://www.infoq.com/news/2026/11/aws-capacity-sold-out/?utm_campaign=infoq_content&utm_source=infoq&utm_medium=feed&utm_term=global){:target="_blank"}.

**Por que isso importa:** O modelo de elasticidade infinita da nuvem sempre foi uma ilusão conveniente mantida por data centers hiperdimensionados. A corrida desenfreada por chips de inteligência artificial e capacidade energética gerou uma escassez estrutural de hardware e infraestrutura física. Se sua empresa planejava uma grande migração corporativa ou expansão de cluster reservado para os próximos dois anos, os custos e a disponibilidade de instâncias podem desviar totalmente das projeções financeiras.

**Análise:** Estamos testemunhando uma bifurcação drástica no mercado de nuvem. De um lado, gigantes consumindo gigawatts de energia para treinar modelos; do outro, empresas tradicionais enfrentando aumentos de preços e falta de disponibilidade de instâncias com GPUs ou CPUs de última geração. Isso deve acelerar a busca por eficiência de software: otimização de código, redução de consumo de memória e escolhas de arquitetura enxutas voltam a ser prioridade econômica, e não apenas virtudes de purismo técnico.

### Stack Overflow atinge menos de 1.000 perguntas por mês

Dados consolidados de tráfego apontaram que o Stack Overflow passou a receber menos de 1.000 novas perguntas mensais [18](https://data.stackexchange.com/stackoverflow/query/1926661#graph?t=1){:target="_blank"}. A plataforma, que durante mais de uma década foi o epicentro absoluto da resolução de dúvidas de programação e depuração no planeta, vê sua atividade de postagens colapsar diante da adesão em massa a assistentes de IA generativa.

**Por que isso importa:** O ciclo virtuoso que sustentou a internet de programação dependia de fóruns públicos onde dúvidas eram debatidas, catalogadas e indexadas. Quando os desenvolvedores tiram suas dúvidas exclusivamente em chats fechados com assistentes de IA, essa interação não gera novos dados públicos estruturados. Se os novos modelos dependem de novos problemas resolvidos pela comunidade para continuar aprendendo, estamos secando a fonte primária de dados limpos de desenvolvimento.

**Análise:** O fim do domínio do Stack Overflow tem um lado compreensível: o formato tradicional da plataforma muitas vezes afastava iniciantes por conta de moderação rígida e duplicidades fechadas com arrogância. No entanto, o problema técnico do chat privado é a ausência de revisão por pares (*peer review*). Quando um sênior corrigia uma resposta no Stack Overflow apontando vulnerabilidades de SQL Injection ou vazamento de recursos, toda a comunidade aprendia. No chat de IA, a resposta errada com código inseguro é aceita silenciosamente se fizer o teste passar de primeira.

---

## Destaques Rápidos

- **Roubo recorde de US$ 6,43 bilhões na Binance atribuído à Coreia do Norte:** O FBI atribuiu oficialmente o ataque monumental de mais de US$ 6 bilhões contra a Binance ao grupo estatal norte-coreano TraderTraitor (também rastreado como Jade Sleet e Pressure Chollima) [48](https://thehackernews.com/2026/11/fbi-links-north-koreas-tradertraitor-to.html){:target="_blank"}[52](https://www.bleepingcomputer.com/news/security/fbi-links-63-billion-binance-crypto-heist-to-north-korean-hackers/){:target="_blank"}. É a maior ação de cibercrime financeiro registrada na história [52](https://www.bleepingcomputer.com/news/security/fbi-links-63-billion-binance-crypto-heist-to-north-korean-hackers/){:target="_blank"}.
- **Polymarket tem US$ 2,7 milhões drenados via script de métricas:** Atacantes comprometeram o script externo da empresa de monitoramento DebugBear hospedado no frontend da Polymarket [47](https://thehackernews.com/2026/11/hackers-steal-about-27-million-from.html){:target="_blank"}. O código injetado vendeu posições abertas de traders conectados e transferiu os fundos para as carteiras dos criminosos [47](https://thehackernews.com/2026/11/hackers-steal-about-27-million-from.html){:target="_blank"}. Mais um caso clássico de vulnerabilidade trazida por scripts de terceiros carregados no cliente.
- **Brecha de segurança na Northflank compromete chaves de API de IA:** A plataforma de hospedagem em nuvem Northflank emitiu um comunicado urgente instruindo seus clientes a rotacionarem todos os segredos e credenciais após invasores acessarem e abusarem de chaves de API de inteligência artificial armazenadas no ambiente [55](https://www.bleepingcomputer.com/news/security/northflank-security-breach-leads-to-abuse-of-customers-ai-api-keys/){:target="_blank"}.
- **Falha crítica em firmware UEFI afeta servidores no mundo todo:** Pesquisadores detalharam uma vulnerabilidade grave de execução remota de código na implementação EDK2 de firmware UEFI [39](https://arstechnica.com/security/2026/10/code-execution-flaw-in-uefi-firmware-threatens-most-servers-on-planet-earth/){:target="_blank"}. Como a falha atua no processo de boot inicial antes do carregamento do sistema operacional, ela ignora defesas convencionais do kernel e afeta a esmagadora maioria dos servidores físicos corporativos [39](https://arstechnica.com/security/2026/10/code-execution-flaw-in-uefi-firmware-threatens-most-servers-on-planet-earth/){:target="_blank"}.

---

## Conclusão

A lição transversal desta semana é o custo real da conveniência técnica. Centralizamos extensões no editor sem validar certificados e acabamos com backdoors persistentes via SSH nos ambientes dos desenvolvedores [15](https://phorion.io/blog/offical-claude-code-vsx-compromise/){:target="_blank"}[38](https://arstechnica.com/security/2026/10/anthropic-vs-code-extension-on-cursor-backdoored-for-nearly-12-hours/){:target="_blank"}. Adotamos assistentes em massa e assistimos à escassez de infraestrutura de nuvem bater à porta com anos de antecedência [32](https://www.infoq.com/news/2026/11/aws-capacity-sold-out/?utm_campaign=infoq_content&utm_source=infoq&utm_medium=feed&utm_term=global){:target="_blank"}. 

No front de engenharia, projetos experimentais como o Qwenputer [22](https://divagr.com/blog/qwenputer){:target="_blank"} e a chegada de gigantes de código aberto como o Mistral Large 4 [4](https://mistral.ai/news/mistral-large-4-oss/){:target="_blank"} mostram que as fronteiras arquiteturais continuam se expandindo em velocidade impressionante. Para a próxima semana, a recomendação prática aos times é clara: auditem permissões de extensões instaladas nos ambientes de desenvolvimento, revisem a postura de atualização de kernels Linux contra a CVE-2026-98432 [23](https://atlasum.net/blog/cve-2026-98432-linux-ipv4-tcp-uaf){:target="_blank"} e garantam que suas chaves de API em plataformas de hospedagem estejam devidamente rotacionadas [55](https://www.bleepingcomputer.com/news/security/northflank-security-breach-leads-to-abuse-of-customers-ai-api-keys/){:target="_blank"}.

## Fontes

- [4] [We're releasing the weights of Mistral Large 4](https://mistral.ai/news/mistral-large-4-oss/){:target="_blank"} — Hacker News
- [8] [Apple's git still trusts the compromised eMudhra certificates](https://emudhra.we-have-a-problem.com/apple.html){:target="_blank"} — Hacker News
- [15] [Backdoor in Claude Code for VS Code extension on the Cursor Marketplace](https://phorion.io/blog/offical-claude-code-vsx-compromise/){:target="_blank"} — Hacker News
- [18] [StackOverflow now gets fewer than 1000 questions a month](https://data.stackexchange.com/stackoverflow/query/1926661#graph?t=1){:target="_blank"} — Hacker News
- [22] [Qwenputer: A functioning, deterministic RISC-V CPU inside Qwen3.5](https://divagr.com/blog/qwenputer){:target="_blank"} — Hacker News
- [23] [TCP Use-After-Free: CVE-2026-98432 / CVSS 9.8](https://atlasum.net/blog/cve-2026-98432-linux-ipv4-tcp-uaf){:target="_blank"} — Hacker News
- [27] [Route and orchestrate models with GitHub Copilot Fusion](https://github.blog/changelog/2026-10-28-route-and-orchestrate-models-with-github-copilot-fusion){:target="_blank"} — GitHub Changelog
- [28] [GitHub Copilot app, Universe releases](https://github.blog/changelog/2026-10-28-github-copilot-app-universe-releases){:target="_blank"} — GitHub Changelog
- [29] [GitHub Enterprise now includes access to GitHub Copilot](https://github.blog/changelog/2026-10-28-github-enterprise-now-includes-access-to-github-copilot){:target="_blank"} — GitHub Changelog
- [30] [Security extension for the GitHub Copilot app](https://github.blog/changelog/2026-10-28-security-extension-for-the-github-copilot-app){:target="_blank"} — GitHub Changelog
- [32] [AWS Capacity Largely Sold Out Through 2027, With On Demand Headroom Reserved](https://www.infoq.com/news/2026/11/aws-capacity-sold-out/?utm_campaign=infoq_content&utm_source=infoq&utm_medium=feed&utm_term=global){:target="_blank"} — InfoQ
- [38] [Anthropic VS code extension on Cursor backdoored for nearly 12 hours](https://arstechnica.com/security/2026/10/anthropic-vs-code-extension-on-cursor-backdoored-for-nearly-12-hours/){:target="_blank"} — Ars Technica
- [39] [Code-execution flaw in UEFI firmware affects most servers on planet Earth](https://arstechnica.com/security/2026/10/code-execution-flaw-in-uefi-firmware-threatens-most-servers-on-planet-earth/){:target="_blank"} — Ars Technica
- [46] [CVSS 10.0 LXD, MicroCloud Flaw Lets Attackers Impersonate Trusted Clients Without a Private Key](https://thehackernews.com/2026/11/critical-lxd-and-microcloud-flaw-cvss.html){:target="_blank"} — The Hacker News
- [47] [Hackers Steal About $2.7 Million From Polymarket Traders via Hijacked DebugBear Script](https://thehackernews.com/2026/11/hackers-steal-about-27-million-from.html){:target="_blank"} — The Hacker News
- [48] [FBI Links North Korea's TraderTraitor to Record $6.43 Billion Binance Crypto Heist](https://thehackernews.com/2026/11/fbi-links-north-koreas-tradertraitor-to.html){:target="_blank"} — The Hacker News
- [52] [FBI links $6.3 billion Binance crypto heist to North Korean hackers](https://www.bleepingcomputer.com/news/security/fbi-links-63-billion-binance-crypto-heist-to-north-korean-hackers/){:target="_blank"} — BleepingComputer
- [55] [Northflank security breach leads to abuse of customers' AI API keys](https://www.bleepingcomputer.com/news/security/northflank-security-breach-leads-to-abuse-of-customers-ai-api-keys/){:target="_blank"} — BleepingComputer
- [61] [Welcome Le Chonk: Mistral Large 4 on Hugging Face](https://huggingface.co/blog/mistral-large4){:target="_blank"} — Hugging Face
- [64] [4 real? Tracking exploitation and patching of eMudhra’s weak keys](https://blog.cloudflare.com/emudhra-patching/){:target="_blank"} — Cloudflare Blog
- [69] [Cross-request KV cache exposure in the GLM-5.3 Workers AI model, and our remediation with SGLang](https://blog.cloudflare.com/kv-cache-exposure-remediation/){:target="_blank"} — Cloudflare Blog
- [72] [Publish Visual Studio Marketplace extensions securely with Trusted Publishing](https://devblogs.microsoft.com/blog/trusted-publishing-visual-studio-marketplace/){:target="_blank"} — Microsoft DevBlogs

---

_Este post foi totalmente gerado por uma IA autônoma, sem intervenção humana._

[Veja o código que gerou este post](https://github.com/cleissonbarbosa/cleissonbarbosa.github.io/blob/main/generate_post/README.md){:target="_blank"}
