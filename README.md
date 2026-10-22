# NMS Endgame Overlay

Overlay de checklist endgame do **No Man's Sky** que roda por cima do jogo
e sincroniza com o checklist no **Obsidian**. Marque missões sem sair do
jogo — o `[x]` é salvo direto de volta no `.md`.

> Funciona com o jogo em modo **janela sem bordas**. Tela cheia exclusiva
> esconde qualquer overlay (vale para qualquer programa).

## Como usar

**Iniciar:** execute `iniciar.bat` (abre sem janela de console).

**Requisito:** Python com `pip install -r requirements.txt` (PySide6).

| Ação | Como |
|---|---|
| Travar / destravar cliques | Tecla **F8** (global, funciona no jogo) ou o pill `○ Livre · F8` |
| Chamar o overlay sem alt-tab | Tecla **F9** (global): traz a janela p/ frente e destrava; de novo devolve o foco ao jogo e restaura a trava |
| Arrastar a janela | Segure a barra superior |
| Redimensionar | Canto inferior-direito |
| Marcar missão | Clique no checkbox ou no texto |
| Focar missão (`★`) | Clique na estrela: a janela encolhe num cartão "Objetivo atual" amarelo |
| Sair do foco | Botão `Sair do foco`, ★ de novo, ou ★ de outra missão |
| Buscar | Digite no campo de busca (`Enter` pula entre seções, `Esc` limpa) |
| Trocar de seção | Cards do overview, botão `‹ Início` ou menu |
| Transparência do fundo | Slider do rodapé (o texto fica sempre 100% legível) |
| Mais opções (`⋯`) | Recarregar, trocar tecla de trava, redefinir posição, abrir pasta |
| Fechar de verdade | `✕` (encerra o processo; não fica em segundo plano) |

Travado = cliques atravessam a janela (não atrapalha o jogo).
Livre = dá para clicar e marcar.
Com o jogo em janela sem bordas, o **F9** resolve o alt-tab: ele guarda
a janela do jogo, destrava e foca o overlay; apertando de novo, o foco
volta ao jogo e a trava anterior é restaurada. Ambas as teclas podem
ser trocadas no menu `⋯`.

## Checklist no Obsidian

O overlay lê os tópicos direto do `.md` e salva o `[x]` de volta nele:

- Seções são os `## `, subtítulos os `### `, itens os `- [ ]` / `- [x]`.
- Backup automático em `.bak` antes da primeira escrita da sessão.
- Se o arquivo mudar no Obsidian enquanto você marca algo, o overlay
  recarrega, preserva sua marcação e avisa ("mesclado e salvo").
- Caminho padrão: checklist embutido em `checklist/nms-endgame-checklist.md`.
  Dá para trocar pelo diálogo de arquivo na primeira abertura, ou apontando
  `md_path` para um `.md` da sua vault no Obsidian (ex.: a versão com
  checkboxes `[x]` guardados lá).

## Configuração (`overlay_config.json`)

Salva automaticamente: posição, tamanho, transparência do fundo,
estado trava/livre, tecla, missão em foco e última visão (overview/seção).

| Chave | Padrão | Descrição |
|---|---|---|
| `md_path` | `checklist/nms-endgame-checklist.md` | Arquivo `.md` do checklist (pode apontar para o seu Obsidian) |
| `opacity` | `0.88` | Transparência **do fundo** (25–100%) |
| `width` / `height` | `340` / `480` | Tamanho da janela |
| `locked` | `false` | Começar travado |
| `hotkey_vk` / `hotkey_name` | `119` / `"F8"` | Tecla global (troque no menu `⋯`) |
| `x` / `y` | `null` | Posição (`null` = canto inferior-direito) |
| `focus` | `null` | Missão em foco `{"sec", "text"}` |
| `view` | overview | Última visão `{"home", "sec"}` |

## Atalho da tecla de trava

Clique em `⋯` → *Trocar tecla de trava*, depois pressione a nova tecla
(`Esc` cancela). Valem `F1`–`F24`, letras, números e teclas como
Insert/Delete/Home/End/PgUp/PgDn/setas/Pause.

Proteções: se a tecla estiver em uso por outro programa, o overlay
**não trava** (para não prender você sem como destravar); um vigia
periódico readquire a tecla e, em último caso, destrava sozinho.

## Estrutura

```text
nms-overlay/
├── iniciar.bat              # inicia sem console (pythonw)
├── nms_overlay.py           # app (lógica + interface)
├── checklist/               # checklist embutido (padrão, sem progresso)
│   └── nms-endgame-checklist.md
├── test_overlay.py          # suite headless (rodar com o venv)
└── requirements.txt         # PySide6>=6.6
```

`overlay_config.json` é a config pessoal (posição, teclas, `md_path`) — fica
na pasta do app e não vai para o repositório.

Interface (`nms_overlay.py`): header, dashboard de progresso, navegação
master-detail (overview em cards + detalhe por seção), itens de checklist,
cartão de foco, rodapé enxuto — tema "Deep Space" em QSS gerado por
`build_qss()`.

## Testes

```bat
venv\Scripts\python.exe test_overlay.py
```

Roda headless (offscreen): posição, arrasto, toggle/save/backup, merge do
Obsidian, slider, rolagem, busca, overview, trava/hotkey, click-through,
watchdog, fechar, foco e visão persistida. Esperado: `TEST-OK geral.`

## Problemas comuns

- **Overlay não aparece no jogo** → coloque o NMS em janela sem bordas.
- **F8 não destrava** → outro programa pode estar usando a tecla; troque
  no menu `⋯` ou clique no pill com o overlay livre.
- **Duas janelas / F8 brigando** → há duas instâncias abertas; feche uma
  pelo Gerenciador de Tarefas (`pythonw.exe`).
- **Texto apagado ao mexer na transparência** → não deve mais acontecer
  (só o fundo fica transparente); se ver, reporte.
- **Checklist não abre** → confira `md_path` no `overlay_config.json`.

## Executável (releases)

Cada versão marcada com tag (ex.: `v1.0.0`) é compilada automaticamente pelo
GitHub Actions e publicada na aba Releases:

- `NMS-Overlay-windows-x64.exe` — Windows x64, arquivo único, sem console.

Não é preciso Python: o checklist embutido já vem dentro. A config
(`overlay_config.json` + posições/teclas) é criada ao lado do `.exe` na
primeira execução. Ainda recomendo apontar `md_path` para o seu `.md` do
Obsidian para continuar sincronizando seu progresso — o executável inclui
o checklist apenas como padrão inicial.

> O binário é somente Windows: o overlay depende de APIs do sistema
> (`user32`) para hotkey global e click-through, que não existem no Linux.
