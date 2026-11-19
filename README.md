# PL Único — interface Streamlit

Interface do notebook **PL Único — Batalha e Serra do Facão em cascata**.

## Executar localmente

1. Instale Python 3.10+ e as bibliotecas de sistema GLPK (no Ubuntu: `sudo apt-get install libglpk40 glpk-utils`).
2. Na pasta do projeto: `pip install -r requirements.txt`.
3. Inicie: `streamlit run app.py`.

## Publicar no Streamlit Community Cloud

Envie os arquivos `app.py`, `otimizador.py`, `requirements.txt` e `packages.txt` ao seu repositório do GitHub. Crie um aplicativo no Streamlit Community Cloud selecionando `app.py` como arquivo principal. Verifique no log de implantação que a biblioteca CVXOPT foi instalada com suporte ao GLPK; a disponibilidade do solver depende do ambiente.

## Fidelidade ao notebook

- Os dados das duas UHEs, duas UTEs, as afluências locais dos dois cenários e as 720 horas por estágio foram preservados.
- A função `pl_unico` foi transcrita diretamente do notebook, incluindo os balanços da cascata, limites, função objetivo e solução CVXOPT/GLPK.
- O cenário otimista corresponde ao índice **0**, e o pessimista ao índice **1**; o notebook original executava ambos separadamente.
- A carga é configurável mas inicia em **250 MW** nos três meses; com 250 MW, corresponde ao dado original.
- Os meses de agosto a outubro permanecem fixos porque o balanço hídrico depende do volume armazenado do estágio anterior.
- O aplicativo valida os balanços numéricos e apresenta custos, geração, volumes, CMO, déficit e exportação de resultados.
- O sistema original usa afluências locais/incrementais na UHE a jusante, hipótese didática explicitada no notebook.
- Foi retirada a instalação automática de dependências durante a execução (apropriada apenas para notebook); a instalação fica em `requirements.txt` e `packages.txt`.

**Atenção:** testes locais e a implantação real requerem que CVXOPT/GLPK estejam disponíveis no ambiente. Não foram alteradas as equações do modelo.
