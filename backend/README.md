# Contextual Post Explainer Backend

Backend FastAPI da POC. Ele recebe uma URL pública do Bluesky, busca contexto público via provider de search, lê as páginas retornadas, ranqueia evidências em memória e gera uma explicação com 3 a 5 bullets citados.

## Requisitos

- Python 3.11+
- `uv`
- `OPENAI_API_KEY`
- Para modo live: `SEARCH_PROVIDER` e a chave do provider escolhido

## Setup

```bash
cd backend
uv sync
```

Copie `.env.example` para `.env` na raiz do projeto e preencha as chaves.

## Rodar API

```bash
make backend-run
```

Endpoints:

- `GET /api/health`
- `GET /api/config/status`
- `POST /api/explain`

Exemplo:

```bash
curl -X POST http://localhost:8000/api/explain \
  -H "Content-Type: application/json" \
  -d '{"url":"https://bsky.app/profile/rbreich.bsky.social/post/3mltultyalm2v"}'
```

## Live vs eval

O modo live usa Bluesky público e um search provider configurado. Sem search provider, retorna `search_provider_required`.

O modo eval usa apenas fixtures locais em `eval/` e não chama Bluesky, Brave, Tavily ou páginas web ao vivo. A única dependência externa do eval real é OpenAI para geração, embeddings e judge quando habilitado.

## Validação de fontes

O live usa duas camadas complementares:

- `source_quality`: filtra fontes sem texto útil, antigas demais para o evento ou sem âncoras dinâmicas extraídas do post.
- `CitationValidator`: valida se a fonte citada é adequada para o tipo de afirmação do bullet.

Cada fonte recebe `source_category` e `source_role`. Cada bullet recebe `claim_label`, `context_modifiers`, `confidence` e `warnings`.

Fonte social pode ser usada para entender o autor ou reações públicas, mas não deve ser a única base de um `confirmed_fact`. Quando isso acontece, a API retorna warning estruturado em vez de tratar a fonte como prova factual.

## Search providers

Valores aceitos em `SEARCH_PROVIDER`:

- `brave`
- `tavily`
- `composite`

Para a POC, use `SEARCH_PROVIDER=tavily` como caminho seguro. Como o acesso gratuito do Brave foi habilitado até 2026-06-01, a validação real pode usar `SEARCH_PROVIDER=composite` enquanto `TAVILY_API_KEY` e `BRAVE_API_KEY` estiverem configuradas.

`composite` usa todas as chaves configuradas (`BRAVE_API_KEY`, `TAVILY_API_KEY`), executa providers em paralelo, mescla resultados e deixa a deduplicação/reranking escolher as melhores fontes.

Em modo `composite`, os artifacts em `runs/live/` incluem métricas P2 para
comparação entre providers:

- `search_results_by_provider`;
- `search_provider_overlap`;
- `search_provider_overlap_count`;
- `ranked_sources_by_provider`;
- `ranked_multi_provider_source_count`;
- `cited_sources_by_provider`;
- `cited_multi_provider_source_count`.

Para comparar manualmente:

```bash
SEARCH_PROVIDER=tavily make backend-run
SEARCH_PROVIDER=brave make backend-run
SEARCH_PROVIDER=composite make backend-run
```

Execute a mesma URL nos três modos e compare os artifacts gerados. Fontes
retornadas por mais de um provider preservam `providers`, `provider_queries` e
`provider_result_count`; o ranking aplica um pequeno boost para essa
convergência, sem tratar isso como prova factual.

## Comparative analysis

Cada artifact live registra um snapshot da configuração usada:

- `search_provider`
- `openai_generation_model`
- `openai_judge_model`
- `openai_embedding_model`
- `openai_vision_model`
- `prompt_config_path`
- `prompt_config_hash`
- `comparison_group_id`
- `comparison_config_id`

A API `GET /api/analysis?limit=500` agrega os artifacts locais e expõe:

- comparação por Search Provider;
- comparação por stack LLM;
- mudança de comportamento por URL;
- link indireto para o run_id que pode ser aberto em Observability.

Para planejar ou executar a matriz comparativa:

```bash
cd backend
uv run python -m app.analysis.runner --matrix search --dry-run
uv run python -m app.analysis.runner --matrix llm --dry-run
```

Remova `--dry-run` apenas quando quiser executar chamadas reais para Bluesky,
Search Providers e OpenAI. O runner grava um resumo em `runs/comparisons/`.

## Eval

```bash
make eval
```

Saídas:

- `eval/results/latest.json`
- `eval/results/latest.md`
- `runs/eval/{run_id}.json`

O eval P1 inclui `groundedness`: cada bullet é avaliado contra as fontes
citadas pelo `OPENAI_JUDGE_MODEL` e recebe verdict `supported`,
`partially_supported` ou `unsupported`. Essa checagem é métrica de avaliação,
não substitui o `CitationValidator` estrutural do runtime.

## Imagens

Quando `OPENAI_VISION_MODEL` está configurado, o live analisa imagens do post
antes da decomposição de queries. A análise separa:

- OCR: texto visível na imagem;
- descrição visual;
- tipo da imagem.

Alt text do Bluesky é preservado, mas não substitui OCR nem descrição visual.
Claims factuais externos continuam exigindo fonte externa; a imagem serve como
contexto pesquisável e como evidência apenas para observações visuais.

## Qualidade

```bash
make backend-lint
make backend-test
```

## Observabilidade

Cada request recebe `x-trace-id`. Cada execução live/eval recebe `run_id` e gera artifact local em `runs/`. Logs são JSON e secrets são redigidos antes de persistência em artifact.
