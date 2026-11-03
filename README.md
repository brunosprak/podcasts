# Podcasts

Catálogo estático de podcasts publicado pelo GitHub Pages. Cada programa tem sua
própria página, arquivos de mídia e feed RSS compatível com aplicativos de podcast.

## Estrutura

- `data.json`: catálogo de podcasts e episódios.
- `podcasts/<slug>/media/`: áudio e imagens de cada programa.
- `tools/build_site.py`: gera a página inicial, páginas dos programas e feeds RSS.
- `tools/sync_youtube.py`: sincroniza o Academic Agent com uma janela rotativa.
- `assets/`: estilos e comportamento da interface.

## Sincronizar o Academic Agent

Instale o `yt-dlp`, confirme que o `ffmpeg` está disponível e execute:

```bash
python3 tools/sync_youtube.py
```

A rotina consulta o canal, baixa o que estiver faltando, conserva somente os cinco
episódios mais recentes, remove as mídias que saíram da janela e reconstrói o site
e o RSS. O limite está definido em `EPISODE_LIMIT` no próprio script.

## Atualizar apenas o site

Depois de uma alteração manual em `data.json`, execute:

```bash
python3 tools/build_site.py
```

O site é servido em `https://brunosprak.github.io/podcasts/`.

## Feed atual

- Academic Agent — áudio:
  `https://brunosprak.github.io/podcasts/podcasts/academic-agent/feed.xml`

Este é um feed independente e não oficial. A autoria do conteúdo e os links para
as publicações originais são preservados nas páginas e no RSS.

## Automação

Para uma execução diária sem aumentar indefinidamente o histórico Git, prefira um
workflow do GitHub Actions que execute a sincronização e publique o resultado como
artefato do GitHub Pages. Não faça commits automáticos dos MP3s na `main`: mesmo
depois da rotação, os arquivos removidos continuariam armazenados no histórico.
