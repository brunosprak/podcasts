# Podcasts

Catálogo estático de podcasts publicado pelo GitHub Pages. Cada programa tem sua
própria página, arquivos de mídia e feed RSS compatível com aplicativos de podcast.

## Estrutura

- `data.json`: catálogo de podcasts e episódios.
- `podcasts/<slug>/media/`: áudio e imagens de cada programa.
- `tools/build_site.py`: gera a página inicial, páginas dos programas e feeds RSS.
- `assets/`: estilos e comportamento da interface.

## Atualizar o site

Edite `data.json`, adicione a mídia ao diretório correspondente e execute:

```bash
python3 tools/build_site.py
```

Depois, valide e publique as alterações na branch `main`. O site foi preparado
para ser servido em `https://brunosprak.github.io/podcasts/`.

## Feed atual

- Academic Agent — áudio:
  `https://brunosprak.github.io/podcasts/podcasts/academic-agent/feed.xml`

Este é um feed independente e não oficial. A autoria do conteúdo e os links para
as publicações originais são preservados nas páginas e no RSS.
