# Backend Template - Instruções

## Python

Projeto Python 3.12. Virtualenv local em `.venv/` — **sempre use o Python do venv**, nunca o Python global.

- Ativar o venv: `source .venv/bin/activate && python ...`
- Chamar o binário direto: `.venv/bin/python ...` ou `.venv/bin/pytest ...`

Nunca rode `python ...` / `pip install ...` sem o venv ativo.

Dependências em `requirements*.txt`. Instalação: `make install` (base + dev). Extras: `make install-postgres`, `make install-mssql`, `make install-ai`.

Testes: `make test` (`.venv/bin/pytest`).

Migrações: `make migrate-new msg="..."`, `make migrate-up`.

Start local: `make run` (ou `./start_services.sh`, adicionado em task posterior).

## Adaptando o template (clonou agora? leia isto)

Se você clonou este template para começar um projeto, leia primeiro **[docs/template-customization.md](docs/template-customization.md)**. Esse documento é escrito para um assistente LLM (Claude Code, etc.) e contém:

- Taxonomia de módulos (core vs opcional).
- Receitas para remover módulos opcionais (AI, reports) sem quebrar a arquitetura.
- Receita para substituir a feature `users` (sample) pela sua primeira feature real.

Quando o usuário pedir "remova X" ou "comece novo projeto sem Y", consulte aquele arquivo antes de mexer no código.

## Arquitetura

Camadas + vertical slicing por feature. Regra de dependência:

```
api → use_cases → domain ← infrastructure
```

`domain/` é Python puro — nunca importa de `infrastructure/` nem de `use_cases/`.

### Adicionando uma feature nova

Siga o playbook em [README.md → "Adicionando uma nova feature"](README.md). Os 5 passos são domain → infrastructure → use_cases → api → tests, criando uma pasta nova em cada camada sem mexer nas outras features.

Antes de começar, identifique:
- **Aggregate root da feature** (ex.: `Project`) → vira `app/domain/<feature>/<feature>.py`.
- **VOs específicos da feature** ficam em `app/domain/<feature>/`. Se for reutilizável (ex.: `Money`), sobe para `app/domain/shared/value_objects/`.
- **Comandos vs queries**: mutação = `commands/`, leitura = `queries/`. Um arquivo por caso de uso.

Sempre rodar `make migrate-new msg="..."` depois de adicionar o mapping em `app/infrastructure/db/mappings/` e importar em `app/migrations/env.py`.

### Não existe pasta `services/` — o handler é a camada de serviço

CQRS com domínio rico: cada `*Handler` em `app/use_cases/<feature>/{commands,queries}/` orquestra repositórios + entidades. Essa é a sua "service layer". Não crie uma camada paralela.

**Regra cross-entity** (ex.: regra que envolve `User` E `Project`):

1. Default — **handler com múltiplos repositórios via DI**. Ex.: `AssignProjectOwnerHandler.__init__(self, projects: IProjectRepository, users: IUserRepository)`. O handler vive na feature "dona" da operação (no exemplo, `app/use_cases/projects/commands/`).
2. Cross-feature **só via interface** (`Protocol` em `domain/<outra>/repository.py`), nunca importando a implementação concreta de `infrastructure/`.
3. Domain service em `domain/shared/` apenas para invariantes puras de domínio que não pertencem a nenhuma das entidades. Raro — só use quando uma regra realmente não cabe em nenhum aggregate.

### Anti-patterns (não fazer)

- ❌ Handler chamando outro handler. Se sentir essa vontade, crie um handler de mais alto nível que orquestra os repositórios diretamente.
- ❌ Lógica de negócio em `routes.py`. Route só valida HTTP (Pydantic), chama o handler, mapeia `Result` → status code.
- ❌ `domain/<feature_a>/` importando de `domain/<feature_b>/`. Se duas features compartilham conceito, ele sobe para `domain/shared/`.
- ❌ `use_cases/` ou `domain/` importando de `infrastructure/`.
- ❌ Criar pasta `services/` ou `app/services/`. Não é o estilo do projeto.
