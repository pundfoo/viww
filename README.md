# viww

The vim web wowser. Inspired by Emacs' Web Wowser.

`viww` is a single file rplugin for neovim inspired by emacs' eww. It is a thin wrapper around
`curl -> pandoc -> (html => plain)`

`:Viww keywords` searches duckduckgo by default or `:Viww {url}` opens the html as plain text.

Requires `pynvim`, `curl`, and `pandoc`.

## Install

Just put the file like so in your runtimepath:

```text
rplugin/python3/viww.py
```
Or point your plugin manager to this repo.

Then run:

```vim
:UpdateRemotePlugins
```

Restart Neovim if needed.

## Use

```vim
:Viww https://example.com
:Viww example.com
:Viww terms keywords quick search
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
