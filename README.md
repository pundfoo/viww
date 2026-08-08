# viww

The vim web wowser.

License: GPL-3.0-or-later.

`viww` is a tiny Neovim remote plugin wrapped around:

```text
curl -> pandoc -> html -> plain text
```

It opens the rendered text in a scratch buffer and appends numbered links.

## Install

Requirements: Neovim Python provider with `pynvim`, `curl`, and `pandoc`.

Put the file here:

```text
rplugin/python3/viww.py
```

Or point any plugin manager at this repo.

Then run:

```vim
:UpdateRemotePlugins
```

Restart Neovim if needed.

## Use

```vim
:Viww https://example.com
:Viww example.com
:Viww search terms
```

In a viww buffer:

```text
<CR>  follow link under cursor
H     back
R     reload
```

Commands:

```vim
:ViwwFollow [n]
:ViwwBack
:ViwwReload
```
